"""Illustration manifest helpers for print rendering."""

from __future__ import annotations

from dataclasses import dataclass
import json
from html import escape
from pathlib import Path
from typing import Literal

import tomllib


MANIFEST_PATH = Path("design/illustrations/oahu-vol-1.toml")
RENDER_ASSET_PREFIX = "../../"

IllustrationTreatment = Literal["opener_motif", "inline_infographic"]
IllustrationPlacement = Literal[
    "after_anchor",
    "before_anchor",
    "after_first_paragraph",
    "after_first_section_break",
]
OpenerPosition = Literal["bottom_right", "title_adjacent", "center_low"]
OpenerScale = Literal["small", "medium", "large"]

ILLUSTRATION_TREATMENTS: tuple[str, ...] = ("opener_motif", "inline_infographic")
ILLUSTRATION_PLACEMENTS: tuple[str, ...] = (
    "after_anchor",
    "before_anchor",
    "after_first_paragraph",
    "after_first_section_break",
)
OPENER_POSITIONS: tuple[str, ...] = ("bottom_right", "title_adjacent", "center_low")
OPENER_SCALES: tuple[str, ...] = ("small", "medium", "large")


@dataclass(frozen=True)
class IllustrationSpec:
    id: str
    chapter_slug: str
    asset_path: str
    treatment: IllustrationTreatment
    enabled: bool = True
    anchor_text: str = ""
    placement: IllustrationPlacement = "after_anchor"
    fallback_placement: str = "after_first_paragraph"
    opener_position: OpenerPosition = "bottom_right"
    opener_scale: OpenerScale = "medium"
    caption_policy: str = "internal"
    alt_text: str = ""
    generation_goal: str = ""


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
            enabled=_bool_value(item.get("enabled"), default=True),
            anchor_text=str(item.get("anchor_text") or ""),
            placement=_placement_value(item),
            fallback_placement=str(item.get("fallback_placement") or "after_first_paragraph"),
            opener_position=str(item.get("opener_position") or "bottom_right"),  # type: ignore[arg-type]
            opener_scale=str(item.get("opener_scale") or "medium"),  # type: ignore[arg-type]
            caption_policy=str(item.get("caption_policy") or "internal"),
            alt_text=str(item.get("alt_text") or ""),
            generation_goal=str(item.get("generation_goal") or ""),
        )
        for item in data.get("figures", [])
    ]


