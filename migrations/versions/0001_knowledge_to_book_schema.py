"""knowledge to book schema

Revision ID: 0001_knowledge_to_book
Revises:
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_knowledge_to_book"
down_revision = None
branch_labels = None
depends_on = None


def jsonb_type():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def id_column():
    return sa.Column("id", sa.Uuid(), nullable=False)


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        id_column(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "book_volumes",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("trim_size", sa.String(length=64), nullable=True),
        sa.Column("page_size", sa.String(length=64), nullable=True),
        sa.Column("binding_type", sa.String(length=120), nullable=True),
        sa.Column("printer_target", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug"),
    )

    op.create_table(
        "source_materials",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("provenance", jsonb_type(), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_nodes",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_runs",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_type", sa.String(length=80), nullable=False),
        sa.Column("agent_name", sa.String(length=160), nullable=False),
        sa.Column("tool_name", sa.String(length=160), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("input_refs", jsonb_type(), nullable=False),
        sa.Column("output_refs", jsonb_type(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tags",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug"),
    )

    op.create_table(
        "field_note_candidates",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("usefulness_score", sa.Float(), nullable=True),
        sa.Column("specificity_score", sa.Float(), nullable=True),
        sa.Column("novelty_score", sa.Float(), nullable=True),
        sa.Column("groundedness_score", sa.Float(), nullable=True),
        sa.Column("local_relevance_score", sa.Float(), nullable=True),
        sa.Column("opinion_strength_score", sa.Float(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "chapter_briefs",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("volume_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("intended_page_count", sa.Integer(), nullable=True),
        sa.Column("target_word_count", sa.Integer(), nullable=True),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("constraint", sa.Text(), nullable=True),
        sa.Column("build", sa.Text(), nullable=True),
        sa.Column("pattern", sa.Text(), nullable=True),
        sa.Column("oahu_layer", sa.Text(), nullable=True),
        sa.Column("field_note", sa.Text(), nullable=True),
        sa.Column("next_build", sa.Text(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["volume_id"], ["book_volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volume_id", "slug"),
    )

    op.create_table(
        "node_source_links",
        id_column(),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("locator_type", sa.String(length=64), nullable=True),
        sa.Column("locator_data", jsonb_type(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source_materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_edges",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_link_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_link_id"], ["node_source_links.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "field_note_candidate_nodes",
        id_column(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["candidate_id"], ["field_note_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "node_id"),
    )

    op.create_table(
        "chapter_brief_candidates",
        id_column(),
        sa.Column("chapter_brief_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["chapter_brief_id"], ["chapter_briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["field_note_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_brief_id", "candidate_id"),
    )

    op.create_table(
        "chapter_brief_nodes",
        id_column(),
        sa.Column("chapter_brief_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.String(length=80), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["chapter_brief_id"], ["chapter_briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_brief_id", "node_id"),
    )

    op.create_table(
        "chapter_drafts",
        id_column(),
        sa.Column("chapter_brief_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("body_format", sa.String(length=40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.String(length=120), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("model_metadata", jsonb_type(), nullable=False),
        sa.Column("generation_prompt_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("editor_notes", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["chapter_brief_id"], ["chapter_briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_brief_id", "version_number"),
    )

    op.create_table(
        "visual_assets",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_brief_id", sa.Uuid(), nullable=True),
        sa.Column("chapter_draft_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_node_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("section_key", sa.String(length=80), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.String(length=120), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("generation_params", jsonb_type(), nullable=False),
        sa.Column("license_status", sa.String(length=120), nullable=True),
        sa.Column("rights_metadata", jsonb_type(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("dpi", sa.Integer(), nullable=True),
        sa.Column("print_suitability_score", sa.Float(), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_brief_id"], ["chapter_briefs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_draft_id"], ["chapter_drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_node_id"], ["knowledge_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["source_materials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rendered_outputs",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("volume_id", sa.Uuid(), nullable=True),
        sa.Column("chapter_brief_id", sa.Uuid(), nullable=True),
        sa.Column("output_type", sa.String(length=64), nullable=False),
        sa.Column("renderer", sa.String(length=120), nullable=False),
        sa.Column("config_path", sa.Text(), nullable=True),
        sa.Column("output_path", sa.Text(), nullable=False),
        sa.Column("git_commit_hash", sa.String(length=80), nullable=True),
        sa.Column("build_logs", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["volume_id"], ["book_volumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_brief_id"], ["chapter_briefs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "evaluations",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_type", sa.String(length=64), nullable=False),
        sa.Column("evaluator_name", sa.String(length=160), nullable=True),
        sa.Column("rubric_name", sa.String(length=120), nullable=False),
        sa.Column("scores", jsonb_type(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "taggings",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag_id", "target_type", "target_id"),
    )

    for table, columns in {
        "book_volumes": ["project_id"],
        "source_materials": ["project_id", "source_type", "content_hash"],
        "knowledge_nodes": ["project_id", "node_type", "status"],
        "agent_runs": ["project_id", "run_type", "status"],
        "field_note_candidates": ["project_id", "status"],
        "chapter_briefs": ["project_id", "volume_id", "status"],
        "node_source_links": ["node_id", "source_id"],
        "knowledge_edges": [
            "project_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "evidence_link_id",
        ],
        "field_note_candidate_nodes": ["candidate_id", "node_id"],
        "chapter_brief_candidates": ["chapter_brief_id", "candidate_id"],
        "chapter_brief_nodes": ["chapter_brief_id", "node_id"],
        "chapter_drafts": ["chapter_brief_id", "agent_run_id", "status"],
        "visual_assets": [
            "project_id",
            "chapter_brief_id",
            "chapter_draft_id",
            "knowledge_node_id",
            "source_id",
            "asset_type",
            "status",
        ],
        "rendered_outputs": [
            "project_id",
            "volume_id",
            "chapter_brief_id",
            "output_type",
            "git_commit_hash",
            "status",
        ],
        "evaluations": ["project_id", "target_type", "target_id", "rubric_name", "status"],
        "tags": ["project_id"],
        "taggings": ["project_id", "tag_id", "target_type", "target_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, columns in {
        "taggings": ["project_id", "tag_id", "target_type", "target_id"],
        "tags": ["project_id"],
        "evaluations": ["project_id", "target_type", "target_id", "rubric_name", "status"],
        "rendered_outputs": [
            "project_id",
            "volume_id",
            "chapter_brief_id",
            "output_type",
            "git_commit_hash",
            "status",
        ],
        "visual_assets": [
            "project_id",
            "chapter_brief_id",
            "chapter_draft_id",
            "knowledge_node_id",
            "source_id",
            "asset_type",
            "status",
        ],
        "chapter_drafts": ["chapter_brief_id", "agent_run_id", "status"],
        "knowledge_edges": [
            "project_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "evidence_link_id",
        ],
        "chapter_brief_nodes": ["chapter_brief_id", "node_id"],
        "chapter_brief_candidates": ["chapter_brief_id", "candidate_id"],
        "field_note_candidate_nodes": ["candidate_id", "node_id"],
        "node_source_links": ["node_id", "source_id"],
        "chapter_briefs": ["project_id", "volume_id", "status"],
        "field_note_candidates": ["project_id", "status"],
        "agent_runs": ["project_id", "run_type", "status"],
        "knowledge_nodes": ["project_id", "node_type", "status"],
        "source_materials": ["project_id", "source_type", "content_hash"],
        "book_volumes": ["project_id"],
    }.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)

    op.drop_table("taggings")
    op.drop_table("evaluations")
    op.drop_table("rendered_outputs")
    op.drop_table("visual_assets")
    op.drop_table("chapter_drafts")
    op.drop_table("chapter_brief_nodes")
    op.drop_table("chapter_brief_candidates")
    op.drop_table("field_note_candidate_nodes")
    op.drop_table("knowledge_edges")
    op.drop_table("node_source_links")
    op.drop_table("chapter_briefs")
    op.drop_table("field_note_candidates")
    op.drop_table("tags")
    op.drop_table("agent_runs")
    op.drop_table("knowledge_nodes")
    op.drop_table("source_materials")
    op.drop_table("book_volumes")
    op.drop_table("projects")
