"""FastAPI review board for the Field Notes workflow."""

from __future__ import annotations

import logging
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

from fieldnotes.chapters import autosave_chapter_draft, get_or_create_chapter_draft
from fieldnotes.config import load_config
from fieldnotes.db.models import (
    CandidateStatus,
    ChapterBrief,
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


class DraftSaveRequest(BaseModel):
    body: str = ""


def _configure_tracing_logger() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)


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

    @app.get("/chapters", response_class=HTMLResponse)
    def chapter_board(request: Request, session: Session = Depends(get_session)):
        project = ensure_project(session, config)
        briefs = list(
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
        candidates = list(
            session.scalars(
                select(ExtractedCandidate)
                .where(
                    ExtractedCandidate.project_id == project.id,
                    ExtractedCandidate.status == CandidateStatus.NEEDS_REVIEW.value,
                )
                .order_by(
                    ExtractedCandidate.reuse_score.desc(),
                    ExtractedCandidate.confidence_score.desc(),
                    ExtractedCandidate.created_at.asc(),
                )
                .limit(20)
            )
        )
        return templates.TemplateResponse(
            request,
            "chapter_board.html",
            {
                "project": project,
                "chapter_slots": _chapter_slots(briefs),
                "candidates": candidates,
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
                .options(selectinload(SourceChunk.source))
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


def _chapter_slots(briefs: list[ChapterBrief]) -> list[dict]:
    slots: list[dict] = []
    briefs_by_order = {
        brief.sequence_order: brief for brief in briefs if brief.sequence_order is not None
    }
    unordered = [brief for brief in briefs if brief.sequence_order is None]

    for slot in range(1, 9):
        brief = briefs_by_order.get(slot)
        if brief is None and unordered:
            brief = unordered.pop(0)
        slots.append({"slot": slot, "brief": brief})
    return slots
