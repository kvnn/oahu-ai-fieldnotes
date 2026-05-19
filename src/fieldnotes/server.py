"""FastAPI review board for the Field Notes workflow."""

from __future__ import annotations

import logging
import re
from html import escape
from pathlib import Path
from time import perf_counter
from uuid import UUID
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
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
    ReviewDecision,
    SourceChunk,
    SourceMaterial,
)
from fieldnotes.db.session import make_engine, make_session_factory
from fieldnotes.review import (
    discard_source_chunk,
    keep_source_chunk,
    promote_candidate,
    reject_candidate,
)
from fieldnotes.workflow import ensure_project


PACKAGE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
logger = logging.getLogger("fieldnotes.server")
CONTEXT_PAGE_SIZE = 12
CHAINLIT_PATH = "/chainlit"
CHAINLIT_TARGET = PACKAGE_DIR / "chat_app.py"


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
        logger.info(
            "request.start trace_id=%s method=%s path=%s client=%s user_agent=%r",
            trace_id,
            request.method,
            request.url.path,
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
        logger.info(
            "request.complete trace_id=%s method=%s path=%s status_code=%s "
            "elapsed_ms=%.2f",
            trace_id,
            request.method,
            request.url.path,
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


def _vivliostyle_chapter_markdown(chapter: dict) -> str:
    title = str(chapter["title"]).strip() or "Untitled Chapter"
    subtitle = str(chapter.get("subtitle") or "").strip()
    body = _strip_leading_chapter_matter(str(chapter["body"]))

    lines = [f"# {title}"]
    if subtitle:
        lines.extend(["", f'<p class="chapter-subtitle">{escape(subtitle)}</p>'])
    if body:
        lines.extend(["", body])
    return "\n".join(lines).strip()


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
