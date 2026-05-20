"""Structured extraction schemas used by model-backed workflows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


NODE_TYPES = (
    "observation",
    "claim",
    "decision",
    "problem",
    "constraint",
    "implementation_detail",
    "pattern",
    "transferable_lesson",
    "oahu_local_layer",
    "strong_opinion",
    "question",
    "risk",
    "artifact",
    "quote",
    "evidence",
    "chapter_idea",
    "visual_idea",
    "diagram_idea",
)

EDGE_TYPES = (
    "supports",
    "contradicts",
    "refines",
    "generalizes",
    "exemplifies",
    "depends_on",
    "caused_by",
    "led_to",
    "repeats_pattern",
    "localizes_to_oahu",
    "becomes_chapter_section",
    "becomes_pull_quote",
    "becomes_visual",
    "belongs_to_cluster",
)

NodeType = Literal[
    "observation",
    "claim",
    "decision",
    "problem",
    "constraint",
    "implementation_detail",
    "pattern",
    "transferable_lesson",
    "oahu_local_layer",
    "strong_opinion",
    "question",
    "risk",
    "artifact",
    "quote",
    "evidence",
    "chapter_idea",
    "visual_idea",
    "diagram_idea",
]

EdgeTypeName = Literal[
    "supports",
    "contradicts",
    "refines",
    "generalizes",
    "exemplifies",
    "depends_on",
    "caused_by",
    "led_to",
    "repeats_pattern",
    "localizes_to_oahu",
    "becomes_chapter_section",
    "becomes_pull_quote",
    "becomes_visual",
    "belongs_to_cluster",
]


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    uncertainty_notes: str = ""
    visible_regions: list[dict[str, str | int | float]] = Field(default_factory=list)


class ExtractedFieldnoteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: NodeType
    title: str
    body: str = ""
    evidence_quote: str = ""
    rationale: str = ""
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    reuse_score: float = Field(default=0.5, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("node_type")
    @classmethod
    def valid_node_type(cls, value: str) -> str:
        if value not in NODE_TYPES:
            raise ValueError(f"unknown node type: {value}")
        return value


class ExtractedFieldnoteEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_title: str
    target_title: str
    edge_type: EdgeTypeName
    rationale: str = ""
    evidence_quote: str = ""
    strength: float = Field(default=0.5, ge=0, le=1)
    confidence_score: float = Field(default=0.5, ge=0, le=1)

    @field_validator("edge_type")
    @classmethod
    def valid_edge_type(cls, value: str) -> str:
        if value not in EDGE_TYPES:
            raise ValueError(f"unknown edge type: {value}")
        return value


class FieldnoteExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passage_summary: str = ""
    candidates: list[ExtractedFieldnoteCandidate] = Field(default_factory=list)
    edges: list[ExtractedFieldnoteEdge] = Field(default_factory=list)
    ambiguity_notes: str = ""


class ProductionBriefMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_form: Literal["scene_to_principle", "concept_first", "notebook_mosaic"]
    source_cluster: list[str] = Field(default_factory=list)
    page_rhythm: list[str] = Field(default_factory=list)
    visual_slots: list[str] = Field(default_factory=list)
    key_claims: list[str] = Field(default_factory=list)
    section_page_budget: int | None = Field(default=None, ge=1)
    opener_spread_notes: str = ""
    marginalia_notes: list[str] = Field(default_factory=list)


EXTRACTION_SCHEMA_VERSION = "fieldnotes.extraction_result.v0.1"
PRODUCTION_BRIEF_SCHEMA_VERSION = "fieldnotes.production_brief.v0.1"
