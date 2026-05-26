"""Print production constants for O'ahu A.I. Field Notes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProductionMargins:
    top: str = "0.5in"
    bottom: str = "0.75in"
    inside: str = "0.625in"
    outside: str = "0.875in"


PRODUCTION_MARGINS = ProductionMargins()
TRIM_SIZE = "5.5in,8.5in"
BLEED = "0.13in"
COVER_TRIM_SIZE = "11.18in,8.5in"
COVER_SPINE_WIDTH = "0.18in"
INTERIOR_PAGE_TARGET = 68
BOOK_OUTPUT_FILE_STEM = "oahu-ai-field-notes"
UPLOAD_COVER_FILE = f"01_{BOOK_OUTPUT_FILE_STEM}_front-back-spine-cover.pdf"
UPLOAD_INTERIOR_FILE = f"02_{BOOK_OUTPUT_FILE_STEM}_inner-pages.pdf"

COLOR_SWATCHES: dict[str, dict[str, Any]] = {
    "paper": {
        "hex": "#f1e9d4",
        "cmyk": {"c": 5, "m": 8, "y": 18, "k": 0},
        "role": "Warm cream stock preview for interior pages.",
    },
    "aubergine": {
        "hex": "#6b4488",
        "cmyk": {"c": 48, "m": 65, "y": 0, "k": 47},
        "role": "Single accent ink for title, rules, labels, and state/emphasis.",
    },
    "rich_black": {
        "hex": "#19142a",
        "cmyk": {"c": 40, "m": 52, "y": 0, "k": 84},
        "role": "Dark fields for cover and chapter opener spreads.",
    },
    "body_black": {
        "hex": "#2a2520",
        "cmyk": {"c": 0, "m": 12, "y": 24, "k": 84},
        "role": "Body text.",
    },
    "muted_label": {
        "hex": "#8b8474",
        "cmyk": {"c": 0, "m": 5, "y": 17, "k": 45},
        "role": "Mono caps labels, rules, and cover furniture.",
    },
    "rail_text": {
        "hex": "#463f33",
        "cmyk": {"c": 0, "m": 10, "y": 27, "k": 73},
        "role": "Secondary rail text.",
    },
    "muted_rule": {
        "hex": "#7a7160",
        "cmyk": {"c": 0, "m": 7, "y": 21, "k": 52},
        "role": "Fine rules and quiet furniture.",
    },
    "cream_text": {
        "hex": "#b8af9a",
        "cmyk": {"c": 0, "m": 5, "y": 16, "k": 28},
        "role": "Secondary type on dark plates.",
    },
    "display_cream": {
        "hex": "#e8dfc4",
        "cmyk": {"c": 0, "m": 4, "y": 16, "k": 9},
        "role": "Large cream display type on dark chapter opener plates.",
    },
    "neutral_mid_gray": {
        "hex": "#9a9a9a",
        "cmyk": {"c": 0, "m": 0, "y": 0, "k": 40},
        "role": "Generated neutral gray from print furniture and rendering edges.",
    },
    "neutral_light_gray": {
        "hex": "#eeeeee",
        "cmyk": {"c": 0, "m": 0, "y": 0, "k": 7},
        "role": "Generated light neutral gray from print furniture and rendering edges.",
    },
    "illustration_structure": {
        "hex": "#aba28d",
        "cmyk": {"c": 0, "m": 5, "y": 18, "k": 33},
        "role": "Parchment structure lines, frames, and rails in illustration SVGs.",
    },
    "illustration_artifact": {
        "hex": "#efe6ce",
        "cmyk": {"c": 0, "m": 4, "y": 14, "k": 6},
        "role": "Single cream artifact in each illustration SVG.",
    },
    "illustration_artifact_text": {
        "hex": "#221733",
        "cmyk": {"c": 33, "m": 55, "y": 0, "k": 80},
        "role": "Dark text on the cream illustration artifact.",
    },
    "illustration_emphasis": {
        "hex": "#9b7fbc",
        "cmyk": {"c": 18, "m": 32, "y": 0, "k": 26},
        "role": "Aubergine emphasis, gate, or threshold in illustration SVGs.",
    },
    "illustration_bright_label": {
        "hex": "#c8bfa9",
        "cmyk": {"c": 0, "m": 5, "y": 16, "k": 22},
        "role": "Bright destination labels in illustration SVGs.",
    },
    "illustration_meta": {
        "hex": "#6b5a82",
        "cmyk": {"c": 18, "m": 31, "y": 0, "k": 49},
        "role": "Meta ties and internal captions in illustration SVGs.",
    },
}


def cmyk_override_map() -> list[list[Any]]:
    """Return Vivliostyle-compatible RGB-to-CMYK overrides."""

    return [
        [swatch["hex"], {key: int(value) * 100 for key, value in swatch["cmyk"].items()}]
        for swatch in COLOR_SWATCHES.values()
        if "cmyk" in swatch
    ]


def mixam_page_count_profile() -> dict[str, Any]:
    margins = asdict(PRODUCTION_MARGINS)
    return {
        "id": "mixam-perfect-booklet-5_5x8_5-v3",
        "label": 'Mixam Perfect Booklets 5.5" x 8.5"',
        "trim_size": TRIM_SIZE,
        "bleed": BLEED,
        "cover_trim_size": COVER_TRIM_SIZE,
        "cover_spine_width": COVER_SPINE_WIDTH,
        "interior_page_target": INTERIOR_PAGE_TARGET,
        "css": margins,
        "colors": COLOR_SWATCHES,
        "pdf_standard_target": "Mixam PDF/X-4 upload pair",
        "press_ready": False,
        "press_ready_target": True,
        "press_ready_note": (
            "Vivliostyle's bundled press-ready path targets PDF/X-1a; final "
            "cover and interior artifacts must be verified as PDF/X-4 before upload."
        ),
        "crop_marks": True,
    }


def render_profile_metadata(profile: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "trim_size": TRIM_SIZE,
        "bleed": BLEED,
        "cover_trim_size": COVER_TRIM_SIZE,
        "cover_spine_width": COVER_SPINE_WIDTH,
        "interior_page_target": INTERIOR_PAGE_TARGET,
        "margins": asdict(PRODUCTION_MARGINS),
        "colors": COLOR_SWATCHES,
        "pdf_standard_target": (
            "Mixam PDF/X-4 upload pair: separate cover and interior PDFs"
            if profile == "print"
            else "draft/proof"
        ),
    }


def proof_output_path() -> Path:
    return Path("dist/oahu-ai-field-notes-proof.pdf")


def print_output_path() -> Path:
    return interior_output_path()


def short_datetime_stamp(now: datetime | None = None) -> str:
    value = now or datetime.now()
    return value.strftime("%Y%m%d-%H%M%S")


def print_build_id(now: datetime | None = None) -> str:
    return short_datetime_stamp(now)


def cover_output_path(build_id: str | None = None) -> Path:
    return Path(f"dist/{UPLOAD_COVER_FILE}")


def interior_output_path(build_id: str | None = None) -> Path:
    return Path(f"dist/{UPLOAD_INTERIOR_FILE}")


def print_output_paths(build_id: str) -> dict[str, Path]:
    return {
        "cover": cover_output_path(build_id),
        "interior": interior_output_path(build_id),
    }
