"""SQLAlchemy models for the knowledge-to-book publishing pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


JSONB_TYPE = JSONB().with_variant(JSON(), "sqlite")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class StringEnum(str, Enum):
    """String-valued constants stored in flexible VARCHAR columns."""

    def __str__(self) -> str:
        return self.value


class ProjectStatus(StringEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"


class SourceType(StringEnum):
    GIT_REPOSITORY = "git_repository"
    FILE_PATH = "file_path"
    UPLOADED_DOCUMENT = "uploaded_document"
    CHAT_TRANSCRIPT = "chat_transcript"
    MEETING_TRANSCRIPT = "meeting_transcript"
    SCREENSHOT = "screenshot"
    GENERATED_IMAGE = "generated_image"
    URL = "url"
    PROJECT_NOTE = "project_note"
    EVENT_NOTE = "event_note"
    CONSULTING_ARTIFACT = "consulting_artifact"
    CODE_SNIPPET = "code_snippet"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    RENDERED_OUTPUT = "rendered_output"


class SourceStatus(StringEnum):
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"
    ARCHIVED = "archived"


class KnowledgeNodeType(StringEnum):
    OBSERVATION = "observation"
    CLAIM = "claim"
    DECISION = "decision"
    PROBLEM = "problem"
    CONSTRAINT = "constraint"
    IMPLEMENTATION_DETAIL = "implementation_detail"
    PATTERN = "pattern"
    TRANSFERABLE_LESSON = "transferable_lesson"
    OAHU_LOCAL_LAYER = "oahu_local_layer"
    STRONG_OPINION = "strong_opinion"
    QUESTION = "question"
    RISK = "risk"
    ARTIFACT = "artifact"
    QUOTE = "quote"
    EVIDENCE = "evidence"
    CHAPTER_IDEA = "chapter_idea"
    VISUAL_IDEA = "visual_idea"
    DIAGRAM_IDEA = "diagram_idea"


class KnowledgeStatus(StringEnum):
    EXTRACTED = "extracted"
    TRIAGED = "triaged"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DRAFTED = "drafted"
    PUBLISHED = "published"


class LocatorType(StringEnum):
    FILE_LINE_RANGE = "file_line_range"
    TIMESTAMP_RANGE = "timestamp_range"
    PAGE_NUMBER = "page_number"
    IMAGE_REGION = "image_region"
    URL_FRAGMENT = "url_fragment"
    COMMIT_HASH = "commit_hash"
    OBJECT_PATH = "object_path"
    FREEFORM = "freeform"


class EdgeType(StringEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFINES = "refines"
    GENERALIZES = "generalizes"
    EXEMPLIFIES = "exemplifies"
    DEPENDS_ON = "depends_on"
    CAUSED_BY = "caused_by"
    LED_TO = "led_to"
    REPEATS_PATTERN = "repeats_pattern"
    LOCALIZES_TO_OAHU = "localizes_to_oahu"
    BECOMES_CHAPTER_SECTION = "becomes_chapter_section"
    BECOMES_PULL_QUOTE = "becomes_pull_quote"
    BECOMES_VISUAL = "becomes_visual"
    BELONGS_TO_CLUSTER = "belongs_to_cluster"


class WorkStatus(StringEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DRAFTING = "drafting"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PUBLISHED = "published"


class ChapterStatus(StringEnum):
    DRAFT = "draft"
    READY = "ready"


class DraftStatus(StringEnum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    REVISING = "revising"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class VisualAssetType(StringEnum):
    GENERATED_IMAGE = "generated_image"
    DIAGRAM = "diagram"
    SCREENSHOT = "screenshot"
    PHOTO = "photo"
    VISUAL_MOTIF = "visual_motif"


class VolumeStatus(StringEnum):
    PLANNING = "planning"
    DRAFTING = "drafting"
    IN_PROOF = "in_proof"
    PRINT_READY = "print_ready"
    PUBLISHED = "published"


class RenderStatus(StringEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RenderOutputType(StringEnum):
    PDF = "pdf"
    WEBPUB = "webpub"
    HTML = "html"
    PROOF_IMAGES = "proof_images"
    PAGE_PNGS = "page_pngs"
    PRINT_READY_PDF = "print_ready_pdf"
    DRAFT_PDF = "draft_pdf"


class EvaluationTargetType(StringEnum):
    KNOWLEDGE_NODE = "knowledge_node"
    CHAPTER_DRAFT = "chapter_draft"
    CHAPTER_BRIEF = "chapter_brief"
    VISUAL_ASSET = "visual_asset"
    FIELD_NOTE_CANDIDATE = "field_note_candidate"
    RENDERED_OUTPUT = "rendered_output"


class EvaluatorType(StringEnum):
    LLM = "llm"
    HUMAN = "human"
    SCRIPT = "script"


class EvaluationStatus(StringEnum):
    PASSING = "passing"
    FAILING = "failing"
    NEEDS_REVIEW = "needs_review"


class AgentRunStatus(StringEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class SourceChunkType(StringEnum):
    TEXT = "text"
    OCR_PAGE = "ocr_page"
    TRANSCRIPT_SEGMENT = "transcript_segment"
    CODE_SNIPPET = "code_snippet"
    REPO_SUMMARY = "repo_summary"
    PDF_PAGE = "pdf_page"
    NOTE = "note"


class ChunkStatus(StringEnum):
    READY = "ready"
    BLOCKED = "blocked"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"
    DISCARDED = "discarded"


class ExtractionStatus(StringEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CandidateStatus(StringEnum):
    NEEDS_REVIEW = "needs_review"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReviewDecisionType(StringEnum):
    PROMOTE = "promote"
    LINK_TO_CHAPTER = "link_to_chapter"
    REJECT = "reject"
    SUPERSEDE = "supersede"
    NOTE = "note"


class ReviewTargetType(StringEnum):
    EXTRACTED_CANDIDATE = "extracted_candidate"
    EXTRACTED_CANDIDATE_EDGE = "extracted_candidate_edge"
    KNOWLEDGE_NODE = "knowledge_node"
    FIELD_NOTE_CANDIDATE = "field_note_candidate"
    CHAPTER_BRIEF = "chapter_brief"
    SOURCE_CHUNK = "source_chunk"


class Project(Base, IdMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=ProjectStatus.ACTIVE.value, nullable=False
    )
    project_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    volumes: Mapped[list[BookVolume]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sources: Mapped[list[SourceMaterial]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_nodes: Mapped[list[KnowledgeNode]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_edges: Mapped[list[KnowledgeEdge]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    field_note_candidates: Mapped[list[FieldNoteCandidate]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    chapter_briefs: Mapped[list[ChapterBrief]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    visual_assets: Mapped[list[VisualAsset]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    rendered_outputs: Mapped[list[RenderedOutput]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    source_chunks: Mapped[list[SourceChunk]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    extraction_runs: Mapped[list[ExtractionRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    extracted_candidates: Mapped[list[ExtractedCandidate]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    extracted_candidate_edges: Mapped[list[ExtractedCandidateEdge]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    review_decisions: Mapped[list[ReviewDecision]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class BookVolume(Base, IdMixin, TimestampMixin):
    __tablename__ = "book_volumes"
    __table_args__ = (UniqueConstraint("project_id", "slug"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    trim_size: Mapped[str | None] = mapped_column(String(64))
    page_size: Mapped[str | None] = mapped_column(String(64))
    binding_type: Mapped[str | None] = mapped_column(String(120))
    printer_target: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(
        String(64), default=VolumeStatus.PLANNING.value, nullable=False
    )
    volume_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="volumes")
    chapter_briefs: Mapped[list[ChapterBrief]] = relationship(back_populates="volume")
    rendered_outputs: Mapped[list[RenderedOutput]] = relationship(back_populates="volume")


class SourceMaterial(Base, IdMixin, TimestampMixin):
    __tablename__ = "source_materials"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(Text)
    uri: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    provenance: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(
        String(64), default=SourceStatus.ACTIVE.value, nullable=False
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="sources")
    evidence_links: Mapped[list[NodeSourceLink]] = relationship(back_populates="source")
    chunks: Mapped[list[SourceChunk]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class KnowledgeNode(Base, IdMixin, TimestampMixin):
    __tablename__ = "knowledge_nodes"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), default=KnowledgeStatus.EXTRACTED.value, nullable=False, index=True
    )
    node_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_nodes")
    evidence_links: Mapped[list[NodeSourceLink]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )
    outgoing_edges: Mapped[list[KnowledgeEdge]] = relationship(
        foreign_keys="KnowledgeEdge.source_node_id",
        back_populates="source_node",
    )
    incoming_edges: Mapped[list[KnowledgeEdge]] = relationship(
        foreign_keys="KnowledgeEdge.target_node_id",
        back_populates="target_node",
    )
    field_note_links: Mapped[list[FieldNoteCandidateNode]] = relationship(
        back_populates="node"
    )
    chapter_brief_links: Mapped[list[ChapterBriefNode]] = relationship(
        back_populates="node"
    )
    visual_assets: Mapped[list[VisualAsset]] = relationship(back_populates="knowledge_node")


class NodeSourceLink(Base, IdMixin, TimestampMixin):
    __tablename__ = "node_source_links"

    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locator_type: Mapped[str | None] = mapped_column(String(64))
    locator_data: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    quote: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    link_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    node: Mapped[KnowledgeNode] = relationship(back_populates="evidence_links")
    source: Mapped[SourceMaterial] = relationship(back_populates="evidence_links")
    knowledge_edges: Mapped[list[KnowledgeEdge]] = relationship(back_populates="evidence_link")


class KnowledgeEdge(Base, IdMixin, TimestampMixin):
    __tablename__ = "knowledge_edges"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    evidence_link_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("node_source_links.id", ondelete="SET NULL"), index=True
    )
    edge_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_edges")
    source_node: Mapped[KnowledgeNode] = relationship(
        foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node: Mapped[KnowledgeNode] = relationship(
        foreign_keys=[target_node_id], back_populates="incoming_edges"
    )
    evidence_link: Mapped[NodeSourceLink | None] = relationship(
        back_populates="knowledge_edges"
    )


class FieldNoteCandidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "field_note_candidates"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    thesis: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=WorkStatus.PROPOSED.value, nullable=False, index=True
    )
    usefulness_score: Mapped[float | None] = mapped_column(Float)
    specificity_score: Mapped[float | None] = mapped_column(Float)
    novelty_score: Mapped[float | None] = mapped_column(Float)
    groundedness_score: Mapped[float | None] = mapped_column(Float)
    local_relevance_score: Mapped[float | None] = mapped_column(Float)
    opinion_strength_score: Mapped[float | None] = mapped_column(Float)
    candidate_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="field_note_candidates")
    node_links: Mapped[list[FieldNoteCandidateNode]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    chapter_brief_links: Mapped[list[ChapterBriefCandidate]] = relationship(
        back_populates="candidate"
    )


class FieldNoteCandidateNode(Base, IdMixin, TimestampMixin):
    __tablename__ = "field_note_candidate_nodes"
    __table_args__ = (UniqueConstraint("candidate_id", "node_id"),)

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("field_note_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str | None] = mapped_column(String(80))
    sequence_order: Mapped[int | None] = mapped_column(Integer)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    candidate: Mapped[FieldNoteCandidate] = relationship(back_populates="node_links")
    node: Mapped[KnowledgeNode] = relationship(back_populates="field_note_links")


class ChapterBrief(Base, IdMixin, TimestampMixin):
    __tablename__ = "chapter_briefs"
    __table_args__ = (UniqueConstraint("volume_id", "slug"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    volume_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("book_volumes.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    sequence_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(64), default=ChapterStatus.DRAFT.value, nullable=False, index=True
    )
    intended_page_count: Mapped[int | None] = mapped_column(Integer)
    target_word_count: Mapped[int | None] = mapped_column(Integer)
    situation: Mapped[str | None] = mapped_column(Text)
    constraint: Mapped[str | None] = mapped_column(Text)
    build: Mapped[str | None] = mapped_column(Text)
    pattern: Mapped[str | None] = mapped_column(Text)
    oahu_layer: Mapped[str | None] = mapped_column(Text)
    field_note: Mapped[str | None] = mapped_column(Text)
    next_build: Mapped[str | None] = mapped_column(Text)
    brief_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="chapter_briefs")
    volume: Mapped[BookVolume | None] = relationship(back_populates="chapter_briefs")
    candidate_links: Mapped[list[ChapterBriefCandidate]] = relationship(
        back_populates="chapter_brief", cascade="all, delete-orphan"
    )
    node_links: Mapped[list[ChapterBriefNode]] = relationship(
        back_populates="chapter_brief", cascade="all, delete-orphan"
    )
    drafts: Mapped[list[ChapterDraft]] = relationship(
        back_populates="chapter_brief", cascade="all, delete-orphan"
    )
    visual_assets: Mapped[list[VisualAsset]] = relationship(back_populates="chapter_brief")
    rendered_outputs: Mapped[list[RenderedOutput]] = relationship(
        back_populates="chapter_brief"
    )


class ChapterBriefCandidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "chapter_brief_candidates"
    __table_args__ = (UniqueConstraint("chapter_brief_id", "candidate_id"),)

    chapter_brief_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapter_briefs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("field_note_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str | None] = mapped_column(String(80))
    sequence_order: Mapped[int | None] = mapped_column(Integer)

    chapter_brief: Mapped[ChapterBrief] = relationship(back_populates="candidate_links")
    candidate: Mapped[FieldNoteCandidate] = relationship(back_populates="chapter_brief_links")


class ChapterBriefNode(Base, IdMixin, TimestampMixin):
    __tablename__ = "chapter_brief_nodes"
    __table_args__ = (UniqueConstraint("chapter_brief_id", "node_id"),)

    chapter_brief_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapter_briefs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_key: Mapped[str | None] = mapped_column(String(80))
    sequence_order: Mapped[int | None] = mapped_column(Integer)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    chapter_brief: Mapped[ChapterBrief] = relationship(back_populates="node_links")
    node: Mapped[KnowledgeNode] = relationship(back_populates="chapter_brief_links")


class ChapterDraft(Base, IdMixin, TimestampMixin):
    __tablename__ = "chapter_drafts"
    __table_args__ = (UniqueConstraint("chapter_brief_id", "version_number"),)

    chapter_brief_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapter_briefs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body_format: Mapped[str] = mapped_column(String(40), default="markdown", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(120))
    model_name: Mapped[str | None] = mapped_column(String(160))
    model_metadata: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    generation_prompt_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=DraftStatus.DRAFT.value, nullable=False, index=True
    )
    editor_notes: Mapped[str | None] = mapped_column(Text)

    chapter_brief: Mapped[ChapterBrief] = relationship(back_populates="drafts")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="chapter_drafts")
    visual_assets: Mapped[list[VisualAsset]] = relationship(back_populates="chapter_draft")


class VisualAsset(Base, IdMixin, TimestampMixin):
    __tablename__ = "visual_assets"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_brief_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_briefs.id", ondelete="SET NULL"), index=True
    )
    chapter_draft_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_drafts.id", ondelete="SET NULL"), index=True
    )
    knowledge_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_materials.id", ondelete="SET NULL"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section_key: Mapped[str | None] = mapped_column(String(80))
    path: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped[str | None] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    model_provider: Mapped[str | None] = mapped_column(String(120))
    model_name: Mapped[str | None] = mapped_column(String(160))
    generation_params: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    license_status: Mapped[str | None] = mapped_column(String(120))
    rights_metadata: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    dpi: Mapped[int | None] = mapped_column(Integer)
    print_suitability_score: Mapped[float | None] = mapped_column(Float)
    alt_text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=WorkStatus.PROPOSED.value, nullable=False, index=True
    )
    asset_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="visual_assets")
    chapter_brief: Mapped[ChapterBrief | None] = relationship(back_populates="visual_assets")
    chapter_draft: Mapped[ChapterDraft | None] = relationship(back_populates="visual_assets")
    knowledge_node: Mapped[KnowledgeNode | None] = relationship(back_populates="visual_assets")
    source: Mapped[SourceMaterial | None] = relationship()


class RenderedOutput(Base, IdMixin, TimestampMixin):
    __tablename__ = "rendered_outputs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    volume_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("book_volumes.id", ondelete="SET NULL"), index=True
    )
    chapter_brief_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_briefs.id", ondelete="SET NULL"), index=True
    )
    output_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    renderer: Mapped[str] = mapped_column(String(120), nullable=False)
    config_path: Mapped[str | None] = mapped_column(Text)
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_hash: Mapped[str | None] = mapped_column(String(80), index=True)
    build_logs: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=RenderStatus.QUEUED.value, nullable=False, index=True
    )
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    render_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="rendered_outputs")
    volume: Mapped[BookVolume | None] = relationship(back_populates="rendered_outputs")
    chapter_brief: Mapped[ChapterBrief | None] = relationship(
        back_populates="rendered_outputs"
    )


class Evaluation(Base, IdMixin):
    __tablename__ = "evaluations"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    evaluator_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluator_name: Mapped[str | None] = mapped_column(String(160))
    rubric_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scores: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(64), default=EvaluationStatus.NEEDS_REVIEW.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="evaluations")


class AgentRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(160))
    prompt: Mapped[str | None] = mapped_column(Text)
    input_refs: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    output_refs: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(64), default=AgentRunStatus.QUEUED.value, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="agent_runs")
    chapter_drafts: Mapped[list[ChapterDraft]] = relationship(back_populates="agent_run")
    extraction_runs: Mapped[list[ExtractionRun]] = relationship(back_populates="agent_run")


class Tag(Base, IdMixin):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("project_id", "slug"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="tags")
    taggings: Mapped[list[Tagging]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class Tagging(Base, IdMixin):
    __tablename__ = "taggings"
    __table_args__ = (UniqueConstraint("tag_id", "target_type", "target_id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    tag: Mapped[Tag] = relationship(back_populates="taggings")


class SourceChunk(Base, IdMixin, TimestampMixin):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_id", "chunk_index"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    locator_type: Mapped[str | None] = mapped_column(String(64))
    locator_data: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(64), default=ChunkStatus.READY.value, nullable=False, index=True
    )
    ocr_engine: Mapped[str | None] = mapped_column(String(160))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    uncertainty_notes: Mapped[str | None] = mapped_column(Text)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="source_chunks")
    source: Mapped[SourceMaterial] = relationship(back_populates="chunks")
    extracted_candidates: Mapped[list[ExtractedCandidate]] = relationship(
        back_populates="source_chunk", cascade="all, delete-orphan"
    )
    extracted_candidate_edges: Mapped[list[ExtractedCandidateEdge]] = relationship(
        back_populates="source_chunk", cascade="all, delete-orphan"
    )


class ExtractionRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "extraction_runs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), default=ExtractionStatus.PENDING.value, nullable=False, index=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    usage: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="extraction_runs")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="extraction_runs")
    candidates: Mapped[list[ExtractedCandidate]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan"
    )
    candidate_edges: Mapped[list[ExtractedCandidateEdge]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan"
    )


class ExtractedCandidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "extracted_candidates"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reuse_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    raw_output: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(64), default=CandidateStatus.NEEDS_REVIEW.value, nullable=False, index=True
    )
    promoted_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), index=True
    )
    candidate_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="extracted_candidates")
    extraction_run: Mapped[ExtractionRun] = relationship(back_populates="candidates")
    source: Mapped[SourceMaterial] = relationship()
    source_chunk: Mapped[SourceChunk] = relationship(back_populates="extracted_candidates")
    promoted_node: Mapped[KnowledgeNode | None] = relationship()
    outgoing_candidate_edges: Mapped[list[ExtractedCandidateEdge]] = relationship(
        foreign_keys="ExtractedCandidateEdge.source_candidate_id",
        back_populates="source_candidate",
    )
    incoming_candidate_edges: Mapped[list[ExtractedCandidateEdge]] = relationship(
        foreign_keys="ExtractedCandidateEdge.target_candidate_id",
        back_populates="target_candidate",
    )


class ExtractedCandidateEdge(Base, IdMixin, TimestampMixin):
    __tablename__ = "extracted_candidate_edges"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extracted_candidates.id", ondelete="CASCADE"), index=True
    )
    target_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extracted_candidates.id", ondelete="CASCADE"), index=True
    )
    source_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    target_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), default=CandidateStatus.NEEDS_REVIEW.value, nullable=False, index=True
    )
    promoted_edge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_edges.id", ondelete="SET NULL"), index=True
    )
    edge_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="extracted_candidate_edges")
    extraction_run: Mapped[ExtractionRun] = relationship(back_populates="candidate_edges")
    source_chunk: Mapped[SourceChunk] = relationship(back_populates="extracted_candidate_edges")
    source_candidate: Mapped[ExtractedCandidate | None] = relationship(
        foreign_keys=[source_candidate_id], back_populates="outgoing_candidate_edges"
    )
    target_candidate: Mapped[ExtractedCandidate | None] = relationship(
        foreign_keys=[target_candidate_id], back_populates="incoming_candidate_edges"
    )
    source_node: Mapped[KnowledgeNode | None] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped[KnowledgeNode | None] = relationship(foreign_keys=[target_node_id])
    promoted_edge: Mapped[KnowledgeEdge | None] = relationship()


class ReviewDecision(Base, IdMixin):
    __tablename__ = "review_decisions"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(160), default="human", nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    applied_by: Mapped[str | None] = mapped_column(String(160))
    dry_run: Mapped[bool] = mapped_column(default=False, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    decision_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSONB_TYPE), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="review_decisions")
