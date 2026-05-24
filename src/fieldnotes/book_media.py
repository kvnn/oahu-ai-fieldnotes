"""Raster/static book media manifest helpers for print rendering."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Literal

import tomllib


MANIFEST_PATH = Path("design/media/oahu-vol-1.toml")
RENDER_ASSET_PREFIX = "../../"

BookMediaSlot = Literal["opener", "cover_front"]
BookMediaTreatment = Literal["opener_image", "cover_image"]
BookMediaPosition = Literal["bottom_right", "title_adjacent", "center_low"]
BookMediaScale = Literal["small", "medium", "large"]

BOOK_MEDIA_SLOTS: tuple[str, ...] = ("opener", "cover_front")
BOOK_MEDIA_TREATMENTS: tuple[str, ...] = ("opener_image", "cover_image")
BOOK_MEDIA_POSITIONS: tuple[str, ...] = ("bottom_right", "title_adjacent", "center_low")
BOOK_MEDIA_SCALES: tuple[str, ...] = ("small", "medium", "large")


@dataclass(frozen=True)
class BookMediaSpec:
    id: str
    chapter_slug: str
    asset_path: str
    slot: BookMediaSlot
    treatment: BookMediaTreatment
    enabled: bool = True
    position: BookMediaPosition = "bottom_right"
    scale: BookMediaScale = "medium"
    decorative: bool = True
    alt_text: str = ""


def load_book_media_manifest(path: Path = MANIFEST_PATH) -> list[BookMediaSpec]:
    """Load static/raster media intended for print placement."""

    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        BookMediaSpec(
            id=str(item["id"]),
            chapter_slug=str(item["chapter_slug"]),
            asset_path=str(item["asset_path"]),
            slot=_slot_value(item),
            treatment=_treatment_value(item),
            enabled=_bool_value(item.get("enabled"), default=True),
            position=_position_value(item),
            scale=_scale_value(item),
            decorative=_bool_value(item.get("decorative"), default=True),
            alt_text=str(item.get("alt_text") or ""),
        )
        for item in data.get("media", [])
    ]


def enabled_book_media_by_slug(path: Path = MANIFEST_PATH) -> dict[str, list[BookMediaSpec]]:
    grouped: dict[str, list[BookMediaSpec]] = {}
    for spec in load_book_media_manifest(path):
        if not spec.enabled:
            continue
        grouped.setdefault(spec.chapter_slug, []).append(spec)
    return grouped


def opener_media_for_slug(slug: str, path: Path = MANIFEST_PATH) -> str:
    specs = enabled_book_media_by_slug(path).get(slug, [])
    return "\n".join(_opener_media_html(spec) for spec in specs if spec.slot == "opener")


def cover_media_for_slot(slot: BookMediaSlot, path: Path = MANIFEST_PATH) -> list[BookMediaSpec]:
    return [spec for spec in load_book_media_manifest(path) if spec.enabled and spec.slot == slot]


def _opener_media_html(spec: BookMediaSpec) -> str:
    treatment_class = escape(spec.treatment.replace("_", "-"))
    alt = "" if spec.decorative else spec.alt_text
    hidden = ' aria-hidden="true"' if spec.decorative else ""
    return (
        f'<figure class="book-media opener-media {treatment_class} '
        f'media-position-{escape(spec.position)} media-scale-{escape(spec.scale)}" '
        f'data-media-id="{escape(spec.id)}" data-media-slot="{escape(spec.slot)}"{hidden}>'
        f'<img src="{escape(_render_src(spec.asset_path))}" alt="{escape(alt)}">'
        "</figure>"
    )


def _render_src(asset_path: str) -> str:
    return f"{RENDER_ASSET_PREFIX}{asset_path}"


def _slot_value(item: dict) -> BookMediaSlot:
    value = str(item.get("slot") or "").strip()
    if value in BOOK_MEDIA_SLOTS:
        return value  # type: ignore[return-value]
    return "opener"


def _treatment_value(item: dict) -> BookMediaTreatment:
    value = str(item.get("treatment") or "").strip()
    if value in BOOK_MEDIA_TREATMENTS:
        return value  # type: ignore[return-value]
    return "opener_image"


def _position_value(item: dict) -> BookMediaPosition:
    value = str(item.get("position") or "").strip()
    if value in BOOK_MEDIA_POSITIONS:
        return value  # type: ignore[return-value]
    return "bottom_right"


def _scale_value(item: dict) -> BookMediaScale:
    value = str(item.get("scale") or "").strip()
    if value in BOOK_MEDIA_SCALES:
        return value  # type: ignore[return-value]
    return "medium"


def _bool_value(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}
