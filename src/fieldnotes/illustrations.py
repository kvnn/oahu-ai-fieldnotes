"""Illustration manifest helpers for print rendering."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Literal

import tomllib


MANIFEST_PATH = Path("design/illustrations/oahu-vol-1.toml")
RENDER_ASSET_PREFIX = "../../"

IllustrationTreatment = Literal["opener_motif", "inline_infographic"]


@dataclass(frozen=True)
class IllustrationSpec:
    id: str
    chapter_slug: str
    asset_path: str
    treatment: IllustrationTreatment
    anchor_text: str = ""
    fallback_placement: str = "after_first_paragraph"
    caption_policy: str = "internal"
    alt_text: str = ""


def load_illustration_manifest(path: Path = MANIFEST_PATH) -> list[IllustrationSpec]:
    """Load the current book illustration manifest."""

    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        IllustrationSpec(
            id=str(item["id"]),
            chapter_slug=str(item["chapter_slug"]),
            asset_path=str(item["asset_path"]),
            treatment=str(item["treatment"]),  # type: ignore[arg-type]
            anchor_text=str(item.get("anchor_text") or ""),
            fallback_placement=str(item.get("fallback_placement") or "after_first_paragraph"),
            caption_policy=str(item.get("caption_policy") or "internal"),
            alt_text=str(item.get("alt_text") or ""),
        )
        for item in data.get("figures", [])
    ]


def illustrations_by_slug(path: Path = MANIFEST_PATH) -> dict[str, IllustrationSpec]:
    return {spec.chapter_slug: spec for spec in load_illustration_manifest(path)}


def opener_motif_for_slug(slug: str) -> str:
    spec = illustrations_by_slug().get(slug)
    if spec is None or spec.treatment != "opener_motif":
        return ""
    return (
        f'<figure class="book-illustration opener-motif" data-illustration-id="{escape(spec.id)}" '
        'aria-hidden="true">'
        f'<img src="{escape(_render_src(spec.asset_path))}" alt="">'
        "</figure>"
    )


def insert_inline_illustration(slug: str, body: str) -> str:
    spec = illustrations_by_slug().get(slug)
    if spec is None or spec.treatment != "inline_infographic":
        return body

    html = _inline_figure_html(spec)
    anchor = spec.anchor_text.strip()
    if anchor and anchor in body:
        insert_at = body.index(anchor) + len(anchor)
        paragraph_end = body.find("\n\n", insert_at)
        if paragraph_end == -1:
            paragraph_end = len(body)
        return body[:paragraph_end].rstrip() + "\n\n" + html + "\n\n" + body[paragraph_end:].lstrip()

    return _insert_at_fallback(spec, body, html)


def _inline_figure_html(spec: IllustrationSpec) -> str:
    return (
        f'<figure class="book-illustration inline-infographic" data-illustration-id="{escape(spec.id)}">'
        f'<img src="{escape(_render_src(spec.asset_path))}" alt="{escape(spec.alt_text)}">'
        "</figure>"
    )


def _insert_at_fallback(spec: IllustrationSpec, body: str, html: str) -> str:
    comment = (
        f'<!-- illustration-anchor-fallback id="{escape(spec.id)}" '
        f'placement="{escape(spec.fallback_placement)}" -->'
    )
    marker = "\n\n---\n\n"
    if spec.fallback_placement == "after_first_section_break" and marker in body:
        head, tail = body.split(marker, 1)
        return f"{head}{marker}{comment}\n{html}\n\n{tail.lstrip()}"

    paragraph_end = body.find("\n\n")
    if paragraph_end == -1:
        paragraph_end = len(body)
    return body[:paragraph_end].rstrip() + "\n\n" + comment + "\n" + html + "\n\n" + body[
        paragraph_end:
    ].lstrip()


def _render_src(asset_path: str) -> str:
    return f"{RENDER_ASSET_PREFIX}{asset_path}"