def save_illustration_manifest(
    specs: list[IllustrationSpec],
    path: Path = MANIFEST_PATH,
) -> None:
    """Persist the illustration manifest in a deterministic shape."""

    data = _manifest_top_level(path)
    lines = [
        f'version = {_toml_string(str(data.get("version") or "oahu-vol-1.illustrations.v1"))}',
        f'book_slug = {_toml_string(str(data.get("book_slug") or "oahu-ai-field-notes-vol-1"))}',
        f"figure_count = {len(specs)}",
        "",
    ]
    for index, spec in enumerate(specs):
        if index:
            lines.append("")
        lines.extend(
            [
                "[[figures]]",
                f"id = {_toml_string(spec.id)}",
                f"enabled = {_toml_bool(spec.enabled)}",
                f"chapter_slug = {_toml_string(spec.chapter_slug)}",
                f"asset_path = {_toml_string(spec.asset_path)}",
                f"treatment = {_toml_string(spec.treatment)}",
                f"anchor_text = {_toml_string(spec.anchor_text)}",
                f"placement = {_toml_string(spec.placement)}",
                f"fallback_placement = {_toml_string(spec.fallback_placement)}",
                f"opener_position = {_toml_string(spec.opener_position)}",
                f"opener_scale = {_toml_string(spec.opener_scale)}",
                f"caption_policy = {_toml_string(spec.caption_policy)}",
                f"alt_text = {_toml_string(spec.alt_text)}",
                f"generation_goal = {_toml_string(spec.generation_goal)}",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def illustrations_by_slug(path: Path = MANIFEST_PATH) -> dict[str, IllustrationSpec]:
    return {spec.chapter_slug: spec for spec in load_illustration_manifest(path)}


def enabled_illustrations_by_slug(path: Path = MANIFEST_PATH) -> dict[str, list[IllustrationSpec]]:
    grouped: dict[str, list[IllustrationSpec]] = {}
    for spec in load_illustration_manifest(path):
        if not spec.enabled:
            continue
        grouped.setdefault(spec.chapter_slug, []).append(spec)
    return grouped


def opener_motif_for_slug(slug: str, path: Path = MANIFEST_PATH) -> str:
    return "\n".join(opener_motifs_for_slug(slug, path=path))


def opener_motifs_for_slug(slug: str, path: Path = MANIFEST_PATH) -> list[str]:
    specs = enabled_illustrations_by_slug(path).get(slug, [])
    return [_opener_motif_html(spec) for spec in specs if spec.treatment == "opener_motif"]


def _opener_motif_html(spec: IllustrationSpec) -> str:
    return (
        f'<figure class="book-illustration opener-motif opener-position-{escape(spec.opener_position)} '
        f'opener-scale-{escape(spec.opener_scale)}" data-illustration-id="{escape(spec.id)}" '
        'aria-hidden="true">'
        f'<img src="{escape(_render_src(spec.asset_path))}" alt="">'
        "</figure>"
    )


def insert_inline_illustration(slug: str, body: str, path: Path = MANIFEST_PATH) -> str:
    return insert_inline_illustrations(slug, body, path=path)


def insert_inline_illustrations(
    slug: str,
    body: str,
    path: Path = MANIFEST_PATH,
) -> str:
    specs = enabled_illustrations_by_slug(path).get(slug, [])
    for spec in reversed(specs):
        if spec.treatment != "inline_infographic":
            continue
        body = _insert_inline_illustration(spec, body)
    return body


def _insert_inline_illustration(spec: IllustrationSpec, body: str) -> str:
    html = _inline_figure_html(spec)
    anchor = spec.anchor_text.strip()
    if spec.placement in {"after_anchor", "before_anchor"} and anchor and anchor in body:
        anchor_start = body.index(anchor)
        paragraph_start, paragraph_end = _paragraph_bounds(body, anchor_start)
        if spec.placement == "before_anchor":
            return _insert_at_index(body, paragraph_start, html)
        return _insert_at_index(body, paragraph_end, html)

    if spec.placement == "after_first_section_break":
        return _insert_after_first_section_break(spec, body, html)
    if spec.placement == "after_first_paragraph":
        return _insert_after_first_paragraph(spec, body, html)

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

    return _insert_after_first_paragraph(spec, body, html, comment=comment)


def _insert_after_first_section_break(spec: IllustrationSpec, body: str, html: str) -> str:
    marker = "\n\n---\n\n"
    comment = (
        f'<!-- illustration-placement id="{escape(spec.id)}" '
        'placement="after_first_section_break" -->'
    )
    if marker in body:
        head, tail = body.split(marker, 1)
        return f"{head}{marker}{comment}\n{html}\n\n{tail.lstrip()}"
    return _insert_after_first_paragraph(spec, body, html, comment=comment)


def _insert_after_first_paragraph(
    spec: IllustrationSpec,
    body: str,
    html: str,
    *,
    comment: str | None = None,
) -> str:
    comment = comment or (
        f'<!-- illustration-placement id="{escape(spec.id)}" '
        'placement="after_first_paragraph" -->'
    )
    paragraph_end = body.find("\n\n")
    if paragraph_end == -1:
        paragraph_end = len(body)
    return body[:paragraph_end].rstrip() + "\n\n" + comment + "\n" + html + "\n\n" + body[
        paragraph_end:
    ].lstrip()


def _insert_at_index(body: str, index: int, html: str) -> str:
    if index <= 0:
        return html + "\n\n" + body.lstrip()
    if index >= len(body):
        return body.rstrip() + "\n\n" + html
    return body[:index].rstrip() + "\n\n" + html + "\n\n" + body[index:].lstrip()


def _paragraph_bounds(body: str, index: int) -> tuple[int, int]:
    start = body.rfind("\n\n", 0, index)
    if start == -1:
        paragraph_start = 0
    else:
        paragraph_start = start + 2
    end = body.find("\n\n", index)
    paragraph_end = len(body) if end == -1 else end
    return paragraph_start, paragraph_end


def _render_src(asset_path: str) -> str:
    return f"{RENDER_ASSET_PREFIX}{asset_path}"


def _manifest_top_level(path: Path) -> dict:
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {key: value for key, value in data.items() if key != "figures"}


def _placement_value(item: dict) -> IllustrationPlacement:
    value = str(item.get("placement") or "").strip()
    if value in ILLUSTRATION_PLACEMENTS:
        return value  # type: ignore[return-value]
    return "after_anchor"


def _bool_value(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"
