"""Shared workflow helpers for CLI and server entry points."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldnotes.config import FieldnotesConfig
from fieldnotes.db.models import BookVolume, Project


def _title_from_slug(slug: str) -> str:
    if slug == "oahu-ai-field-notes-vol-1":
        return "O‘ahu A.I. Field Notes Vol. 1"
    return slug.replace("-", " ").title()


def ensure_project(session: Session, config: FieldnotesConfig) -> Project:
    project = session.scalar(select(Project).where(Project.slug == config.project_slug))
    if project is not None:
        return project

    project = Project(
        name=_title_from_slug(config.project_slug),
        slug=config.project_slug,
        description=(
            "Agent-driven, source-grounded publishing project for turning messy "
            "work into chapter-ready field notes."
        ),
        project_metadata={
            "vivliostyle_config": str(config.vivliostyle_config),
            "curated_assets_dir": str(config.curated_assets_dir),
        },
    )
    session.add(project)
    session.flush()

    session.add(
        BookVolume(
            project=project,
            title="O‘ahu A.I. Field Notes",
            subtitle="Vol. 1",
            slug="vol-1",
            trim_size='5.5" x 8.5"',
            page_size='5.5" x 8.5"',
            binding_type="perfect_bound",
            printer_target="Mixam perfect bound",
        )
    )
    session.flush()
    return project


def first_volume(session: Session, project: Project) -> BookVolume | None:
    return session.scalar(
        select(BookVolume)
        .where(BookVolume.project_id == project.id)
        .order_by(BookVolume.created_at.asc())
        .limit(1)
    )
