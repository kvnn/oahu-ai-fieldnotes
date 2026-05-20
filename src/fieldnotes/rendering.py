"""Shared Vivliostyle render profile helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fieldnotes.db.models import (
    BookVolume,
    Project,
    RenderOutputType,
    RenderStatus,
    RenderedOutput,
    utc_now,
)
from fieldnotes.production import (
    BLEED,
    TRIM_SIZE,
    print_output_path,
    proof_output_path,
    render_profile_metadata,
)


RenderProfile = Literal["draft", "proof", "print"]


@dataclass(frozen=True)
class BookPdfRenderResult:
    profile: RenderProfile
    output_path: Path
    commands: list[list[str]]
    logs: str
    returncode: int
    metadata: dict

    @property
    def status(self) -> str:
        return (
            RenderStatus.SUCCEEDED.value
            if self.returncode == 0
            else RenderStatus.FAILED.value
        )


def render_commands(profile: str) -> list[tuple[list[str], Path]]:
    if profile == "draft":
        return [(["npm", "run", "build"], Path("dist/oahu-ai-field-notes.pdf"))]

    proof_command = ["npm", "run", "build:proof"]
    if profile == "proof":
        return [(proof_command, proof_output_path())]

    if profile == "print":
        return [(["npm", "run", "build:print"], print_output_path())]
    raise ValueError(f"unknown render profile: {profile}")


def render_output_type(profile: str) -> str:
    if profile == "print":
        return RenderOutputType.PRINT_READY_PDF.value
    if profile == "proof":
        return RenderOutputType.DRAFT_PDF.value
    return RenderOutputType.PDF.value


def render_book_pdf(root: Path, profile: RenderProfile) -> BookPdfRenderResult:
    logs_parts: list[str] = []
    returncode = 0
    output_path = {
        "draft": Path("dist/oahu-ai-field-notes.pdf"),
        "proof": proof_output_path(),
        "print": print_output_path(),
    }[profile]
    metadata = render_profile_metadata(profile)
    metadata.update(
        {
            "commands": [],
            "returncode": None,
            "profile_note": (
                "Print output is built for Mixam upload as single pages with bleed, "
                "CMYK mapping, and no crop marks."
            ),
            "trim_size": TRIM_SIZE,
            "bleed": BLEED,
        }
    )

    try:
        commands = render_commands(profile)
    except ValueError as exc:
        returncode = 2
        metadata["error"] = str(exc)
    else:
        for command, expected_output in commands:
            metadata["commands"].append(command)
            output_path = expected_output
            result = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            logs_parts.extend(part for part in [result.stdout, result.stderr] if part)
            returncode = result.returncode
            if result.returncode != 0:
                metadata["error"] = f"render command failed: {' '.join(command)}"
                break

    logs = "\n".join(logs_parts)
    metadata["returncode"] = returncode
    metadata["output_path"] = str(output_path)
    return BookPdfRenderResult(
        profile=profile,
        output_path=output_path,
        commands=list(metadata["commands"]),
        logs=logs,
        returncode=returncode,
        metadata=metadata,
    )


def render_database_book_pdf(
    root: Path,
    *,
    markdown: str,
    chapter_refs: list[dict],
    word_count: int,
) -> BookPdfRenderResult:
    output_dir = root / "dist" / "generated-book"
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "book.md"
    markdown_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    relative_markdown_path = markdown_path.relative_to(root)
    output_path = print_output_path()
    command = ["npm", "run", "build:print"]
    metadata = render_profile_metadata("print")
    metadata.update(
        {
            "source": "database",
            "generated_markdown_path": str(relative_markdown_path),
            "chapter_count": len(chapter_refs),
            "word_count": word_count,
            "chapters": chapter_refs,
            "commands": [command],
            "returncode": None,
            "output_path": str(output_path),
            "profile_note": (
                "Print output is built from the database-compiled manuscript shown "
                "in the Book Markdown drawer."
            ),
            "trim_size": TRIM_SIZE,
            "bleed": BLEED,
        }
    )
    if not markdown.strip():
        metadata["returncode"] = 2
        metadata["error"] = "database manuscript is empty"
        return BookPdfRenderResult(
            profile="print",
            output_path=output_path,
            commands=[],
            logs=metadata["error"],
            returncode=2,
            metadata=metadata,
        )

    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    logs = "\n".join(part for part in [result.stdout, result.stderr] if part)
    metadata["returncode"] = result.returncode
    if result.returncode != 0:
        metadata["error"] = f"render command failed: {' '.join(command)}"

    return BookPdfRenderResult(
        profile="print",
        output_path=output_path,
        commands=[command],
        logs=logs,
        returncode=result.returncode,
        metadata=metadata,
    )


def record_book_pdf_render(
    session,
    *,
    project: Project,
    volume: BookVolume | None,
    config_path: Path,
    result: BookPdfRenderResult,
) -> RenderedOutput:
    record = RenderedOutput(
        project=project,
        volume=volume,
        output_type=render_output_type(result.profile),
        renderer="Vivliostyle",
        config_path=str(config_path),
        output_path=str(result.output_path),
        build_logs=result.logs[-20000:],
        status=result.status,
        rendered_at=utc_now(),
        render_metadata=result.metadata,
    )
    session.add(record)
    session.flush()
    return record
