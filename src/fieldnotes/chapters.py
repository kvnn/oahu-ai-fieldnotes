"""Chapter concept review helpers."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fieldnotes.db.models import (
    AgentRun,
    AgentRunStatus,
    ChapterBrief,
    ChapterDraft,
    ChapterStatus,
    DraftStatus,
    Project,
    ReviewDecision,
    ReviewDecisionType,
    ReviewTargetType,
    utc_now,
)
from fieldnotes.workflow import first_volume


def chapter_slug(title: str) -> str:
    """Create a stable slug for agent-authored chapter candidates."""

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled-chapter"


def save_chapter_candidate(
    session: Session,
    project: Project,
    *,
    title: str,
    subtitle: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    reviewer: str = "codex",
    source: str = "conversation",
) -> ChapterBrief:
    """Create or update a proposed chapter brief from an agent-facing save action."""

    brief_slug = slug or chapter_slug(title)
    volume = first_volume(session, project)
    brief = session.scalar(
        select(ChapterBrief).where(
            ChapterBrief.project_id == project.id,
            ChapterBrief.slug == brief_slug,
        )
    )
    if brief is None:
        brief = ChapterBrief(
            project=project,
            volume=volume,
            title=title,
            subtitle=subtitle,
            slug=brief_slug,
            status=ChapterStatus.DRAFT.value,
        )
        session.add(brief)
        action = "create"
    else:
        brief.title = title
        brief.subtitle = subtitle
        if volume is not None and brief.volume is None:
            brief.volume = volume
        action = "update"

    metadata = dict(brief.brief_metadata or {})
    metadata["description"] = description
    metadata["saved_by"] = reviewer
    metadata["source"] = source
    brief.brief_metadata = metadata
    session.flush()

    now = utc_now()
    session.add(
        AgentRun(
            project=project,
            run_type="chapter_candidate_save",
            agent_name=reviewer,
            tool_name="fieldnotes chapter save-candidate",
            prompt=None,
            input_refs={
                "title": title,
                "subtitle": subtitle,
                "description": description,
                "slug": brief_slug,
                "source": source,
            },
            output_refs={
                "chapter_brief_id": str(brief.id),
                "chapter_brief_slug": brief.slug,
                "action": action,
            },
            status=AgentRunStatus.SUCCEEDED.value,
            started_at=now,
            completed_at=now,
            run_metadata={"action": "save_chapter_candidate"},
        )
    )
    session.flush()
    return brief


def latest_chapter_draft(session: Session, brief: ChapterBrief) -> ChapterDraft | None:
    return session.scalar(
        select(ChapterDraft)
        .where(ChapterDraft.chapter_brief_id == brief.id)
        .order_by(ChapterDraft.version_number.desc())
        .limit(1)
    )


def chapter_draft_by_version(
    session: Session,
    brief: ChapterBrief,
    version_number: int,
) -> ChapterDraft | None:
    return session.scalar(
        select(ChapterDraft)
        .where(
            ChapterDraft.chapter_brief_id == brief.id,
            ChapterDraft.version_number == version_number,
        )
        .limit(1)
    )


def chapter_draft_versions(session: Session, brief: ChapterBrief) -> list[ChapterDraft]:
    return list(
        session.scalars(
            select(ChapterDraft)
            .where(ChapterDraft.chapter_brief_id == brief.id)
            .order_by(ChapterDraft.version_number.desc())
        )
    )


def get_or_create_chapter_draft(
    session: Session,
    brief: ChapterBrief,
) -> ChapterDraft:
    draft = latest_chapter_draft(session, brief)
    if draft is not None:
        return draft

    draft = ChapterDraft(
        chapter_brief=brief,
        version_number=1,
        body_format="markdown",
        body="",
        status=DraftStatus.DRAFT.value,
        editor_notes="Created from chapter editor autosave surface.",
    )
    session.add(draft)
    session.flush()
    return draft


def create_chapter_draft_version(
    session: Session,
    brief: ChapterBrief,
    body: str,
    *,
    model_provider: str | None = None,
    model_name: str | None = None,
    model_metadata: dict | None = None,
    generation_prompt_ref: str | None = None,
    editor_notes: str | None = None,
) -> ChapterDraft:
    latest_number = (
        session.scalar(
            select(func.max(ChapterDraft.version_number)).where(
                ChapterDraft.chapter_brief_id == brief.id
            )
        )
        or 0
    )
    draft = ChapterDraft(
        chapter_brief=brief,
        version_number=int(latest_number) + 1,
        body_format="markdown",
        body=body,
        model_provider=model_provider,
        model_name=model_name,
        model_metadata=model_metadata or {},
        generation_prompt_ref=generation_prompt_ref,
        status=DraftStatus.DRAFT.value,
        editor_notes=editor_notes,
    )
    session.add(draft)
    session.flush()
    return draft


def autosave_chapter_draft(
    session: Session,
    brief: ChapterBrief,
    body: str,
) -> ChapterDraft:
    draft = get_or_create_chapter_draft(session, brief)
    draft.body = body
    draft.status = DraftStatus.DRAFT.value
    session.flush()
    return draft


def approve_chapter_brief(
    session: Session,
    project: Project,
    slug: str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
) -> ChapterBrief:
    brief = session.scalar(
        select(ChapterBrief).where(
            ChapterBrief.project_id == project.id,
            ChapterBrief.slug == slug,
        )
    )
    if brief is None:
        raise ValueError(f"unknown chapter brief: {slug}")

    brief.status = ChapterStatus.READY.value
    session.add(
        ReviewDecision(
            project_id=project.id,
            decision_type=ReviewDecisionType.PROMOTE.value,
            target_type=ReviewTargetType.CHAPTER_BRIEF.value,
            target_id=brief.id,
            decision=ChapterStatus.READY.value,
            reviewer=reviewer,
            rationale=rationale,
            evidence={
                "chapter_brief_id": str(brief.id),
                "chapter_brief_slug": brief.slug,
                "title": brief.title,
            },
            decision_metadata={"action": "approve_chapter_concept"},
        )
    )
    session.flush()
    return brief


def approve_chapter_brief_by_id(
    session: Session,
    chapter_brief_id: UUID | str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
) -> ChapterBrief:
    brief_id = chapter_brief_id if isinstance(chapter_brief_id, UUID) else UUID(str(chapter_brief_id))
    brief = session.get(ChapterBrief, brief_id)
    if brief is None:
        raise ValueError(f"unknown chapter brief: {chapter_brief_id}")
    project = session.get(Project, brief.project_id)
    if project is None:
        raise ValueError(f"chapter brief has unknown project: {brief.project_id}")
    return approve_chapter_brief(
        session,
        project,
        brief.slug,
        reviewer=reviewer,
        rationale=rationale,
    )
