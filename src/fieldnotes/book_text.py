"""Draft-backed chapter text helpers for the Book Text panel."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from fieldnotes.config import FieldnotesConfig
from fieldnotes.db.models import ChapterBrief


RewriteMode = Literal["simplify", "expound", "rewrite"]


class BookRewriteUnavailable(RuntimeError):
    pass


class BookRewriteResult(BaseModel):
    rewritten_text: str = Field(
        description="Replacement Markdown for the selected block only."
    )


@dataclass(frozen=True)
class BookChunk:
    id: str
    index: int
    kind: str
    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
ORDERED_LIST_RE = re.compile(r"^\s*\d+[.)]\s+")


def build_brief_skeleton(brief: ChapterBrief) -> str:
    """Create a readable first draft surface from chapter brief fields."""

    lines: list[str] = [f"# {brief.title.strip()}"]
    if brief.subtitle:
        lines.extend(["", f"*{brief.subtitle.strip()}*"])

    sections = [
        ("Situation", brief.situation),
        ("Constraint", brief.constraint),
        ("Build", brief.build),
        ("Pattern", brief.pattern),
        ("O'ahu Layer", brief.oahu_layer),
        ("Field Note", brief.field_note),
        ("Next Build", brief.next_build),
    ]
    for label, value in sections:
        if value and value.strip():
            lines.extend(["", f"## {label}", "", value.strip()])

    metadata = dict(brief.brief_metadata or {})
    description = metadata.get("description")
    if description and str(description).strip():
        lines.extend(["", "## Brief", "", str(description).strip()])

    if len(lines) == 1 or (len(lines) == 3 and brief.subtitle):
        fallback = brief.field_note or brief.situation or "Draft from this chapter brief."
        lines.extend(["", "## Field Note", "", fallback.strip()])

    return "\n".join(lines).strip() + "\n"


def split_markdown_chunks(body: str) -> list[BookChunk]:
    """Split Markdown into editable blocks while preserving offsets."""

    text = _normalize_newlines(body)
    if not text.strip():
        return []

    chunks: list[BookChunk] = []
    current_start: int | None = None
    in_fence: str | None = None
    offset = 0

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        is_blank = stripped == ""

        if current_start is None:
            if is_blank:
                offset += len(line)
                continue
            current_start = offset
        elif is_blank and in_fence is None:
            _append_chunk(chunks, text, current_start, offset)
            current_start = None
            offset += len(line)
            continue

        marker = _fence_marker(line)
        if marker:
            if in_fence == marker:
                in_fence = None
            elif in_fence is None:
                in_fence = marker
        offset += len(line)

    if current_start is not None:
        _append_chunk(chunks, text, current_start, len(text))

    return chunks


def chunk_by_id(body: str, chunk_id: str) -> BookChunk | None:
    return next((chunk for chunk in split_markdown_chunks(body) if chunk.id == chunk_id), None)


def replace_chunk(body: str, chunk_id: str, replacement: str) -> str:
    text = _normalize_newlines(body)
    chunk = chunk_by_id(text, chunk_id)
    if chunk is None:
        raise ValueError(f"unknown book chunk: {chunk_id}")
    cleaned = replacement.strip("\n")
    return f"{text[: chunk.start]}{cleaned}{text[chunk.end :]}"


def rewrite_book_chunk(
    config: FieldnotesConfig,
    *,
    chapter_title: str,
    full_body: str,
    chunk: BookChunk,
    mode: RewriteMode,
    instruction: str = "",
) -> BookRewriteResult:
    """Rewrite a selected chapter block with OpenAI."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise BookRewriteUnavailable("openai package is not installed") from exc

    if mode == "rewrite" and not instruction.strip():
        raise ValueError("rewrite mode requires an instruction")

    model = config.openai.draft_model or config.openai.extraction_model
    client = OpenAI()
    try:
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You revise one Markdown block for O'ahu A.I. Field Notes. "
                                "Return only a replacement for the selected block. Preserve "
                                "the block's Markdown role unless the user instruction clearly "
                                "requires otherwise. Keep the book voice concrete, observant, "
                                "specific, and useful."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _rewrite_prompt(
                                chapter_title=chapter_title,
                                full_body=full_body,
                                chunk=chunk,
                                mode=mode,
                                instruction=instruction,
                            ),
                        }
                    ],
                },
            ],
            text_format=BookRewriteResult,
        )
    except Exception as exc:
        raise BookRewriteUnavailable(f"OpenAI rewrite failed: {exc}") from exc
    parsed = _first_parsed(response)
    if isinstance(parsed, BookRewriteResult):
        return parsed
    return BookRewriteResult.model_validate(parsed)


def _rewrite_prompt(
    *,
    chapter_title: str,
    full_body: str,
    chunk: BookChunk,
    mode: RewriteMode,
    instruction: str,
) -> str:
    if mode == "simplify":
        task = (
            "Simplify this block. Preserve meaning, remove needless complexity, "
            "and make the line of thought easier to follow."
        )
    elif mode == "expound":
        task = (
            "Expound this block. Add cogency, specificity, and connective tissue "
            "without turning it into a tutorial or generic AI commentary."
        )
    else:
        task = f"Rewrite this block according to the user's instruction: {instruction.strip()}"

    return (
        f"Chapter: {chapter_title}\n"
        f"Selected block id: {chunk.id}\n"
        f"Selected block kind: {chunk.kind}\n"
        f"Task: {task}\n\n"
        f"Selected block:\n{chunk.text}\n\n"
        f"Full chapter context:\n{full_body[:12000]}"
    )


def _append_chunk(chunks: list[BookChunk], text: str, start: int, end: int) -> None:
    while end > start and text[end - 1] == "\n":
        end -= 1
    raw = text[start:end]
    if not raw.strip():
        return
    chunks.append(
        BookChunk(
            id=f"b{len(chunks):03d}",
            index=len(chunks),
            kind=_block_kind(raw),
            text=raw,
            start=start,
            end=end,
        )
    )


def _block_kind(text: str) -> str:
    stripped = text.lstrip()
    if FENCE_RE.match(stripped):
        return "code"
    if HEADING_RE.match(stripped):
        return "heading"
    if stripped.startswith(">"):
        return "quote"
    if stripped.startswith("- ") or stripped.startswith("* ") or ORDERED_LIST_RE.match(stripped):
        return "list"
    if stripped.startswith("<") and stripped.endswith(">"):
        return "html"
    return "paragraph"


def _fence_marker(line: str) -> str | None:
    match = FENCE_RE.match(line)
    return match.group(1) if match else None


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _first_parsed(response: Any) -> Any:
    if hasattr(response, "output_parsed") and response.output_parsed is not None:
        return response.output_parsed
    for output in getattr(response, "output", []):
        for item in getattr(output, "content", []):
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return parsed
    raise BookRewriteUnavailable("OpenAI response did not include parsed rewrite output")
