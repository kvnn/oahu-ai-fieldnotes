"""Seed the database with the initial Oahu AI Field Notes project graph."""

from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy import select

from fieldnotes.db.models import (
    AgentRun,
    AgentRunStatus,
    Base,
    BookVolume,
    ChapterBrief,
    ChapterBriefCandidate,
    ChapterBriefNode,
    EdgeType,
    FieldNoteCandidate,
    FieldNoteCandidateNode,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeType,
    LocatorType,
    NodeSourceLink,
    Project,
    RenderOutputType,
    RenderStatus,
    RenderedOutput,
    SourceMaterial,
    SourceType,
    WorkStatus,
    utc_now,
)
from fieldnotes.db.session import get_database_url, make_engine, make_session_factory


PROJECT_SLUG = "oahu-ai-field-notes-vol-1"


def seed_demo(session) -> UUID:
    existing_project_id = session.scalar(
        select(Project.id).where(Project.slug == PROJECT_SLUG)
    )
    if existing_project_id:
        return existing_project_id

    project = Project(
        name="O‘ahu A.I. Field Notes Vol. 1",
        slug=PROJECT_SLUG,
        description=(
            "A source-grounded longform publishing project that turns messy AI "
            "work into field-note chapters."
        ),
        project_metadata={"vivliostyle_config": "vivliostyle.config.js"},
    )

    volume = BookVolume(
        project=project,
        title="O‘ahu A.I. Field Notes",
        subtitle="Vol. 1",
        slug="vol-1",
        trim_size="6in x 9in",
        page_size="6in x 9in",
        binding_type="perfect_bound",
        printer_target="Mixam perfect bound",
    )

    repo_source = SourceMaterial(
        project=project,
        source_type=SourceType.GIT_REPOSITORY.value,
        title="Book scaffold repository",
        location="/Users/kvnn/Projects/oahu-ai-field-notes",
        provenance={"captured_by": "seed_demo"},
        source_metadata={"framework": "Vivliostyle"},
    )
    config_source = SourceMaterial(
        project=project,
        source_type=SourceType.FILE_PATH.value,
        title="Vivliostyle configuration",
        location="vivliostyle.config.js",
        provenance={"captured_by": "seed_demo"},
    )
    render_source = SourceMaterial(
        project=project,
        source_type=SourceType.RENDERED_OUTPUT.value,
        title="Initial PDF render",
        location="dist/oahu-ai-field-notes.pdf",
        provenance={"renderer": "Vivliostyle"},
    )

    observation = KnowledgeNode(
        project=project,
        node_type=KnowledgeNodeType.OBSERVATION.value,
        title="The book is also an extraction system",
        body=(
            "The project needs to preserve source material and extracted meaning, "
            "not only chapter prose."
        ),
        confidence=0.92,
        node_metadata={"pipeline_stage": "source_to_observation"},
    )
    decision = KnowledgeNode(
        project=project,
        node_type=KnowledgeNodeType.DECISION.value,
        title="Use Vivliostyle for page rendering",
        body=(
            "Vivliostyle gives the project a programmable path from Markdown and "
            "CSS into PDF and WebPub outputs."
        ),
        confidence=0.9,
    )
    lesson = KnowledgeNode(
        project=project,
        node_type=KnowledgeNodeType.TRANSFERABLE_LESSON.value,
        title="Keep provenance close to prose",
        body=(
            "A chapter is more useful when claims, examples, and visual choices "
            "can be traced back to concrete project artifacts."
        ),
        confidence=0.86,
    )

    config_evidence = NodeSourceLink(
        node=decision,
        source=config_source,
        locator_type=LocatorType.FILE_LINE_RANGE.value,
        locator_data={"path": "vivliostyle.config.js", "start_line": 1, "end_line": 45},
        excerpt="Vivliostyle config defines the printable book outputs.",
        relevance_score=0.95,
        confidence_score=0.9,
    )
    NodeSourceLink(
        node=observation,
        source=repo_source,
        locator_type=LocatorType.OBJECT_PATH.value,
        locator_data={"path": "README.md"},
        excerpt="Project README describes the manuscript structure.",
        relevance_score=0.75,
        confidence_score=0.82,
    )
    NodeSourceLink(
        node=lesson,
        source=render_source,
        locator_type=LocatorType.OBJECT_PATH.value,
        locator_data={"path": "dist/oahu-ai-field-notes.pdf"},
        excerpt="Rendered outputs become evidence for print-readiness decisions.",
        relevance_score=0.78,
        confidence_score=0.8,
    )

    KnowledgeEdge(
        project=project,
        source_node=decision,
        target_node=lesson,
        edge_type=EdgeType.SUPPORTS.value,
        description="The rendering decision supports the broader print-aware pattern.",
        confidence=0.84,
        evidence_link=config_evidence,
    )

    candidate = FieldNoteCandidate(
        project=project,
        title="The manuscript is a graph before it is a chapter",
        thesis=(
            "A useful AI field-notes book should keep sources, claims, and print "
            "decisions connected through the whole publishing pipeline."
        ),
        summary=(
            "A candidate field note about turning a working repo into a grounded "
            "book-production system."
        ),
        status=WorkStatus.ACCEPTED.value,
        usefulness_score=0.91,
        specificity_score=0.84,
        novelty_score=0.72,
        groundedness_score=0.88,
        local_relevance_score=0.68,
        opinion_strength_score=0.79,
    )
    FieldNoteCandidateNode(
        candidate=candidate,
        node=observation,
        role="lead_observation",
        sequence_order=1,
        relevance_score=0.95,
    )
    FieldNoteCandidateNode(
        candidate=candidate,
        node=decision,
        role="build_decision",
        sequence_order=2,
        relevance_score=0.88,
    )
    FieldNoteCandidateNode(
        candidate=candidate,
        node=lesson,
        role="takeaway",
        sequence_order=3,
        relevance_score=0.9,
    )

    brief = ChapterBrief(
        project=project,
        volume=volume,
        title="A Book That Remembers Its Sources",
        subtitle="Turning messy AI work into grounded print",
        slug="book-that-remembers-its-sources",
        sequence_order=1,
        status=WorkStatus.ACCEPTED.value,
        intended_page_count=12,
        target_word_count=3500,
        situation=(
            "The project begins as a real working repo and publishing setup, not "
            "as a clean manuscript."
        ),
        constraint=(
            "Every useful chapter claim needs a recoverable path back to source "
            "material."
        ),
        build="Create a SQLAlchemy graph that connects sources, nodes, briefs, drafts, and renders.",
        pattern="Treat longform publishing as a knowledge extraction pipeline.",
        oahu_layer=(
            "The O‘ahu framing asks which lessons matter locally, culturally, and "
            "operationally."
        ),
        field_note=(
            "The book should be able to cite its own making without becoming a "
            "generic CMS."
        ),
        next_build="Draft the first chapter from the candidate cluster and evaluate grounding.",
    )
    ChapterBriefCandidate(
        chapter_brief=brief,
        candidate=candidate,
        role="primary_candidate",
        sequence_order=1,
    )
    ChapterBriefNode(
        chapter_brief=brief,
        node=observation,
        section_key="situation",
        sequence_order=1,
        relevance_score=0.93,
    )
    ChapterBriefNode(
        chapter_brief=brief,
        node=decision,
        section_key="build",
        sequence_order=2,
        relevance_score=0.88,
    )
    ChapterBriefNode(
        chapter_brief=brief,
        node=lesson,
        section_key="field_note",
        sequence_order=3,
        relevance_score=0.9,
    )

    AgentRun(
        project=project,
        run_type="schema_seed",
        agent_name="codex",
        tool_name="fieldnotes-seed",
        prompt="Create seed data for the O‘ahu AI Field Notes knowledge-to-book schema.",
        input_refs={"sources": ["vivliostyle.config.js", "README.md"]},
        output_refs={"chapter_brief_slug": brief.slug},
        status=AgentRunStatus.SUCCEEDED.value,
        started_at=utc_now(),
        completed_at=utc_now(),
    )

    RenderedOutput(
        project=project,
        volume=volume,
        output_type=RenderOutputType.PDF.value,
        renderer="Vivliostyle",
        config_path="vivliostyle.config.js",
        output_path="dist/oahu-ai-field-notes.pdf",
        status=RenderStatus.SUCCEEDED.value,
        rendered_at=utc_now(),
    )

    session.add(project)
    session.commit()
    return project.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=get_database_url())
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create tables from SQLAlchemy metadata before seeding.",
    )
    args = parser.parse_args()

    engine = make_engine(args.database_url)
    if args.create:
        Base.metadata.create_all(engine)

    session_factory = make_session_factory(engine)
    with session_factory() as session:
        project_id = seed_demo(session)
        print(f"Seeded demo project: {project_id}")


if __name__ == "__main__":
    main()
