"""Source scanning, chunking, and OCR helpers."""

from __future__ import annotations

import hashlib
import mimetypes
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldnotes.config import FieldnotesConfig, WatchRoot
from fieldnotes.db.models import (
    ChunkStatus,
    LocatorType,
    Project,
    SourceChunk,
    SourceChunkType,
    SourceMaterial,
    SourceStatus,
    SourceType,
)
from fieldnotes.openai_ocr import OpenAIOCRClient, OCRUnavailable


TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".sql",
    ".csv",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}
REPO_SUMMARY_FILES = {
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    "package.json",
    "vivliostyle.config.js",
}


@dataclass(frozen=True)
class IngestStats:
    sources_seen: int = 0
    sources_created: int = 0
    chunks_created: int = 0
    chunks_updated: int = 0
    blocked_images: int = 0
    errors: tuple[str, ...] = ()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_pdf_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {path}")
    return result.stdout


def chunk_text(text: str, max_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    current = ""
    for paragraph in cleaned.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph.strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph.strip()
        else:
            chunks.extend(
                paragraph[index : index + max_chars]
                for index in range(0, len(paragraph), max_chars)
            )
            current = ""
    if current:
        chunks.append(current)
    return chunks


def source_type_for_path(path: Path, watch_root: WatchRoot) -> str:
    if watch_root.source_type:
        return watch_root.source_type
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return SourceType.SCREENSHOT.value
    if suffix in PDF_EXTENSIONS:
        return SourceType.UPLOADED_DOCUMENT.value
    return SourceType.FILE_PATH.value


def chunk_type_for_path(path: Path, watch_root: WatchRoot) -> str:
    suffix = path.suffix.lower()
    if watch_root.mode == "repo_summary":
        return SourceChunkType.REPO_SUMMARY.value
    if suffix in IMAGE_EXTENSIONS:
        return SourceChunkType.OCR_PAGE.value
    if suffix in PDF_EXTENSIONS:
        return SourceChunkType.PDF_PAGE.value
    if "transcript" in watch_root.mode or "transcript" in path.name.lower():
        return SourceChunkType.TRANSCRIPT_SEGMENT.value
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".sql"}:
        return SourceChunkType.CODE_SNIPPET.value
    return SourceChunkType.TEXT.value


def iter_watch_files(config: FieldnotesConfig) -> list[tuple[Path, WatchRoot]]:
    found: list[tuple[Path, WatchRoot]] = []
    for root in config.watch_roots:
        resolved = config.resolve_path(root.path)
        if not resolved.exists():
            continue
        if root.mode == "repo_summary" and resolved.is_dir():
            for name in sorted(REPO_SUMMARY_FILES):
                candidate = resolved / name
                if candidate.exists() and candidate.is_file():
                    found.append((candidate, root))
            continue
        if resolved.is_file():
            found.append((resolved, root))
            continue
        pattern = "**/*" if root.recursive else "*"
        for path in sorted(resolved.glob(pattern)):
            if path.is_file() and path.name != ".gitkeep":
                found.append((path, root))
    return found


def get_or_create_source(
    session: Session,
    project: Project,
    path: Path,
    watch_root: WatchRoot,
) -> tuple[SourceMaterial, bool]:
    location = str(path)
    digest = file_hash(path)
    source = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.project_id == project.id,
            SourceMaterial.location == location,
        )
    )
    created = source is None
    if source is None:
        source = SourceMaterial(project=project, location=location)
        session.add(source)
    source.source_type = source_type_for_path(path, watch_root)
    source.title = path.name
    source.content_hash = digest
    source.status = SourceStatus.ACTIVE.value
    source.provenance = {
        "watch_root": str(watch_root.path),
        "watch_root_label": watch_root.label,
        "mode": watch_root.mode,
        "read_only": watch_root.read_only,
    }
    source.source_metadata = {
        "mime_type": mimetypes.guess_type(path.name)[0],
        "size_bytes": path.stat().st_size,
        "context_label": watch_root.label,
    }
    return source, created


def upsert_chunk(
    session: Session,
    project: Project,
    source: SourceMaterial,
    *,
    chunk_index: int,
    chunk_type: str,
    text: str,
    title: str | None,
    locator_type: str | None,
    locator_data: dict,
    status: str = ChunkStatus.READY.value,
    ocr_engine: str | None = None,
    ocr_confidence: float | None = None,
    uncertainty_notes: str | None = None,
) -> tuple[SourceChunk, bool]:
    chunk = session.scalar(
        select(SourceChunk).where(
            SourceChunk.source_id == source.id,
            SourceChunk.chunk_index == chunk_index,
        )
    )
    created = chunk is None
    if chunk is None:
        chunk = SourceChunk(
            project=project,
            source=source,
            chunk_index=chunk_index,
            chunk_type=chunk_type,
            text_hash=text_hash(text),
        )
        session.add(chunk)
    chunk.chunk_type = chunk_type
    chunk.title = title
    chunk.text = text
    chunk.text_hash = text_hash(text)
    chunk.locator_type = locator_type
    chunk.locator_data = locator_data
    chunk.status = status
    chunk.ocr_engine = ocr_engine
    chunk.ocr_confidence = ocr_confidence
    chunk.uncertainty_notes = uncertainty_notes
    return chunk, created


