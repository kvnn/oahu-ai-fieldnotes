"""Print production constants for O'ahu A.I. Field Notes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
BLEED = "0.125in"

COLOR_SWATCHES: dict[str, dict[str, Any]] = {
    "paper": {
        "hex": "#f6efe3",
        "cmyk": {"c": 0, "m": 0, "y": 0, "k": 0},
        "role": "Warm stock preview only; physical stock supplies the cream surface.",
    },
    "aubergine": {
        "hex": "#2b1244",
        "cmyk": {"c": 80, "m": 95, "y": 40, "k": 55},
        "role": "Single accent ink for title, rules, labels, and state/emphasis.",
    },
    "rich_black": {
        "hex": "#1a1525",
        "cmyk": {"c": 40, "m": 30, "y": 30, "k": 100},
        "role": "Dark fields for cover and chapter opener spreads.",
    },
    "body_black": {
        "hex": "#111111",
        "cmyk": {"c": 0, "m": 0, "y": 0, "k": 100},
        "role": "Body text.",
    },
    "body_black_fallback": {
        "hex": "#272727",
        "cmyk": {"c": 0, "m": 0, "y": 0, "k": 100},
        "role": "Renderer fallback text color mapped to body black.",
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
        "css": margins,
        "colors": COLOR_SWATCHES,
        "pdf_standard_target": "Mixam press-ready PDF",
        "press_ready": False,
        "press_ready_target": True,
        "press_ready_note": (
            "Page-count renders skip press-ready conversion because it does not "
            "change pagination; the final print profile uses a dedicated no-crop "
            "Vivliostyle output."
        ),
        "crop_marks": True,
    }


def render_profile_metadata(profile: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "trim_size": TRIM_SIZE,
        "bleed": BLEED,
        "margins": asdict(PRODUCTION_MARGINS),
        "colors": COLOR_SWATCHES,
        "pdf_standard_target": (
            "Mixam press-ready PDF: CMYK-mapped, single pages, bleed, no crop marks"
            if profile == "print"
            else "draft/proof"
        ),
    }


def proof_output_path() -> Path:
    return Path("dist/oahu-ai-field-notes-proof.pdf")


def print_output_path() -> Path:
    return Path("dist/oahu-ai-field-notes-print.pdf")
