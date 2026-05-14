"""Review actions for promoting extracted candidates into the canonical graph."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldnotes.db.models import (
    CandidateStatus,
    ChapterBrief,
    ChapterBriefNode,
    ChunkStatus,
    ExtractedCandidate,
    KnowledgeNode,
    KnowledgeStatus,
    NodeSourceLink,
    ReviewDecision,
    ReviewDecisionType,
    ReviewTargetType,
    SourceChunk,
)


def _uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _review_decision(
    *,
    candidate: ExtractedCandidate,
    decision_type: str,
    decision: str,
    reviewer: str,
    rationale: str | None,
    applied_by: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        project_id=candidate.project_id,
        decision_type=decision_type,
        target_type=ReviewTargetType.EXTRACTED_CANDIDATE.value,
        target_id=candidate.id,
        decision=decision,
        reviewer=reviewer,
        rationale=rationale,
        applied_by=applied_by,
        evidence=evidence or {},
    )


def get_candidate(session: Session, candidate_id: UUID | str) -> ExtractedCandidate:
    candidate = session.get(ExtractedCandidate, _uuid(candidate_id))
    if candidate is None:
        raise ValueError(f"unknown extracted candidate: {candidate_id}")
    return candidate


def get_source_chunk(session: Session, chunk_id: UUID | str) -> SourceChunk:
    chunk = session.get(SourceChunk, _uuid(chunk_id))
    if chunk is None:
        raise ValueError(f"unknown source chunk: {chunk_id}")
    return chunk


def _source_chunk_decision(
    *,
    chunk: SourceChunk,
    decision_type: str,
    decision: str,
    reviewer: str,
    rationale: str | None,
    evidence: dict[str, Any] | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        project_id=chunk.project_id,
        decision_type=decision_type,
        target_type=ReviewTargetType.SOURCE_CHUNK.value,
        target_id=chunk.id,
        decision=decision,
        reviewer=reviewer,
        rationale=rationale,
        evidence=evidence or {},
    )


def keep_source_chunk(
    session: Session,
    chunk_id: UUID | str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
) -> SourceChunk:
    chunk = get_source_chunk(session, chunk_id)
    if chunk.status == ChunkStatus.DISCARDED.value:
        chunk.status = ChunkStatus.READY.value
    session.add(
        _source_chunk_decision(
            chunk=chunk,
            decision_type=ReviewDecisionType.NOTE.value,
            decision="kept",
            reviewer=reviewer,
            rationale=rationale,
            evidence={
                "source_id": str(chunk.source_id),
                "chunk_index": chunk.chunk_index,
                "status": chunk.status,
            },
        )
    )
    session.flush()
    return chunk


def discard_source_chunk(
    session: Session,
    chunk_id: UUID | str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
) -> SourceChunk:
    chunk = get_source_chunk(session, chunk_id)
    chunk.status = ChunkStatus.DISCARDED.value
    session.add(
        _source_chunk_decision(
            chunk=chunk,
            decision_type=ReviewDecisionType.REJECT.value,
            decision=ChunkStatus.DISCARDED.value,
            reviewer=reviewer,
            rationale=rationale,
            evidence={
                "source_id": str(chunk.source_id),
                "chunk_index": chunk.chunk_index,
            },
        )
    )
    session.flush()
    return chunk


def promote_candidate(
    session: Session,
    candidate_id: UUID | str,
    *,
    reviewer: str = "human",
    chapter_brief_id: UUID | str | None = None,
    rationale: str | None = None,
    section_key: str = "field_note",
) -> KnowledgeNode:
    """Promote a reviewed extracted candidate into a canonical knowledge node."""

    candidate = get_candidate(session, candidate_id)
    if candidate.promoted_node is not None:
        node = candidate.promoted_node
    else:
        node = KnowledgeNode(
            project_id=candidate.project_id,
            node_type=candidate.node_type,
            title=candidate.title,
            body=candidate.body,
            confidence=candidate.confidence_score,
            status=KnowledgeStatus.ACCEPTED.value,
            node_metadata={
                "extracted_candidate_id": str(candidate.id),
                "source_chunk_id": str(candidate.source_chunk_id),
                "extraction_run_id": str(candidate.extraction_run_id),
                "tags": candidate.candidate_metadata.get("tags", []),
                "review_rationale": rationale,
            },
        )
        session.add(node)
        session.flush()

        locator_data = dict(candidate.source_chunk.locator_data or {})
        locator_data["source_chunk_id"] = str(candidate.source_chunk_id)
        session.add(
            NodeSourceLink(
                node=node,
                source=candidate.source,
                locator_type=candidate.source_chunk.locator_type,
                locator_data=locator_data,
                quote=candidate.evidence_quote,
                excerpt=candidate.evidence_quote or candidate.body[:500],
                relevance_score=candidate.reuse_score,
                confidence_score=candidate.confidence_score,
                link_metadata={
                    "created_from": "extracted_candidate",
                    "extracted_candidate_id": str(candidate.id),
                },
            )
        )
        candidate.promoted_node = node

    candidate.status = CandidateStatus.PROMOTED.value
    session.add(
        _review_decision(
            candidate=candidate,
            decision_type=ReviewDecisionType.PROMOTE.value,
            decision=CandidateStatus.PROMOTED.value,
            reviewer=reviewer,
            rationale=rationale,
            evidence={
                "promoted_node_id": str(node.id),
                "source_chunk_id": str(candidate.source_chunk_id),
            },
        )
    )

    if chapter_brief_id is not None:
        link_candidate_to_chapter(
            session,
            candidate.id,
            chapter_brief_id,
            reviewer=reviewer,
            rationale=rationale,
            section_key=section_key,
            promote_if_needed=False,
        )

    session.flush()
    return node


def reject_candidate(
    session: Session,
    candidate_id: UUID | str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
) -> ExtractedCandidate:
    candidate = get_candidate(session, candidate_id)
    candidate.status = CandidateStatus.REJECTED.value
    session.add(
        _review_decision(
            candidate=candidate,
            decision_type=ReviewDecisionType.REJECT.value,
            decision=CandidateStatus.REJECTED.value,
            reviewer=reviewer,
            rationale=rationale,
        )
    )
    session.flush()
    return candidate


def link_candidate_to_chapter(
    session: Session,
    candidate_id: UUID | str,
    chapter_brief_id: UUID | str,
    *,
    reviewer: str = "human",
    rationale: str | None = None,
    section_key: str = "field_note",
    promote_if_needed: bool = True,
) -> ChapterBriefNode:
    candidate = get_candidate(session, candidate_id)
    if promote_if_needed or candidate.promoted_node is None:
        node = promote_candidate(
            session,
            candidate.id,
            reviewer=reviewer,
            rationale=rationale,
            section_key=section_key,
        )
    else:
        node = candidate.promoted_node

    chapter_brief = session.get(ChapterBrief, _uuid(chapter_brief_id))
    if chapter_brief is None:
        raise ValueError(f"unknown chapter brief: {chapter_brief_id}")
    if chapter_brief.project_id != candidate.project_id:
        raise ValueError("candidate and chapter brief belong to different projects")

    existing = session.scalar(
        select(ChapterBriefNode).where(
            ChapterBriefNode.chapter_brief_id == chapter_brief.id,
            ChapterBriefNode.node_id == node.id,
        )
    )
    if existing is not None:
        link = existing
    else:
        link = ChapterBriefNode(
            chapter_brief=chapter_brief,
            node=node,
            section_key=section_key,
            relevance_score=candidate.reuse_score,
        )
        session.add(link)

    session.add(
        _review_decision(
            candidate=candidate,
            decision_type=ReviewDecisionType.LINK_TO_CHAPTER.value,
            decision="linked",
            reviewer=reviewer,
            rationale=rationale,
            evidence={
                "chapter_brief_id": str(chapter_brief.id),
                "knowledge_node_id": str(node.id),
                "section_key": section_key,
            },
        )
    )
    session.flush()
    return link
