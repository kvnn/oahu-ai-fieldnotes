"""Command line tools for the Field Notes publishing workflow."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from fieldnotes.chapters import (
    approve_chapter_brief,
    approve_chapter_brief_by_id,
    save_chapter_candidate,
)
from fieldnotes.config import DEFAULT_CONFIG_PATH, load_config
from fieldnotes.db.models import (
    Base,
    RenderOutputType,
    RenderStatus,
    RenderedOutput,
    utc_now,
)
from fieldnotes.db.seed import seed_demo
from fieldnotes.db.session import make_engine, make_session_factory, session_scope
from fieldnotes.extraction import run_extraction
from fieldnotes.ingest import ingest_sources
from fieldnotes.review import link_candidate_to_chapter, promote_candidate, reject_candidate
from fieldnotes.workflow import ensure_project, first_volume


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to fieldnotes.config.toml.",
    )


def _session_factory(config_path: str):
    config = load_config(config_path)
    engine = make_engine(config.database_url)
    return config, engine, make_session_factory(engine)


def init_db(args: argparse.Namespace) -> None:
    config, engine, _ = _session_factory(args.config)
    Base.metadata.create_all(engine)
    print(f"initialized database for {config.project_slug}")


def seed_db(args: argparse.Namespace) -> None:
    _, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        project_id = seed_demo(session)
    print(f"seeded project {project_id}")


def ingest(args: argparse.Namespace) -> None:
    config, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        project = ensure_project(session, config)
        stats = ingest_sources(session, config, project, run_ocr=not args.skip_ocr)
    print(
        "ingested "
        f"{stats.sources_seen} sources, "
        f"{stats.chunks_created} chunks created, "
        f"{stats.chunks_updated} chunks updated, "
        f"{stats.blocked_images} image chunks awaiting OCR"
    )
    if stats.errors:
        print("errors:")
        for error in stats.errors:
            print(f"- {error}")


def extract(args: argparse.Namespace) -> None:
    config, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        project = ensure_project(session, config)
        run = run_extraction(
            session,
            config,
            project,
            provider=args.provider,
            limit=args.limit,
            include_existing=args.include_existing,
        )
        run_id = run.id
        chunks_count = run.chunks_count
        candidates_count = run.candidates_count
        status = run.status
    print(
        f"extraction run {run_id} {status}: "
        f"{chunks_count} chunks, {candidates_count} candidates"
    )


def promote(args: argparse.Namespace) -> None:
    _, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        node = promote_candidate(
            session,
            args.candidate_id,
            reviewer=args.reviewer,
            chapter_brief_id=args.chapter_brief_id,
            rationale=args.rationale,
            section_key=args.section_key,
        )
        node_id = node.id
        title = node.title
    print(f"promoted candidate to knowledge node {node_id}: {title}")


def reject(args: argparse.Namespace) -> None:
    _, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        candidate = reject_candidate(
            session,
            args.candidate_id,
            reviewer=args.reviewer,
            rationale=args.rationale,
        )
        candidate_id = candidate.id
    print(f"rejected candidate {candidate_id}")


def link(args: argparse.Namespace) -> None:
    _, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        link_record = link_candidate_to_chapter(
            session,
            args.candidate_id,
            args.chapter_brief_id,
            reviewer=args.reviewer,
            rationale=args.rationale,
            section_key=args.section_key,
        )
        link_id = link_record.id
    print(f"linked promoted candidate to chapter brief node {link_id}")


def approve_chapter(args: argparse.Namespace) -> None:
    config, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        project = ensure_project(session, config)
        if args.chapter_brief_id:
            brief = approve_chapter_brief_by_id(
                session,
                args.chapter_brief_id,
                reviewer=args.reviewer,
                rationale=args.rationale,
            )
        else:
            brief = approve_chapter_brief(
                session,
                project,
                args.slug,
                reviewer=args.reviewer,
                rationale=args.rationale,
            )
        brief_id = brief.id
        title = brief.title
    print(f"approved chapter concept {brief_id}: {title}")


def save_chapter(args: argparse.Namespace) -> None:
    config, _, session_factory = _session_factory(args.config)
    with session_scope(session_factory) as session:
        project = ensure_project(session, config)
        brief = save_chapter_candidate(
            session,
            project,
            title=args.title,
            subtitle=args.subtitle,
            description=args.description,
            slug=args.slug,
            reviewer=args.reviewer,
            source=args.source,
        )
        brief_id = brief.id
        slug = brief.slug
        title = brief.title
    print(f"saved chapter candidate {brief_id} ({slug}): {title}")


def render(args: argparse.Namespace) -> None:
    config, _, session_factory = _session_factory(args.config)
    command = ["npm", "run", "build"]
    result = subprocess.run(command, cwd=config.root, check=False, capture_output=True, text=True)
    logs = "\n".join(part for part in [result.stdout, result.stderr] if part)

    output_path = Path("dist/oahu-ai-field-notes.pdf")
    with session_scope(session_factory) as session:
        project = ensure_project(session, config)
        volume = first_volume(session, project)
        session.add(
            RenderedOutput(
                project=project,
                volume=volume,
                output_type=RenderOutputType.PDF.value,
                renderer="Vivliostyle",
                config_path=str(config.vivliostyle_config),
                output_path=str(output_path),
                build_logs=logs[-20000:],
                status=(
                    RenderStatus.SUCCEEDED.value
                    if result.returncode == 0
                    else RenderStatus.FAILED.value
                ),
                rendered_at=utc_now(),
                render_metadata={"command": command, "returncode": result.returncode},
            )
        )

    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(f"rendered {output_path}")


def serve(args: argparse.Namespace) -> None:
    import uvicorn

    from fieldnotes.server import create_app

    app = create_app(config_path=args.config)
    uvicorn.run(app, host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fieldnotes",
        description="Ingest, extract, review, and render source-grounded field notes.",
    )
    _add_config_arg(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Create database tables.")
    init_parser.set_defaults(func=init_db)

    seed_parser = subparsers.add_parser("seed", help="Seed the demo project graph.")
    seed_parser.set_defaults(func=seed_db)

    ingest_parser = subparsers.add_parser("ingest", help="Scan configured watch roots.")
    ingest_parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Create blocked image chunks instead of calling OpenAI OCR.",
    )
    ingest_parser.set_defaults(func=ingest)

    extract_parser = subparsers.add_parser(
        "extract", help="Extract provisional knowledge candidates from ready chunks."
    )
    extract_parser.add_argument("--provider", choices=["openai", "local"], default=None)
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--include-existing", action="store_true")
    extract_parser.set_defaults(func=extract)

    review_parser = subparsers.add_parser("review", help="Review extracted candidates.")
    review_subparsers = review_parser.add_subparsers(dest="review_command", required=True)

    promote_parser = review_subparsers.add_parser("promote")
    promote_parser.add_argument("candidate_id")
    promote_parser.add_argument("--chapter-brief-id")
    promote_parser.add_argument("--section-key", default="field_note")
    promote_parser.add_argument("--reviewer", default="human")
    promote_parser.add_argument("--rationale")
    promote_parser.set_defaults(func=promote)

    reject_parser = review_subparsers.add_parser("reject")
    reject_parser.add_argument("candidate_id")
    reject_parser.add_argument("--reviewer", default="human")
    reject_parser.add_argument("--rationale")
    reject_parser.set_defaults(func=reject)

    link_parser = review_subparsers.add_parser("link")
    link_parser.add_argument("candidate_id")
    link_parser.add_argument("chapter_brief_id")
    link_parser.add_argument("--section-key", default="field_note")
    link_parser.add_argument("--reviewer", default="human")
    link_parser.add_argument("--rationale")
    link_parser.set_defaults(func=link)

    chapter_parser = subparsers.add_parser("chapter", help="Review chapter concepts.")
    chapter_subparsers = chapter_parser.add_subparsers(
        dest="chapter_command", required=True
    )

    approve_parser = chapter_subparsers.add_parser("approve")
    approve_parser.add_argument(
        "slug",
        nargs="?",
        default="book-that-remembers-its-sources",
        help="Chapter brief slug to approve.",
    )
    approve_parser.add_argument("--chapter-brief-id")
    approve_parser.add_argument("--reviewer", default="human")
    approve_parser.add_argument("--rationale")
    approve_parser.set_defaults(func=approve_chapter)

    save_parser = chapter_subparsers.add_parser(
        "save-candidate",
        help="Create or update a proposed chapter brief from an agent note.",
    )
    save_parser.add_argument("--title", required=True)
    save_parser.add_argument("--subtitle")
    save_parser.add_argument("--description")
    save_parser.add_argument("--slug")
    save_parser.add_argument("--reviewer", default="codex")
    save_parser.add_argument("--source", default="conversation")
    save_parser.set_defaults(func=save_chapter)

    render_parser = subparsers.add_parser(
        "render", help="Run Vivliostyle build and record the output."
    )
    render_parser.set_defaults(func=render)

    serve_parser = subparsers.add_parser("serve", help="Run the review board.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.set_defaults(func=serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
