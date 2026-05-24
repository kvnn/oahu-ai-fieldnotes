"""Project configuration for the field notes workflow."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from fieldnotes.db.session import DEFAULT_DATABASE_URL


DEFAULT_CONFIG_PATH = Path("fieldnotes.config.toml")


@dataclass(frozen=True)
class WatchRoot:
    path: Path
    source_type: str
    mode: str
    recursive: bool = True
    read_only: bool = True
    label: str = ""


@dataclass(frozen=True)
class OpenAIConfig:
    ocr_model: str = "gpt-4.1"
    extraction_model: str = "gpt-5.5"
    draft_model: str | None = None
    illustration_model: str | None = None


@dataclass(frozen=True)
class ExtractionConfig:
    provider: str = "openai"
    prompt_version: str = "fieldnotes.extraction.v0.1"
    schema_version: str = "fieldnotes.extraction_result.v0.1"
    max_chunk_chars: int = 4000


@dataclass(frozen=True)
class FieldnotesConfig:
    root: Path
    project_slug: str = "oahu-ai-field-notes-vol-1"
    curated_assets_dir: Path = Path("assets/curated")
    vivliostyle_config: Path = Path("vivliostyle.config.js")
    manuscript_dir: Path = Path("manuscript")
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    watch_roots: list[WatchRoot] = field(default_factory=list)
    database_url: str = DEFAULT_DATABASE_URL

    def resolve_path(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return candidate
        return self.root / candidate


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _database_url() -> str:
    return (
        os.getenv("DB_ENGINE_URL")
        or os.getenv("FIELDNOTES_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or DEFAULT_DATABASE_URL
    )


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> FieldnotesConfig:
    root = Path.cwd()
    load_dotenv(root / ".env")

    path = Path(config_path)
    if not path.is_absolute():
        path = root / path

    raw = _read_toml(path)
    openai_raw = raw.get("openai", {})
    extraction_raw = raw.get("extraction", {})

    watch_roots = [
        WatchRoot(
            path=Path(item["path"]),
            source_type=item["source_type"],
            mode=item.get("mode", "text"),
            recursive=bool(item.get("recursive", True)),
            read_only=bool(item.get("read_only", True)),
            label=item.get("label", ""),
        )
        for item in raw.get("watch_roots", [])
    ]

    return FieldnotesConfig(
        root=root,
        project_slug=raw.get("project_slug", "oahu-ai-field-notes-vol-1"),
        curated_assets_dir=Path(raw.get("curated_assets_dir", "assets/curated")),
        vivliostyle_config=Path(raw.get("vivliostyle_config", "vivliostyle.config.js")),
        manuscript_dir=Path(raw.get("manuscript_dir", "manuscript")),
        openai=OpenAIConfig(
            ocr_model=os.getenv("FIELDNOTES_OCR_MODEL")
            or openai_raw.get("ocr_model", "gpt-4.1"),
            extraction_model=os.getenv("FIELDNOTES_EXTRACTION_MODEL")
            or openai_raw.get("extraction_model", "gpt-5.5"),
            draft_model=os.getenv("FIELDNOTES_DRAFT_MODEL")
            or openai_raw.get("draft_model"),
            illustration_model=os.getenv("FIELDNOTES_ILLUSTRATION_MODEL")
            or openai_raw.get("illustration_model"),
        ),
        extraction=ExtractionConfig(
            provider=os.getenv("FIELDNOTES_EXTRACTION_PROVIDER")
            or extraction_raw.get("provider", "openai"),
            prompt_version=extraction_raw.get(
                "prompt_version", "fieldnotes.extraction.v0.1"
            ),
            schema_version=extraction_raw.get(
                "schema_version", "fieldnotes.extraction_result.v0.1"
            ),
            max_chunk_chars=int(extraction_raw.get("max_chunk_chars", 4000)),
        ),
        watch_roots=watch_roots,
        database_url=_database_url(),
    )
