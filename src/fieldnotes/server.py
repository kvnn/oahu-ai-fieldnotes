"""FastAPI review board for the Field Notes workflow."""

from __future__ import annotations

import logging
import json
import re
import subprocess
from hashlib import sha256
from html import escape
from pathlib import Path
from time import perf_counter
from uuid import UUID
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

try:
    from chainlit.utils import mount_chainlit
except ImportError:  # pragma: no cover - optional runtime integration
    mount_chainlit = None

from fieldnotes.book_text import (
    BookRewriteUnavailable,
    RewriteMode,
    build_brief_skeleton,
    chunk_by_id,
    replace_chunk,
    rewrite_book_chunk,
    split_markdown_chunks,
)
from fieldnotes.chapters import (
    autosave_chapter_draft,
    chapter_draft_by_version,
    chapter_draft_versions,
    chapter_slug,
    create_chapter_draft_version,
    get_or_create_chapter_draft,
    latest_chapter_draft,
)
from fieldnotes.config import load_config
from fieldnotes.db.models import (
    CandidateStatus,
    ChapterBrief,
    ChapterStatus,
    ExtractedCandidate,
    KnowledgeNode,
    Project,
    RenderStatus,
    RenderedOutput,
    ReviewDecision,
    SourceChunk,
    SourceMaterial,
    utc_now,
)
from fieldnotes.db.session import make_engine, make_session_factory
from fieldnotes.production import mixam_page_count_profile, print_output_path
from fieldnotes.rendering import (
    record_book_pdf_render,
    render_book_pdf,
    render_database_book_pdf,
    render_output_type,
)
from fieldnotes.review import (
    discard_source_chunk,
    keep_source_chunk,
    promote_candidate,
    reject_candidate,
)
from fieldnotes.workflow import ensure_project, first_volume


PACKAGE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
logger = logging.getLogger("fieldnotes.server")
CONTEXT_PAGE_SIZE = 12
CHAINLIT_PATH = "/chainlit"
CHAINLIT_TARGET = PACKAGE_DIR / "chat_app.py"
PAGE_COUNT_OUTPUT_TYPE = "page_count"
FINAL_PDF_PROFILE = "print"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MIXAM_PAGE_COUNT_PROFILE = mixam_page_count_profile()


class DraftSaveRequest(BaseModel):
    body: str = ""


class BookChunkEditRequest(BaseModel):
    edited_text: str = ""
    base_version: int | None = None


class BookTextSaveRequest(BaseModel):
    body: str = ""
    base_version: int | None = None


class BookChunkRewriteRequest(BaseModel):
    mode: RewriteMode
    instruction: str = ""
    base_version: int | None = None


class ChapterOrderRequest(BaseModel):
    chapter_ids: list[UUID]


class ChapterStatusRequest(BaseModel):
    status: str


class ChapterCreateRequest(BaseModel):
    title: str
    subtitle: str = ""


class ChapterMetadataRequest(BaseModel):
    title: str
    subtitle: str = ""


def _configure_tracing_logger() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)


def _clean_log_text(value: str | None) -> str:
    return ANSI_ESCAPE_RE.sub("", value or "")


def _text_tail(value: str | None, limit: int = 2000) -> str:
    return _clean_log_text(value)[-limit:]


def _request_trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", ""))


def _configure_chainlit(app: FastAPI) -> None:
    app.state.chainlit_path = CHAINLIT_PATH
    app.state.chainlit_target = str(CHAINLIT_TARGET)
    if mount_chainlit is None:
        app.state.chainlit_available = False
        logger.info("chainlit.unavailable target=%s", CHAINLIT_TARGET)
        return

    mount_chainlit(app=app, target=str(CHAINLIT_TARGET), path=CHAINLIT_PATH)
    app.state.chainlit_available = True
    logger.info("chainlit.mounted path=%s target=%s", CHAINLIT_PATH, CHAINLIT_TARGET)


