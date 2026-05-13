"""ingestion review workflow

Revision ID: 0002_ingestion_review
Revises: 0001_knowledge_to_book
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_ingestion_review"
down_revision = "0001_knowledge_to_book"
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
        "source_chunks",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_type", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=128), nullable=False),
        sa.Column("locator_type", sa.String(length=64), nullable=True),
        sa.Column("locator_data", jsonb_type(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("ocr_engine", sa.String(length=160), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("uncertainty_notes", sa.Text(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source_materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "chunk_index"),
    )

    op.create_table(
        "extraction_runs",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("config", jsonb_type(), nullable=False),
        sa.Column("usage", jsonb_type(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("chunks_count", sa.Integer(), nullable=False),
        sa.Column("candidates_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "extracted_candidates",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_chunk_id", sa.Uuid(), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("reuse_score", sa.Float(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("raw_output", jsonb_type(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("promoted_node_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["source_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promoted_node_id"], ["knowledge_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "extracted_candidate_edges",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_chunk_id", sa.Uuid(), nullable=False),
        sa.Column("source_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("target_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("source_node_id", sa.Uuid(), nullable=True),
        sa.Column("target_node_id", sa.Uuid(), nullable=True),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("promoted_edge_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", jsonb_type(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["source_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["extracted_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_candidate_id"], ["extracted_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promoted_edge_id"], ["knowledge_edges.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "review_decisions",
        id_column(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reviewer", sa.String(length=160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("applied_by", sa.String(length=160), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("evidence", jsonb_type(), nullable=False),
        sa.Column("metadata", jsonb_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    for table, columns in {
        "source_chunks": ["project_id", "source_id", "chunk_type", "text_hash", "status"],
        "extraction_runs": ["project_id", "agent_run_id", "status"],
        "extracted_candidates": [
            "project_id",
            "extraction_run_id",
            "source_id",
            "source_chunk_id",
            "node_type",
            "status",
            "promoted_node_id",
        ],
        "extracted_candidate_edges": [
            "project_id",
            "extraction_run_id",
            "source_chunk_id",
            "source_candidate_id",
            "target_candidate_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "status",
            "promoted_edge_id",
        ],
        "review_decisions": ["project_id", "decision_type", "target_type", "target_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, columns in {
        "review_decisions": ["project_id", "decision_type", "target_type", "target_id"],
        "extracted_candidate_edges": [
            "project_id",
            "extraction_run_id",
            "source_chunk_id",
            "source_candidate_id",
            "target_candidate_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "status",
            "promoted_edge_id",
        ],
        "extracted_candidates": [
            "project_id",
            "extraction_run_id",
            "source_id",
            "source_chunk_id",
            "node_type",
            "status",
            "promoted_node_id",
        ],
        "extraction_runs": ["project_id", "agent_run_id", "status"],
        "source_chunks": ["project_id", "source_id", "chunk_type", "text_hash", "status"],
    }.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)

    op.drop_table("review_decisions")
    op.drop_table("extracted_candidate_edges")
    op.drop_table("extracted_candidates")
    op.drop_table("extraction_runs")
    op.drop_table("source_chunks")