def chunks_for_file(
    path: Path,
    watch_root: WatchRoot,
    config: FieldnotesConfig,
    *,
    run_ocr: bool,
    ocr_client: OpenAIOCRClient | None,
) -> tuple[list[dict], int]:
    suffix = path.suffix.lower()
    chunk_type = chunk_type_for_path(path, watch_root)

    if suffix in IMAGE_EXTENSIONS:
        if not run_ocr:
            return (
                [
                    {
                        "text": "",
                        "status": ChunkStatus.NEEDS_OCR.value,
                        "title": path.name,
                        "locator_type": LocatorType.IMAGE_REGION.value,
                        "locator_data": {"path": str(path)},
                        "ocr_engine": None,
                        "ocr_confidence": None,
                        "uncertainty_notes": "OCR required before extraction.",
                    }
                ],
                1,
            )
        if ocr_client is None:
            raise OCRUnavailable("OpenAI OCR client is not configured")
        result = ocr_client.transcribe_image(path)
        return (
            [
                {
                    "text": result.text,
                    "status": ChunkStatus.READY.value if result.text.strip() else ChunkStatus.BLOCKED.value,
                    "title": path.name,
                    "locator_type": LocatorType.IMAGE_REGION.value,
                    "locator_data": {
                        "path": str(path),
                        "visible_regions": result.visible_regions,
                    },
                    "ocr_engine": f"openai:{ocr_client.model}",
                    "ocr_confidence": result.confidence_score,
                    "uncertainty_notes": result.uncertainty_notes,
                }
            ],
            0,
        )

    if suffix in PDF_EXTENSIONS:
        text = extract_pdf_text(path)
        locator_type = LocatorType.PAGE_NUMBER.value
    else:
        text = read_text(path)
        locator_type = LocatorType.OBJECT_PATH.value

    return (
        [
            {
                "text": chunk,
                "status": ChunkStatus.READY.value,
                "title": f"{path.name} #{index + 1}",
                "locator_type": locator_type,
                "locator_data": {"path": str(path), "chunk_index": index},
                "ocr_engine": None,
                "ocr_confidence": None,
                "uncertainty_notes": None,
            }
            for index, chunk in enumerate(chunk_text(text, config.extraction.max_chunk_chars))
        ],
        0,
    )


def ingest_sources(
    session: Session,
    config: FieldnotesConfig,
    project: Project,
    *,
    run_ocr: bool = True,
) -> IngestStats:
    ocr_client = OpenAIOCRClient(config.openai.ocr_model) if run_ocr else None
    stats = {
        "sources_seen": 0,
        "sources_created": 0,
        "chunks_created": 0,
        "chunks_updated": 0,
        "blocked_images": 0,
        "errors": [],
    }

    for path, watch_root in iter_watch_files(config):
        stats["sources_seen"] += 1
        try:
            source, created_source = get_or_create_source(session, project, path, watch_root)
            session.flush()
            if created_source:
                stats["sources_created"] += 1
            chunk_payloads, blocked_images = chunks_for_file(
                path, watch_root, config, run_ocr=run_ocr, ocr_client=ocr_client
            )
            stats["blocked_images"] += blocked_images
            chunk_type = chunk_type_for_path(path, watch_root)
            for index, payload in enumerate(chunk_payloads):
                _, created_chunk = upsert_chunk(
                    session,
                    project,
                    source,
                    chunk_index=index,
                    chunk_type=chunk_type,
                    text=payload["text"],
                    title=payload["title"],
                    locator_type=payload["locator_type"],
                    locator_data=payload["locator_data"],
                    status=payload["status"],
                    ocr_engine=payload["ocr_engine"],
                    ocr_confidence=payload["ocr_confidence"],
                    uncertainty_notes=payload["uncertainty_notes"],
                )
                if created_chunk:
                    stats["chunks_created"] += 1
                else:
                    stats["chunks_updated"] += 1
        except Exception as exc:
            stats["errors"].append(f"{path}: {exc}")

    return IngestStats(
        sources_seen=stats["sources_seen"],
        sources_created=stats["sources_created"],
        chunks_created=stats["chunks_created"],
        chunks_updated=stats["chunks_updated"],
        blocked_images=stats["blocked_images"],
        errors=tuple(stats["errors"]),
    )