def create_app(
    *,
    config_path: str | Path = "fieldnotes.config.toml",
    database_url: str | None = None,
) -> FastAPI:
    _configure_tracing_logger()
    config = load_config(config_path)
    engine = make_engine(database_url or config.database_url)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="Oahu AI Field Notes Review Board")
    app.state.config = config
    app.state.session_factory = session_factory
    app.mount(
        "/static",
        StaticFiles(directory=PACKAGE_DIR / "static"),
        name="static",
    )
    _configure_chainlit(app)

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        trace_id = uuid4().hex
        request.state.trace_id = trace_id
        started = perf_counter()
        client = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        query = request.url.query
        logger.info(
            "request.start trace_id=%s method=%s path=%s query=%r client=%s user_agent=%r",
            trace_id,
            request.method,
            request.url.path,
            query,
            client,
            user_agent,
        )
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000
            logger.exception(
                "request.exception trace_id=%s method=%s path=%s elapsed_ms=%.2f "
                "error_type=%s",
                trace_id,
                request.method,
                request.url.path,
                elapsed_ms,
                type(exc).__name__,
            )
            return PlainTextResponse(
                f"Internal Server Error\ntrace_id={trace_id}\n",
                status_code=500,
                headers={"X-Trace-Id": trace_id},
            )

        elapsed_ms = (perf_counter() - started) * 1000
        response.headers["X-Trace-Id"] = trace_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", "")
        log = logger.warning if response.status_code >= 400 else logger.info
        log(
            "request.complete trace_id=%s method=%s path=%s route=%s query=%r "
            "status_code=%s elapsed_ms=%.2f",
            trace_id,
            request.method,
            request.url.path,
            route_path,
            query,
            response.status_code,
            elapsed_ms,
        )
        return response

    def get_session() -> Session:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/chapters", status_code=302)

    @app.get("/chat/status")
    def chat_status() -> dict[str, str | bool]:
        return {
            "available": bool(app.state.chainlit_available),
            "path": app.state.chainlit_path,
            "target": Path(app.state.chainlit_target).name,
        }

    @app.get("/api/book-text")
    def compiled_book_text(
        include_drafts: bool = Query(default=False),
        output_format: str = Query(default="raw", alias="format"),
        session: Session = Depends(get_session),
    ) -> dict:
        normalized_format = output_format.lower()
        if normalized_format not in {"raw", "vivliostyle"}:
            raise HTTPException(status_code=422, detail="format must be raw or vivliostyle")
        project = ensure_project(session, config)
        chapters = _compiled_book_chapters(
            session,
            _ordered_chapter_briefs(session, project),
            include_drafts=include_drafts,
        )
        markdown = _compiled_book_markdown(chapters, output_format=normalized_format)
        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "slug": project.slug,
            },
            "include_drafts": include_drafts,
            "format": normalized_format,
            "chapter_count": len(chapters),
            "word_count": _word_count(markdown),
            "markdown": markdown,
            "chapters": chapters,
        }

    @app.get("/api/book-text/page-counts")
    def cached_book_page_counts(
        request: Request,
        include_drafts: bool = Query(default=False),
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        chapters = _compiled_book_chapters(
            session,
            _ordered_chapter_briefs(session, project),
            include_drafts=include_drafts,
        )
        response = _page_count_response(session, chapters, include_drafts=include_drafts)
        _log_page_count_response(
            "page_counts.cached",
            response,
            trace_id=_request_trace_id(request),
            project_slug=project.slug,
        )
        return response

    @app.post("/api/book-text/page-counts")
    def render_book_page_counts(
        request: Request,
        include_drafts: bool = Query(default=False),
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        chapters = _compiled_book_chapters(
            session,
            _ordered_chapter_briefs(session, project),
            include_drafts=include_drafts,
        )
        trace_id = _request_trace_id(request)
        logger.info(
            "page_counts.render.start trace_id=%s project=%s include_drafts=%s "
            "chapter_count=%s profile=%s",
            trace_id,
            project.slug,
            include_drafts,
            len(chapters),
            MIXAM_PAGE_COUNT_PROFILE["id"],
        )
        for chapter in chapters:
            _render_chapter_page_count(
                config.root,
                session,
                project,
                chapter,
                trace_id=trace_id,
            )
        session.flush()
        response = _page_count_response(session, chapters, include_drafts=include_drafts)
        _log_page_count_response(
            "page_counts.render.complete",
            response,
            trace_id=trace_id,
            project_slug=project.slug,
        )
        return response

    @app.get("/api/book-text/final-pdf")
    def latest_final_pdf(
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        record = _latest_final_pdf_record(session, project)
        return _final_pdf_payload(config.root, record)

    @app.post("/api/book-text/final-pdf")
    def render_final_pdf(
        request: Request,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        volume = first_volume(session, project)
        trace_id = _request_trace_id(request)
        logger.info(
            "final_pdf.render.start trace_id=%s project=%s profile=%s",
            trace_id,
            project.slug,
            FINAL_PDF_PROFILE,
        )
        chapters = _compiled_book_chapters(
            session,
            _ordered_chapter_briefs(session, project),
            include_drafts=False,
        )
        markdown = _compiled_book_markdown(chapters, output_format="vivliostyle")
        result = render_database_book_pdf(
            config.root,
            markdown=markdown,
            chapter_refs=_render_chapter_refs(chapters),
            word_count=_word_count(markdown),
        )
        record = record_book_pdf_render(
            session,
            project=project,
            volume=volume,
            config_path=config.vivliostyle_config,
            result=result,
        )
        log = logger.warning if record.status == RenderStatus.FAILED.value else logger.info
        log(
            "final_pdf.render.complete trace_id=%s project=%s profile=%s "
            "status=%s returncode=%s output_path=%s error=%r",
            trace_id,
            project.slug,
            FINAL_PDF_PROFILE,
            record.status,
            result.returncode,
            record.output_path,
            result.metadata.get("error"),
        )
        return _final_pdf_payload(config.root, record)

    @app.get("/api/book-text/final-pdf/file")
    def final_pdf_file(
        session: Session = Depends(get_session),
    ) -> FileResponse:
        project = ensure_project(session, config)
        record = _latest_final_pdf_record(session, project, succeeded_only=True)
        if record is None:
            raise HTTPException(status_code=404, detail="final PDF has not rendered successfully")
        path = _safe_dist_output_path(config.root, record.output_path)
        if path is None:
            raise HTTPException(status_code=403, detail="final PDF path is outside dist")
        if not path.exists():
            raise HTTPException(status_code=404, detail="final PDF file is missing")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
        )

    @app.get("/api/chapters/{chapter_brief_id}/book-text")
    def chapter_book_text(
        chapter_brief_id: UUID,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        return _book_text_payload(session, brief)

    @app.post("/api/chapters/{chapter_brief_id}/book-text")
    def save_book_text(
        request: Request,
        chapter_brief_id: UUID,
        payload: BookTextSaveRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        _, base_version, previous_draft = _current_book_body(
            session,
            brief,
            payload.base_version,
        )
        draft = create_chapter_draft_version(
            session,
            brief,
            payload.body,
            model_metadata={
                "action": "full_book_text_save",
                "base_version": base_version,
                "previous_draft_id": str(previous_draft.id) if previous_draft else None,
            },
            editor_notes="Book Text full-chapter editor save.",
        )
        return {
            **_book_text_payload(session, brief, draft=draft),
            "status": "saved",
            "persistence": True,
            "previous_version": base_version,
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters/{chapter_brief_id}/chunks/{chunk_id}/edit")
    def edit_book_chunk(
        request: Request,
        chapter_brief_id: UUID,
        chunk_id: str,
        payload: BookChunkEditRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        body, base_version, previous_draft = _current_book_body(
            session,
            brief,
            payload.base_version,
        )
        if chunk_by_id(body, chunk_id) is None:
            raise HTTPException(status_code=404, detail="book chunk not found")
        try:
            next_body = replace_chunk(body, chunk_id, payload.edited_text)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        draft = create_chapter_draft_version(
            session,
            brief,
            next_body,
            model_metadata={
                "action": "manual_chunk_edit",
                "chunk_id": chunk_id,
                "base_version": base_version,
                "previous_draft_id": str(previous_draft.id) if previous_draft else None,
            },
            editor_notes=f"Book Text manual edit for {chunk_id}.",
        )
        return {
            **_book_text_payload(session, brief, draft=draft),
            "status": "saved",
            "chunk_id": chunk_id,
            "persistence": True,
            "previous_version": base_version,
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters/{chapter_brief_id}/chunks/{chunk_id}/rewrite")
    def rewrite_book_chunk_endpoint(
        request: Request,
        chapter_brief_id: UUID,
        chunk_id: str,
        payload: BookChunkRewriteRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        body, base_version, previous_draft = _current_book_body(
            session,
            brief,
            payload.base_version,
        )
        chunk = chunk_by_id(body, chunk_id)
        if chunk is None:
            raise HTTPException(status_code=404, detail="book chunk not found")
        if payload.mode == "rewrite" and not payload.instruction.strip():
            raise HTTPException(
                status_code=422,
                detail="rewrite mode requires an instruction",
            )
        try:
            result = rewrite_book_chunk(
                config,
                chapter_title=brief.title,
                full_body=body,
                chunk=chunk,
                mode=payload.mode,
                instruction=payload.instruction,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except BookRewriteUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        next_body = replace_chunk(body, chunk_id, result.rewritten_text)
        model_name = config.openai.draft_model or config.openai.extraction_model
        draft = create_chapter_draft_version(
            session,
            brief,
            next_body,
            model_provider="openai",
            model_name=model_name,
            model_metadata={
                "action": "book_chunk_rewrite",
                "mode": payload.mode,
                "chunk_id": chunk_id,
                "base_version": base_version,
                "previous_draft_id": str(previous_draft.id) if previous_draft else None,
            },
            generation_prompt_ref=f"book_text.{payload.mode}.v0.1",
            editor_notes=f"Book Text {payload.mode} rewrite for {chunk_id}.",
        )
        return {
            **_book_text_payload(session, brief, draft=draft),
            "status": "rewritten",
            "chunk_id": chunk_id,
            "mode": payload.mode,
            "rewritten_text": result.rewritten_text,
            "previous_version": base_version,
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters/{chapter_brief_id}/versions/{version_number}/restore")
    def restore_chapter_version(
        request: Request,
        chapter_brief_id: UUID,
        version_number: int,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        target = chapter_draft_by_version(session, brief, version_number)
        if target is None:
            raise HTTPException(status_code=404, detail="chapter draft version not found")
        latest = latest_chapter_draft(session, brief)
        draft = create_chapter_draft_version(
            session,
            brief,
            target.body,
            model_metadata={
                "action": "restore_version",
                "restored_from_version": version_number,
                "base_version": latest.version_number if latest else 0,
                "previous_draft_id": str(latest.id) if latest else None,
            },
            editor_notes=f"Restored from draft version {version_number}.",
        )
        return {
            **_book_text_payload(session, brief, draft=draft),
            "status": "restored",
            "restored_from_version": version_number,
            "previous_version": latest.version_number if latest else 0,
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters/order")
    def reorder_chapters(
        request: Request,
        payload: ChapterOrderRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        chapter_ids = payload.chapter_ids
        if len(chapter_ids) != len(set(chapter_ids)):
            raise HTTPException(status_code=422, detail="chapter order contains duplicates")
        if not chapter_ids:
            raise HTTPException(status_code=422, detail="chapter order is empty")

        briefs = list(
            session.scalars(
                select(ChapterBrief).where(
                    ChapterBrief.project_id == project.id,
                    ChapterBrief.id.in_(chapter_ids),
                )
            )
        )
        briefs_by_id = {brief.id: brief for brief in briefs}
        if len(briefs_by_id) != len(chapter_ids):
            raise HTTPException(status_code=404, detail="chapter not found")

        for index, chapter_id in enumerate(chapter_ids, start=1):
            briefs_by_id[chapter_id].sequence_order = index
        session.flush()
        return {
            "status": "saved",
            "chapters": _chapter_toc_payload(_ordered_chapter_briefs(session, project)),
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters")
    def create_chapter(
        request: Request,
        payload: ChapterCreateRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        title = payload.title.strip()
        subtitle = payload.subtitle.strip() or None
        if not title:
            raise HTTPException(status_code=422, detail="title is required")

        next_order = (
            session.scalar(
                select(func.max(ChapterBrief.sequence_order)).where(
                    ChapterBrief.project_id == project.id
                )
            )
            or 0
        ) + 1
        brief = ChapterBrief(
            project=project,
            title=title,
            subtitle=subtitle,
            slug=_unique_chapter_slug(session, project, title),
            sequence_order=next_order,
            status=ChapterStatus.DRAFT.value,
        )
        session.add(brief)
        session.flush()
        chapters = _chapter_toc_payload(_ordered_chapter_briefs(session, project))
        return {
            "status": "saved",
            "chapter": _chapter_summary(brief),
            "chapters": chapters,
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.patch("/api/chapters/{chapter_brief_id}")
    def update_chapter_metadata(
        request: Request,
        chapter_brief_id: UUID,
        payload: ChapterMetadataRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        title = payload.title.strip()
        subtitle = payload.subtitle.strip() or None
        if not title:
            raise HTTPException(status_code=422, detail="title is required")

        brief.title = title
        brief.subtitle = subtitle
        session.flush()
        return {
            "status": "saved",
            "chapter": _chapter_summary(brief),
            "chapters": _chapter_toc_payload(_ordered_chapter_briefs(session, project)),
            "book_text": _book_text_payload(session, brief),
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.post("/api/chapters/{chapter_brief_id}/status")
    def update_chapter_status(
        request: Request,
        chapter_brief_id: UUID,
        payload: ChapterStatusRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        project = ensure_project(session, config)
        brief = _chapter_brief_or_404(session, project, chapter_brief_id)
        normalized = _normalize_chapter_status(payload.status)
        if payload.status != normalized:
            raise HTTPException(status_code=422, detail="status must be draft or ready")
        brief.status = normalized
        session.flush()
        return {
            "status": "saved",
            "chapter": _chapter_summary(brief),
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.get("/chapters", response_class=HTMLResponse)
    def chapter_board(request: Request, session: Session = Depends(get_session)):
        project = ensure_project(session, config)
        briefs = _ordered_chapter_briefs(session, project)
        return templates.TemplateResponse(
            request,
            "chapter_board.html",
            {
                "project": project,
                "chapters": _chapter_toc_payload(briefs),
                "stats": _stats(session, project),
            },
        )

    @app.get("/context", response_class=HTMLResponse)
    def context_workbench(
        request: Request,
        tab: str = Query(default="meaning"),
        page: int = Query(default=1, ge=1),
        label: str = Query(default=""),
        status: str = Query(default=""),
        session: Session = Depends(get_session),
    ):
        project = ensure_project(session, config)
        active_tab = tab if tab in {"sources", "meaning"} else "meaning"
        labels = _context_labels(session, project)
        normalized_label = label if label in labels else ""
        chunks: list[SourceChunk] = []
        candidates: list[ExtractedCandidate] = []

        if active_tab == "sources":
            source_query = (
                select(SourceChunk)
                .options(
                    selectinload(SourceChunk.source),
                    selectinload(SourceChunk.extracted_candidates),
                )
                .where(SourceChunk.project_id == project.id)
                .order_by(SourceChunk.created_at.desc(), SourceChunk.chunk_index.asc())
            )
            chunks = list(session.scalars(source_query))
            chunks = [
                chunk
                for chunk in chunks
                if _matches_context_filters(
                    _source_label(chunk.source), chunk.status, normalized_label, status
                )
            ]
            chunks.sort(key=lambda chunk: not bool(chunk.extracted_candidates))
            page_items, pagination = _paginate(chunks, page)
        else:
            candidate_query = (
                select(ExtractedCandidate)
                .options(
                    selectinload(ExtractedCandidate.source),
                    selectinload(ExtractedCandidate.source_chunk),
                    selectinload(ExtractedCandidate.promoted_node),
                )
                .where(ExtractedCandidate.project_id == project.id)
                .order_by(
                    ExtractedCandidate.created_at.desc(),
                    ExtractedCandidate.reuse_score.desc(),
                )
            )
            candidates = list(session.scalars(candidate_query))
            candidates = [
                candidate
                for candidate in candidates
                if _matches_context_filters(
                    _source_label(candidate.source),
                    candidate.status,
                    normalized_label,
                    status,
                )
            ]
            page_items, pagination = _paginate(candidates, page)

        return_to = _return_to(request)
        return templates.TemplateResponse(
            request,
            "context_workbench.html",
            {
                "project": project,
                "tab": active_tab,
                "label": normalized_label,
                "status": status,
                "labels": labels,
                "items": page_items,
                "pagination": pagination,
                "return_to": return_to,
                "stats": _context_stats(session, project),
            },
        )

    @app.get("/chapters/{chapter_brief_id}", response_class=HTMLResponse)
    def chapter_editor(
        request: Request,
        chapter_brief_id: UUID,
        session: Session = Depends(get_session),
    ):
        project = ensure_project(session, config)
        brief = session.get(ChapterBrief, chapter_brief_id)
        if brief is None or brief.project_id != project.id:
            raise HTTPException(status_code=404, detail="chapter not found")
        draft = get_or_create_chapter_draft(session, brief)
        return templates.TemplateResponse(
            request,
            "chapter_editor.html",
            {"brief": brief, "draft": draft},
        )

    @app.post("/chapters/{chapter_brief_id}/draft")
    def save_chapter_draft(
        request: Request,
        chapter_brief_id: UUID,
        payload: DraftSaveRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, str | int]:
        project = ensure_project(session, config)
        brief = session.get(ChapterBrief, chapter_brief_id)
        if brief is None or brief.project_id != project.id:
            raise HTTPException(status_code=404, detail="chapter not found")
        draft = autosave_chapter_draft(session, brief, payload.body)
        return {
            "status": "saved",
            "draft_id": str(draft.id),
            "version_number": draft.version_number,
            "updated_at": draft.updated_at.isoformat(),
            "trace_id": getattr(request.state, "trace_id", ""),
        }

    @app.get("/candidates/{candidate_id}", response_class=HTMLResponse)
    def candidate_detail(
        request: Request,
        candidate_id: UUID,
        session: Session = Depends(get_session),
    ):
        candidate = session.get(ExtractedCandidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        briefs = list(
            session.scalars(
                select(ChapterBrief)
                .where(ChapterBrief.project_id == candidate.project_id)
                .order_by(
                    ChapterBrief.sequence_order.is_(None),
                    ChapterBrief.sequence_order.asc(),
                    ChapterBrief.created_at.asc(),
                )
            )
        )
        return templates.TemplateResponse(
            request,
            "candidate_detail.html",
            {"candidate": candidate, "briefs": briefs},
        )

    @app.post("/candidates/{candidate_id}/promote")
    def promote(
        candidate_id: UUID,
        chapter_brief_id: UUID | None = Query(default=None),
        section_key: str = Query(default="field_note"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        promote_candidate(
            session,
            candidate_id,
            reviewer="web",
            chapter_brief_id=chapter_brief_id,
            section_key=section_key,
        )
        return RedirectResponse(f"/candidates/{candidate_id}", status_code=303)

    @app.post("/candidates/{candidate_id}/keep")
    def keep_candidate(
        candidate_id: UUID,
        return_to: str = Query(default="/context?tab=meaning"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        promote_candidate(session, candidate_id, reviewer="web")
        return RedirectResponse(_safe_redirect(return_to), status_code=303)

    @app.post("/candidates/{candidate_id}/reject")
    def reject(
        candidate_id: UUID,
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        reject_candidate(session, candidate_id, reviewer="web")
        return RedirectResponse("/chapters", status_code=303)

    @app.post("/candidates/{candidate_id}/discard")
    def discard_candidate(
        candidate_id: UUID,
        return_to: str = Query(default="/context?tab=meaning"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        reject_candidate(session, candidate_id, reviewer="web")
        return RedirectResponse(_safe_redirect(return_to), status_code=303)

    @app.post("/chunks/{chunk_id}/keep")
    def keep_chunk(
        chunk_id: UUID,
        return_to: str = Query(default="/context?tab=sources"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        keep_source_chunk(session, chunk_id, reviewer="web")
        return RedirectResponse(_safe_redirect(return_to), status_code=303)

    @app.post("/chunks/{chunk_id}/discard")
    def discard_chunk(
        chunk_id: UUID,
        return_to: str = Query(default="/context?tab=sources"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        discard_source_chunk(session, chunk_id, reviewer="web")
        return RedirectResponse(_safe_redirect(return_to), status_code=303)

    @app.get("/sources/{source_id}", response_class=HTMLResponse)
    def source_detail(
        request: Request,
        source_id: UUID,
        session: Session = Depends(get_session),
    ):
        source = session.get(SourceMaterial, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="source not found")
        chunks = list(
            session.scalars(
                select(SourceChunk)
                .where(SourceChunk.source_id == source.id)
                .order_by(SourceChunk.chunk_index.asc())
            )
        )
        return templates.TemplateResponse(
            request,
            "source_detail.html",
            {"source": source, "chunks": chunks},
        )

    return app


def _chapter_brief_or_404(
    session: Session,
    project: Project,
    chapter_brief_id: UUID,
) -> ChapterBrief:
    brief = session.get(ChapterBrief, chapter_brief_id)
    if brief is None or brief.project_id != project.id:
        raise HTTPException(status_code=404, detail="chapter not found")
    return brief


def _ordered_chapter_briefs(session: Session, project: Project) -> list[ChapterBrief]:
    return list(
        session.scalars(
            select(ChapterBrief)
            .where(ChapterBrief.project_id == project.id)
            .order_by(
                ChapterBrief.sequence_order.is_(None),
                ChapterBrief.sequence_order.asc(),
                ChapterBrief.created_at.asc(),
            )
        )
    )


def _unique_chapter_slug(session: Session, project: Project, title: str) -> str:
    base_slug = chapter_slug(title)
    slug = base_slug
    suffix = 2
    while session.scalar(
        select(ChapterBrief.id).where(
            ChapterBrief.project_id == project.id,
            ChapterBrief.slug == slug,
        )
    ):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def _normalize_chapter_status(status: str | None) -> str:
    if status in {
        ChapterStatus.READY.value,
        "accepted",
        "published",
    }:
        return ChapterStatus.READY.value
    return ChapterStatus.DRAFT.value


def _chapter_summary(brief: ChapterBrief) -> dict:
    status = _normalize_chapter_status(brief.status)
    return {
        "id": str(brief.id),
        "title": brief.title,
        "subtitle": brief.subtitle,
        "slug": brief.slug,
        "sequence_order": brief.sequence_order,
        "status": status,
        "status_label": "Visible" if status == ChapterStatus.READY.value else "Draft",
    }


def _chapter_toc_payload(briefs: list[ChapterBrief]) -> list[dict]:
    return [
        {
            **_chapter_summary(brief),
            "toc_number": index,
            "can_move_up": index > 1,
            "can_move_down": index < len(briefs),
        }
        for index, brief in enumerate(briefs, start=1)
    ]


def _current_book_body(
    session: Session,
    brief: ChapterBrief,
    base_version: int | None,
) -> tuple[str, int, object | None]:
    latest = latest_chapter_draft(session, brief)
    latest_version = latest.version_number if latest else 0
    if base_version is not None and base_version != latest_version:
        raise HTTPException(
            status_code=409,
            detail=f"chapter draft changed; latest version is {latest_version}",
        )
    body = latest.body if latest is not None and latest.body.strip() else build_brief_skeleton(brief)
    return body, latest_version, latest


def _book_text_payload(
    session: Session,
    brief: ChapterBrief,
    *,
    draft=None,
) -> dict:
    selected_draft = draft or latest_chapter_draft(session, brief)
    if selected_draft is not None and selected_draft.body.strip():
        body = selected_draft.body
        source = "draft"
        version_number = selected_draft.version_number
        draft_id = str(selected_draft.id)
    else:
        body = build_brief_skeleton(brief)
        source = "brief_skeleton"
        version_number = selected_draft.version_number if selected_draft else 0
        draft_id = str(selected_draft.id) if selected_draft else None

    chunks = [chunk.to_dict() for chunk in split_markdown_chunks(body)]
    versions = [
        {
            "id": str(version.id),
            "version_number": version.version_number,
            "updated_at": version.updated_at.isoformat(),
            "editor_notes": version.editor_notes,
        }
        for version in chapter_draft_versions(session, brief)
    ]
    return {
        "chapter": {
            "id": str(brief.id),
            "title": brief.title,
            "subtitle": brief.subtitle,
            "slug": brief.slug,
            "status": _normalize_chapter_status(brief.status),
        },
        "draft_id": draft_id,
        "version_number": version_number,
        "source": source,
        "body": body,
        "chunks": chunks,
        "versions": versions,
    }


def _compiled_book_chapters(
    session: Session,
    briefs: list[ChapterBrief],
    *,
    include_drafts: bool,
) -> list[dict]:
    chapters: list[dict] = []
    for toc_number, brief in enumerate(briefs, start=1):
        status = _normalize_chapter_status(brief.status)
        if not include_drafts and status != ChapterStatus.READY.value:
            continue
        draft = latest_chapter_draft(session, brief)
        source = "draft" if draft is not None and draft.body.strip() else "brief_skeleton"
        body = draft.body.strip() if source == "draft" else build_brief_skeleton(brief).strip()
        chapters.append(
            {
                **_chapter_summary(brief),
                "toc_number": toc_number,
                "source": source,
                "version_number": draft.version_number if draft else 0,
                "word_count": _word_count(body),
                "body": body,
                "brief_metadata": dict(brief.brief_metadata or {}),
                "intended_page_count": brief.intended_page_count,
                "target_word_count": brief.target_word_count,
            }
        )
    return chapters


def _compiled_book_markdown(
    chapters: list[dict],
    *,
    output_format: str = "raw",
) -> str:
    if output_format == "vivliostyle":
        return "\n\n".join(_vivliostyle_chapter_markdown(chapter) for chapter in chapters).strip()
    return "\n\n".join(str(chapter["body"]).strip() for chapter in chapters).strip()


def _render_chapter_refs(chapters: list[dict]) -> list[dict]:
    return [
        {
            "id": chapter["id"],
            "slug": chapter["slug"],
            "title": chapter["title"],
            "toc_number": chapter["toc_number"],
            "source": chapter["source"],
            "version_number": chapter["version_number"],
            "word_count": chapter["word_count"],
        }
        for chapter in chapters
    ]


def _vivliostyle_chapter_markdown(chapter: dict) -> str:
    title = str(chapter["title"]).strip() or "Untitled Chapter"
    subtitle = str(chapter.get("subtitle") or "").strip()
    body = _strip_leading_chapter_matter(str(chapter["body"]))
    slug = str(chapter.get("slug") or "").strip()
    kicker = _chapter_kicker(chapter)

    lines = [
        f'<section class="chapter-opener opener-title" data-chapter-slug="{escape(slug)}">',
        f'<p class="opener-kicker">{escape(kicker)}</p>',
        f"<h1>{escape(title)}</h1>",
    ]
    if subtitle:
        lines.append(f'<p class="opener-subtitle">{escape(subtitle)}</p>')
    lines.extend(
        [
            f'<p class="opener-running-label">{escape(_chapter_running_label(chapter))}</p>',
            "</section>",
            "",
            '<div class="chapter-body-marker" aria-hidden="true"></div>',
        ]
    )
    if body:
        lines.extend(["", body])
    return "\n".join(lines).strip()


def _chapter_kicker(chapter: dict) -> str:
    try:
        sequence_order = int(chapter.get("sequence_order") or 0)
    except (TypeError, ValueError):
        sequence_order = 0
    if sequence_order == 1:
        return "INTRO"

    try:
        toc_number = int(chapter.get("toc_number") or 0)
    except (TypeError, ValueError):
        toc_number = 0
    return f"FIELD NOTE {(toc_number - 1):02d}" if toc_number else "FIELD NOTE"


def _chapter_running_label(chapter: dict) -> str:
    metadata = dict(chapter.get("brief_metadata") or {})
    form = str(metadata.get("chapter_form") or metadata.get("form") or "").strip()
    if form:
        return form.upper()
    return "O'AHU A.I. FIELD NOTES"


def _strip_leading_chapter_matter(body: str) -> str:
    lines = body.strip().splitlines()
    if lines and re.match(r"^\s*#\s+", lines[0]):
        lines = _strip_leading_blank_lines(lines[1:])
        if lines and _is_leading_subtitle_line(lines[0]):
            lines = _strip_leading_blank_lines(lines[1:])
    return "\n".join(lines).strip()


def _strip_leading_blank_lines(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    return lines


def _is_leading_subtitle_line(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(r'^<p\s+class=["\']chapter-subtitle["\'][^>]*>.*</p>$', stripped)
        or re.match(r"^\*[^*].*[^*]\*$", stripped)
    )


def _word_count(text: str) -> int:
    return len(text.split())


def _page_count_response(
    session: Session,
    chapters: list[dict],
    *,
    include_drafts: bool,
) -> dict:
    rows = [_page_count_row(session, chapter) for chapter in chapters]
    return {
        "profile": MIXAM_PAGE_COUNT_PROFILE,
        "include_drafts": include_drafts,
        "chapter_count": len(rows),
        "total_pages": sum(row["page_count"] or 0 for row in rows if row["page_status"] == "fresh"),
        "chapters": rows,
    }


def _log_page_count_response(
    event: str,
    response: dict,
    *,
    trace_id: str,
    project_slug: str,
) -> None:
    rows = response["chapters"]
    status_counts = {
        status: sum(1 for row in rows if row["page_status"] == status)
        for status in ["fresh", "stale", "missing", "failed"]
    }
    log = logger.warning if status_counts["failed"] else logger.info
    log(
        "%s trace_id=%s project=%s include_drafts=%s chapter_count=%s "
        "total_pages=%s fresh=%s stale=%s missing=%s failed=%s",
        event,
        trace_id,
        project_slug,
        response["include_drafts"],
        response["chapter_count"],
        response["total_pages"],
        status_counts["fresh"],
        status_counts["stale"],
        status_counts["missing"],
        status_counts["failed"],
    )
    for row in rows:
        if row["page_status"] in {"failed", "stale", "missing"}:
            log_row = logger.warning if row["page_status"] == "failed" else logger.info
            log_row(
                "page_counts.row trace_id=%s project=%s chapter=%s slug=%s "
                "status=%s page_count=%s input_hash=%s rendered_at=%s "
                "returncode=%s output_path=%s error=%r logs_excerpt=%r",
                trace_id,
                project_slug,
                row["id"],
                row["slug"],
                row["page_status"],
                row["page_count"],
                row["input_hash"],
                row["rendered_at"],
                row["returncode"],
                row["output_path"],
                row["error"],
                row["logs_excerpt"],
            )


def _page_count_row(session: Session, chapter: dict) -> dict:
    input_hash = _page_count_input_hash(chapter)
    record = _latest_page_count_record(session, UUID(str(chapter["id"])))
    base = {
        "id": chapter["id"],
        "title": chapter["title"],
        "subtitle": chapter["subtitle"],
        "slug": chapter["slug"],
        "status": chapter["status"],
        "status_label": chapter["status_label"],
        "toc_number": chapter["toc_number"],
        "input_hash": input_hash,
        "page_count": None,
        "page_status": "missing",
        "stale": False,
        "rendered_at": None,
        "output_path": None,
        "error": None,
        "returncode": None,
        "renderer_elapsed_ms": None,
        "logs_excerpt": None,
    }
    if record is None:
        return base

    metadata = dict(record.render_metadata or {})
    cached_hash = metadata.get("input_hash")
    page_count = metadata.get("page_count")
    stale = cached_hash != input_hash
    page_status = "failed" if record.status == RenderStatus.FAILED.value else "fresh"
    if stale and page_status == "fresh":
        page_status = "stale"
    return {
        **base,
        "page_count": page_count if isinstance(page_count, int) else None,
        "page_status": page_status,
        "stale": stale,
        "rendered_at": record.rendered_at.isoformat() if record.rendered_at else None,
        "output_path": record.output_path,
        "error": metadata.get("error"),
        "returncode": metadata.get("returncode"),
        "renderer_elapsed_ms": metadata.get("elapsed_ms"),
        "logs_excerpt": metadata.get("logs_excerpt"),
    }


def _latest_page_count_record(
    session: Session,
    chapter_brief_id: UUID,
) -> RenderedOutput | None:
    records = list(
        session.scalars(
            select(RenderedOutput)
            .where(
                RenderedOutput.chapter_brief_id == chapter_brief_id,
                RenderedOutput.output_type == PAGE_COUNT_OUTPUT_TYPE,
            )
            .order_by(RenderedOutput.created_at.desc())
        )
    )
    for record in records:
        metadata = dict(record.render_metadata or {})
        if metadata.get("profile_id") == MIXAM_PAGE_COUNT_PROFILE["id"]:
            return record
    return None


def _latest_final_pdf_record(
    session: Session,
    project: Project,
    *,
    succeeded_only: bool = False,
) -> RenderedOutput | None:
    statement = (
        select(RenderedOutput)
        .where(
            RenderedOutput.project_id == project.id,
            RenderedOutput.output_type == render_output_type(FINAL_PDF_PROFILE),
        )
        .order_by(RenderedOutput.created_at.desc())
    )
    records = list(session.scalars(statement))
    for record in records:
        metadata = dict(record.render_metadata or {})
        if metadata.get("profile") != FINAL_PDF_PROFILE:
            continue
        if metadata.get("source") != "database":
            continue
        if succeeded_only and record.status != RenderStatus.SUCCEEDED.value:
            continue
        return record
    return None


def _final_pdf_payload(root: Path, record: RenderedOutput | None) -> dict:
    if record is None:
        output_path = str(print_output_path())
        return {
            "profile": FINAL_PDF_PROFILE,
            "status": "missing",
            "output_path": output_path,
            "download_url": None,
            "rendered_at": None,
            "returncode": None,
            "error": None,
            "logs_excerpt": None,
            "pdf_standard_target": "Mixam press-ready PDF",
            "source": "database",
            "generated_markdown_path": None,
            "chapter_count": 0,
            "commands": [],
            "file_exists": False,
        }

    metadata = dict(record.render_metadata or {})
    path = _safe_dist_output_path(root, record.output_path)
    file_exists = bool(path and path.exists())
    succeeded = record.status == RenderStatus.SUCCEEDED.value
    return {
        "id": str(record.id),
        "profile": metadata.get("profile") or FINAL_PDF_PROFILE,
        "status": record.status,
        "output_path": record.output_path,
        "download_url": "/api/book-text/final-pdf/file" if succeeded and file_exists else None,
        "rendered_at": record.rendered_at.isoformat() if record.rendered_at else None,
        "returncode": metadata.get("returncode"),
        "error": metadata.get("error"),
        "logs_excerpt": _text_tail(record.build_logs or metadata.get("error")),
        "pdf_standard_target": metadata.get("pdf_standard_target", "Mixam press-ready PDF"),
        "source": metadata.get("source", "database"),
        "generated_markdown_path": metadata.get("generated_markdown_path"),
        "chapter_count": metadata.get("chapter_count"),
        "commands": metadata.get("commands", []),
        "file_exists": file_exists,
    }


def _safe_dist_output_path(root: Path, output_path: str | Path) -> Path | None:
    dist_root = (root / "dist").resolve()
    candidate = Path(output_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(dist_root):
        return None
    return resolved


def _render_chapter_page_count(
    root: Path,
    session: Session,
    project: Project,
    chapter: dict,
    *,
    trace_id: str = "",
) -> RenderedOutput:
    output_dir = root / "dist" / "page-counts" / str(chapter["slug"])
    output_dir.mkdir(parents=True, exist_ok=True)
    input_hash = _page_count_input_hash(chapter)
    markdown_path = output_dir / f"{input_hash[:12]}.md"
    css_path = output_dir / "mixam-page-count.css"
    pdf_path = output_dir / f"{input_hash[:12]}.pdf"
    markdown_path.write_text(_vivliostyle_chapter_markdown(chapter) + "\n", encoding="utf-8")
    css_path.write_text(_mixam_page_count_css(root), encoding="utf-8")
    vivliostyle_bin = root / "node_modules" / ".bin" / "vivliostyle"

    command = [
        str(vivliostyle_bin),
        "build",
        markdown_path.name,
        "--theme",
        css_path.name,
        "--size",
        str(MIXAM_PAGE_COUNT_PROFILE["trim_size"]),
        "--bleed",
        str(MIXAM_PAGE_COUNT_PROFILE["bleed"]),
        "--crop-marks",
        "--output",
        pdf_path.name,
        "--format",
        "pdf",
    ]
    if MIXAM_PAGE_COUNT_PROFILE["press_ready"]:
        command.insert(command.index("--bleed"), "--press-ready")
    command_json = json.dumps(command)
    relative_markdown_path = str(markdown_path.relative_to(root))
    relative_css_path = str(css_path.relative_to(root))
    relative_pdf_path = str(pdf_path.relative_to(root))
    metadata = {
        "profile_id": MIXAM_PAGE_COUNT_PROFILE["id"],
        "profile": MIXAM_PAGE_COUNT_PROFILE,
        "render_mode": "pagination_only",
        "press_ready_skipped": not MIXAM_PAGE_COUNT_PROFILE["press_ready"],
        "input_hash": input_hash,
        "chapter_id": str(chapter["id"]),
        "chapter_slug": chapter["slug"],
        "version_number": chapter["version_number"],
        "source": chapter["source"],
        "command": command,
        "returncode": None,
        "cwd": str(output_dir),
        "markdown_path": relative_markdown_path,
        "css_path": relative_css_path,
        "output_path": relative_pdf_path,
    }
    logger.info(
        "page_count.chapter.start trace_id=%s project=%s chapter=%s slug=%s "
        "toc_number=%s source=%s version=%s word_count=%s input_hash=%s "
        "markdown_path=%s css_path=%s output_path=%s cwd=%s command=%s",
        trace_id,
        project.slug,
        chapter["id"],
        chapter["slug"],
        chapter["toc_number"],
        chapter["source"],
        chapter["version_number"],
        chapter["word_count"],
        input_hash,
        relative_markdown_path,
        relative_css_path,
        relative_pdf_path,
        output_dir,
        command_json,
    )
    render_started = perf_counter()
    try:
        result = subprocess.run(command, cwd=output_dir, check=False, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        logs = _clean_log_text(str(exc))
        status = RenderStatus.FAILED.value
        metadata["error"] = _text_tail(logs) or "Vivliostyle build could not be started"
        metadata["logs_excerpt"] = _text_tail(logs)
        metadata["elapsed_ms"] = round((perf_counter() - render_started) * 1000, 2)
        logger.exception(
            "page_count.chapter.exception trace_id=%s project=%s chapter=%s slug=%s "
            "elapsed_ms=%s command=%s error=%r",
            trace_id,
            project.slug,
            chapter["id"],
            chapter["slug"],
            metadata["elapsed_ms"],
            command_json,
            metadata["error"],
        )
    else:
        logs = _clean_log_text("\n".join(part for part in [result.stdout, result.stderr] if part))
        stdout_tail = _text_tail(result.stdout)
        stderr_tail = _text_tail(result.stderr)
        logs_tail = _text_tail(logs)
        metadata["returncode"] = result.returncode
        metadata["elapsed_ms"] = round((perf_counter() - render_started) * 1000, 2)
        metadata["stdout_tail"] = stdout_tail
        metadata["stderr_tail"] = stderr_tail
        metadata["logs_excerpt"] = logs_tail
        status = RenderStatus.SUCCEEDED.value
        logger.info(
            "page_count.vivliostyle.complete trace_id=%s project=%s chapter=%s slug=%s "
            "returncode=%s elapsed_ms=%s stdout_tail=%r stderr_tail=%r",
            trace_id,
            project.slug,
            chapter["id"],
            chapter["slug"],
            result.returncode,
            metadata["elapsed_ms"],
            stdout_tail,
            stderr_tail,
        )
        if result.returncode == 0:
            try:
                metadata["page_count"] = _count_pdf_pages(pdf_path)
            except Exception as exc:  # pragma: no cover - defensive around external PDFs
                status = RenderStatus.FAILED.value
                metadata["error"] = str(exc)
                logger.exception(
                    "page_count.count.exception trace_id=%s project=%s chapter=%s "
                    "slug=%s output_path=%s error=%r",
                    trace_id,
                    project.slug,
                    chapter["id"],
                    chapter["slug"],
                    relative_pdf_path,
                    metadata["error"],
                )
            else:
                logger.info(
                    "page_count.count.complete trace_id=%s project=%s chapter=%s "
                    "slug=%s output_path=%s page_count=%s",
                    trace_id,
                    project.slug,
                    chapter["id"],
                    chapter["slug"],
                    relative_pdf_path,
                    metadata["page_count"],
                )
        else:
            status = RenderStatus.FAILED.value
            metadata["error"] = logs_tail or "Vivliostyle build failed"
            logger.warning(
                "page_count.vivliostyle.failed trace_id=%s project=%s chapter=%s slug=%s "
                "returncode=%s elapsed_ms=%s command=%s stdout_tail=%r stderr_tail=%r",
                trace_id,
                project.slug,
                chapter["id"],
                chapter["slug"],
                result.returncode,
                metadata["elapsed_ms"],
                command_json,
                stdout_tail,
                stderr_tail,
            )

    record = RenderedOutput(
        project=project,
        chapter_brief_id=UUID(str(chapter["id"])),
        output_type=PAGE_COUNT_OUTPUT_TYPE,
        renderer="Vivliostyle",
        config_path=MIXAM_PAGE_COUNT_PROFILE["id"],
        output_path=relative_pdf_path,
        build_logs=logs[-20000:],
        status=status,
        rendered_at=utc_now(),
        render_metadata=metadata,
    )
    session.add(record)
    session.flush()
    record_log = logger.warning if status == RenderStatus.FAILED.value else logger.info
    record_log(
        "page_count.record.saved trace_id=%s project=%s chapter=%s slug=%s "
        "status=%s page_count=%s returncode=%s elapsed_ms=%s output_path=%s error=%r",
        trace_id,
        project.slug,
        chapter["id"],
        chapter["slug"],
        status,
        metadata.get("page_count"),
        metadata.get("returncode"),
        metadata.get("elapsed_ms"),
        relative_pdf_path,
        metadata.get("error"),
    )
    return record


def _page_count_input_hash(chapter: dict) -> str:
    payload = {
        "profile": MIXAM_PAGE_COUNT_PROFILE,
        "markdown": _vivliostyle_chapter_markdown(chapter),
        "version_number": chapter.get("version_number"),
        "source": chapter.get("source"),
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _mixam_page_count_css(root: Path) -> str:
    css = MIXAM_PAGE_COUNT_PROFILE["css"]
    book_css_uri = (root / "styles" / "book.css").resolve().as_uri()
    return (
        f'@import url("{book_css_uri}");\n\n'
        "@page {\n"
        f"  size: {MIXAM_PAGE_COUNT_PROFILE['trim_size']};\n"
        f"  margin: {css['top']} {css['outside']} {css['bottom']} {css['inside']};\n"
        "}\n\n"
        "@page :left {\n"
        f"  margin-left: {css['outside']};\n"
        f"  margin-right: {css['inside']};\n"
        "}\n\n"
        "@page :right {\n"
        f"  margin-left: {css['inside']};\n"
        f"  margin-right: {css['outside']};\n"
        "}\n\n"
        "body > h1:first-child {\n"
        "  page-break-before: auto;\n"
        "}\n"
    )


def _count_pdf_pages(path: Path) -> int:
    errors: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        errors.append("pypdf unavailable")
    else:
        try:
            count = len(PdfReader(str(path)).pages)
        except Exception as exc:  # pragma: no cover - depends on external PDF parser
            errors.append(f"pypdf failed: {exc}")
        else:
            if count > 0:
                return count
            errors.append("pypdf returned 0 pages")

    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"pdfinfo unavailable: {exc}")
    else:
        output = _clean_log_text("\n".join(part for part in [result.stdout, result.stderr] if part))
        match = re.search(r"^Pages:\s*(\d+)\s*$", output, flags=re.MULTILINE)
        if result.returncode == 0 and match:
            count = int(match.group(1))
            if count > 0:
                return count
            errors.append("pdfinfo returned 0 pages")
        else:
            errors.append(
                f"pdfinfo failed returncode={result.returncode} output={_text_tail(output, 500)!r}"
            )

    try:
        data = path.read_bytes()
    except OSError as exc:
        errors.append(f"raw scan failed: {exc}")
    else:
        count = len(re.findall(rb"/Type\s*/Page\b", data))
        if count > 0:
            return count
        errors.append("raw scan found 0 /Page objects")

    raise ValueError(f"could not count pages in {path}; " + "; ".join(errors))


def _stats(session: Session, project: Project) -> dict[str, int]:
    def count(model, *criteria) -> int:
        return int(
            session.scalar(
                select(func.count(model.id)).where(model.project_id == project.id, *criteria)
            )
            or 0
        )

    return {
        "sources": count(SourceMaterial),
        "chunks": count(SourceChunk),
        "ready_chunks": count(SourceChunk, SourceChunk.status == "ready"),
        "blocked_chunks": count(SourceChunk, SourceChunk.status.in_(["blocked", "needs_ocr"])),
        "needs_review": count(
            ExtractedCandidate,
            ExtractedCandidate.status == CandidateStatus.NEEDS_REVIEW.value,
        ),
        "promoted_candidates": count(
            ExtractedCandidate,
            ExtractedCandidate.status == CandidateStatus.PROMOTED.value,
        ),
        "knowledge_nodes": count(KnowledgeNode),
        "review_decisions": count(ReviewDecision),
    }


def _source_label(source: SourceMaterial | None) -> str:
    if source is None:
        return ""
    return str(source.source_metadata.get("context_label") or "unlabeled")


def _matches_context_filters(
    label: str,
    status: str,
    wanted_label: str,
    wanted_status: str,
) -> bool:
    if wanted_label and label != wanted_label:
        return False
    if wanted_status and status != wanted_status:
        return False
    return True


def _context_labels(session: Session, project: Project) -> list[str]:
    sources = session.scalars(
        select(SourceMaterial).where(SourceMaterial.project_id == project.id)
    )
    labels = {
        _source_label(source)
        for source in sources
        if source.source_metadata.get("context_label") is not None
    }
    return sorted(labels)


def _context_stats(session: Session, project: Project) -> dict[str, int]:
    return {
        "source_chunks": int(
            session.scalar(
                select(func.count(SourceChunk.id)).where(
                    SourceChunk.project_id == project.id
                )
            )
            or 0
        ),
        "discarded_chunks": int(
            session.scalar(
                select(func.count(SourceChunk.id)).where(
                    SourceChunk.project_id == project.id,
                    SourceChunk.status == "discarded",
                )
            )
            or 0
        ),
        "meaning_cards": int(
            session.scalar(
                select(func.count(ExtractedCandidate.id)).where(
                    ExtractedCandidate.project_id == project.id
                )
            )
            or 0
        ),
        "needs_review": int(
            session.scalar(
                select(func.count(ExtractedCandidate.id)).where(
                    ExtractedCandidate.project_id == project.id,
                    ExtractedCandidate.status == CandidateStatus.NEEDS_REVIEW.value,
                )
            )
            or 0
        ),
    }


def _paginate(items: list, page: int, per_page: int = CONTEXT_PAGE_SIZE) -> tuple[list, dict]:
    total = len(items)
    page_count = max(1, (total + per_page - 1) // per_page)
    current_page = min(max(page, 1), page_count)
    start = (current_page - 1) * per_page
    return (
        items[start : start + per_page],
        {
            "page": current_page,
            "page_count": page_count,
            "per_page": per_page,
            "total": total,
            "has_previous": current_page > 1,
            "has_next": current_page < page_count,
            "previous_page": current_page - 1,
            "next_page": current_page + 1,
        },
    )


def _return_to(request: Request) -> str:
    query = str(request.url.query)
    return f"{request.url.path}?{query}" if query else request.url.path


def _safe_redirect(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        return "/context"
    return path
