"""Structured extraction from ready source chunks."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldnotes.config import FieldnotesConfig
from fieldnotes.db.models import (
    CandidateStatus,
    ChunkStatus,
    ExtractedCandidate,
    ExtractedCandidateEdge,
    ExtractionRun,
    ExtractionStatus,
    Project,
    SourceChunk,
    utc_now,
)
from fieldnotes.schemas import FieldnoteExtractionResult


class ExtractionUnavailable(RuntimeError):
    pass


def ready_chunks(session: Session, project: Project, limit: int | None = None) -> list[SourceChunk]:
    statement = (
        select(SourceChunk)
        .where(SourceChunk.project_id == project.id, SourceChunk.status == ChunkStatus.READY.value)
        .order_by(SourceChunk.created_at.asc())
    )
    if limit:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def chunk_has_candidates(session: Session, chunk: SourceChunk) -> bool:
    return (
        session.scalar(
            select(ExtractedCandidate.id)
            .where(ExtractedCandidate.source_chunk_id == chunk.id)
            .limit(1)
        )
        is not None
    )


def local_extract(chunk: SourceChunk) -> FieldnoteExtractionResult:
    text = chunk.text.strip()
    if not text:
        return FieldnoteExtractionResult()
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title = first_line[:120] or chunk.title or "Untitled observation"
    body = text[:900]
    evidence = text[:280]
    return FieldnoteExtractionResult(
        passage_summary=body[:300],
        candidates=[
            {
                "node_type": "observation",
                "title": title,
                "body": body,
                "evidence_quote": evidence,
                "rationale": "Local fallback extraction from a ready source chunk.",
                "confidence_score": 0.55,
                "reuse_score": 0.45,
                "tags": ["local-extraction"],
            }
        ],
    )


def openai_extract(config: FieldnotesConfig, chunk: SourceChunk) -> FieldnoteExtractionResult:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ExtractionUnavailable("openai package is not installed") from exc

    client = OpenAI()
    response = client.responses.parse(
        model=config.openai.extraction_model,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Extract knowledge-to-book candidates from source material for "
                            "O'ahu A.I. Field Notes. Return only grounded observations, "
                            "claims, decisions, patterns, questions, risks, visual ideas, "
                            "and chapter ideas that can help build a printed chapter. "
                            "Do not promote anything to canon."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Source chunk title: {chunk.title or ''}\n"
                            f"Locator: {chunk.locator_data}\n\n{chunk.text}"
                        ),
                    }
                ],
            },
        ],
        text_format=FieldnoteExtractionResult,
    )
    parsed = _first_parsed(response)
    if isinstance(parsed, FieldnoteExtractionResult):
        return parsed
    return FieldnoteExtractionResult.model_validate(parsed)


def _first_parsed(response: Any) -> Any:
    if hasattr(response, "output_parsed") and response.output_parsed is not None:
        return response.output_parsed
    for output in getattr(response, "output", []):
        for item in getattr(output, "content", []):
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return parsed
    raise ExtractionUnavailable("OpenAI response did not include parsed extraction output")


def persist_extraction_result(
    session: Session,
    project: Project,
    run: ExtractionRun,
    chunk: SourceChunk,
    result: FieldnoteExtractionResult,
) -> int:
    created = 0
    title_to_candidate: dict[str, ExtractedCandidate] = {}
    for item in result.candidates:
        candidate = ExtractedCandidate(
            project=project,
            extraction_run=run,
            source=chunk.source,
            source_chunk=chunk,
            node_type=item.node_type,
            title=item.title,
            body=item.body,
            confidence_score=item.confidence_score,
            reuse_score=item.reuse_score,
            evidence_quote=item.evidence_quote,
            rationale=item.rationale,
            raw_output=item.model_dump(),
            status=CandidateStatus.NEEDS_REVIEW.value,
            candidate_metadata={
                "tags": item.tags,
                "passage_summary": result.passage_summary,
                "ambiguity_notes": result.ambiguity_notes,
            },
        )
        session.add(candidate)
        title_to_candidate[item.title] = candidate
        created += 1
    session.flush()

    for edge in result.edges:
        source = title_to_candidate.get(edge.source_title)
        target = title_to_candidate.get(edge.target_title)
        if source is None or target is None:
            continue
        session.add(
            ExtractedCandidateEdge(
                project=project,
                extraction_run=run,
                source_chunk=chunk,
                source_candidate=source,
                target_candidate=target,
                edge_type=edge.edge_type,
                rationale=edge.rationale,
                evidence_quote=edge.evidence_quote,
                strength=edge.strength,
                confidence_score=edge.confidence_score,
                status=CandidateStatus.NEEDS_REVIEW.value,
                edge_metadata=edge.model_dump(),
            )
        )
    return created


def run_extraction(
    session: Session,
    config: FieldnotesConfig,
    project: Project,
    *,
    provider: str | None = None,
    limit: int | None = None,
    include_existing: bool = False,
) -> ExtractionRun:
    provider_name = provider or config.extraction.provider
    model = (
        "local-fallback"
        if provider_name == "local"
        else config.openai.extraction_model
    )
    run = ExtractionRun(
        project=project,
        provider=provider_name,
        model=model,
        prompt_version=config.extraction.prompt_version,
        schema_version=config.extraction.schema_version,
        status=ExtractionStatus.RUNNING.value,
        config={
            "max_chunk_chars": config.extraction.max_chunk_chars,
            "include_existing": include_existing,
        },
        usage={},
        started_at=utc_now(),
    )
    session.add(run)
    session.flush()

    chunks = ready_chunks(session, project, limit=limit)
    processed = 0
    created = 0
    try:
        for chunk in chunks:
            if not include_existing and chunk_has_candidates(session, chunk):
                continue
            result = (
                local_extract(chunk)
                if provider_name == "local"
                else openai_extract(config, chunk)
            )
            processed += 1
            created += persist_extraction_result(session, project, run, chunk, result)
        run.status = ExtractionStatus.SUCCEEDED.value
        run.chunks_count = processed
        run.candidates_count = created
        run.completed_at = utc_now().astimezone(timezone.utc)
    except Exception as exc:
        run.status = ExtractionStatus.FAILED.value
        run.error = str(exc)
        run.chunks_count = processed
        run.candidates_count = created
        run.completed_at = utc_now().astimezone(timezone.utc)
        raise
    return run
