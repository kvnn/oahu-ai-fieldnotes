"""OpenAI-backed SVG candidate generation for the illustration workbench."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field

from fieldnotes.config import FieldnotesConfig
from fieldnotes.illustrations import IllustrationSpec


ILLUSTRATION_SHOTGUN_PROMPT_VERSION = "fieldnotes.illustration_shotgun.v0.1"
ILLUSTRATION_SHOTGUN_SYSTEM_PROMPT = "\n".join(
    [
        (
            "Your task is to generate 5 meaningful but minimal SVG illustrations "
            "for O'ahu A.I. Field Notes Volume 01. You will be provided the "
            "illustration goal, chapter body, current illustration metadata, the "
            "current SVG when one exists, and any previously generated "
            "illustrations for this figure."
        ),
        "",
        (
            "Each illustration should be unique to the chapter, representing a "
            "distinct node on the axis of qualitative symbology. Treat the SVG "
            "as a thinking tool for a printed field-notes book, not decoration."
        ),
        "",
        "Return exactly 5 candidates. Each candidate must include:",
        "- a short title",
        "- a concise axis_node naming the symbolic position it explores",
        "- a concise rationale",
        "- alt text suitable for the book",
        "- one complete, self-contained SVG string",
        "",
        "SVG constraints:",
        (
            "- Use only inline SVG. Do not reference external assets, fonts, "
            "scripts, images, CSS imports, or network URLs."
        ),
        "- Keep the drawing minimal, legible, and print-minded.",
        (
            "- Include role=\"img\", data-figure-system=\"fieldnotes-v1\", a "
            "<title>, and a <desc>."
        ),
        (
            "- Prefer a viewBox of \"0 0 1200 800\" for body figures and "
            "\"0 0 800 800\" for opener motifs."
        ),
        (
            "- Use transparent SVG backgrounds. The workbench and print CSS "
            "own the page surface and dark plates."
        ),
        (
            "- opener_motif: design for a dark aubergine CSS background "
            "(#19142a), but do not include #19142a or a full-canvas background "
            "shape in the SVG. Use #aba28d, #c8bfa9, #efe6ce, and #9b7fbc "
            "for visible motif marks."
        ),
        (
            "- inline_infographic: design for a cream paper CSS background. "
            "Use #221733 for ink, #9b7fbc for emphasis, and restrained support "
            "from #aba28d, #c8bfa9, #6b5a82, and #8b8474."
        ),
        (
            "- Use #efe6ce as artifact fill only, not as a full SVG page "
            "background."
        ),
        (
            "- Avoid literal logos, interface screenshots, photorealism, "
            "clutter, and generic AI symbols unless the chapter context makes "
            "them meaningfully specific."
        ),
    ]
)


class IllustrationGenerationUnavailable(RuntimeError):
    """Raised when the OpenAI-backed candidate generator cannot run."""


class GeneratedSvgCandidate(BaseModel):
    title: str = Field(description="Short display title for this SVG candidate.")
    axis_node: str = Field(description="The symbolic position this candidate explores.")
    rationale: str = Field(description="Why this candidate fits the chapter and goal.")
    alt_text: str = Field(description="Accessible alt text for the SVG.")
    svg_text: str = Field(description="Complete, self-contained SVG XML.")


class GeneratedSvgBatch(BaseModel):
    candidates: list[GeneratedSvgCandidate] = Field(
        min_length=5,
        max_length=5,
        description="Exactly five distinct SVG illustration candidates.",
    )


def illustration_generation_model(config: FieldnotesConfig) -> str:
    """Return the configured model for SVG candidate generation."""

    return (
        config.openai.illustration_model
        or config.openai.draft_model
        or config.openai.extraction_model
    )


def generate_svg_candidates(
    config: FieldnotesConfig,
    *,
    illustration: IllustrationSpec,
    chapter_title: str,
    chapter_subtitle: str,
    chapter_body: str,
    generation_goal: str,
    current_svg: str = "",
    previous_candidates: Sequence[Mapping[str, str]] = (),
) -> GeneratedSvgBatch:
    """Generate a batch of five SVG candidates from chapter context."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise IllustrationGenerationUnavailable("openai package is not installed") from exc

    model = illustration_generation_model(config)
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
                            "text": ILLUSTRATION_SHOTGUN_SYSTEM_PROMPT,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _generation_user_prompt(
                                illustration=illustration,
                                chapter_title=chapter_title,
                                chapter_subtitle=chapter_subtitle,
                                chapter_body=chapter_body,
                                generation_goal=generation_goal,
                                current_svg=current_svg,
                                previous_candidates=previous_candidates,
                            ),
                        }
                    ],
                },
            ],
            text_format=GeneratedSvgBatch,
        )
    except Exception as exc:
        raise IllustrationGenerationUnavailable(
            f"OpenAI illustration generation failed: {exc}"
        ) from exc

    parsed = _first_parsed(response)
    if isinstance(parsed, GeneratedSvgBatch):
        return parsed
    return GeneratedSvgBatch.model_validate(parsed)


def _generation_user_prompt(
    *,
    illustration: IllustrationSpec,
    chapter_title: str,
    chapter_subtitle: str,
    chapter_body: str,
    generation_goal: str,
    current_svg: str,
    previous_candidates: Sequence[Mapping[str, str]],
) -> str:
    prior_sections = []
    for index, candidate in enumerate(previous_candidates, start=1):
        prior_sections.append(
            "\n".join(
                [
                    f"Previous candidate {index}:",
                    f"Title: {candidate.get('title', '')}",
                    f"Axis node: {candidate.get('axis_node', '')}",
                    f"Rationale: {candidate.get('rationale', '')}",
                    "SVG:",
                    candidate.get("svg_text", ""),
                ]
            ).strip()
        )

    prior_text = "\n\n".join(prior_sections) if prior_sections else "None yet."
    subtitle = chapter_subtitle.strip() or "(none)"
    goal = generation_goal.strip() or illustration.alt_text or "Find a meaningful visual form."

    return (
        f"Book: O'ahu A.I. Field Notes Volume 01\n"
        f"Chapter title: {chapter_title}\n"
        f"Chapter subtitle: {subtitle}\n"
        f"Chapter slug: {illustration.chapter_slug}\n"
        f"Illustration id: {illustration.id}\n"
        f"Treatment: {illustration.treatment}\n"
        f"Placement: {illustration.placement}\n"
        f"Treatment color contract: {_treatment_color_contract(illustration)}\n"
        f"Illustration goal: {goal}\n\n"
        f"Current SVG:\n{current_svg.strip() or 'None.'}\n\n"
        f"Previously generated illustrations:\n{prior_text}\n\n"
        f"Full chapter body:\n{chapter_body.strip()}"
    )


def _treatment_color_contract(illustration: IllustrationSpec) -> str:
    if illustration.treatment == "opener_motif":
        return (
            "Transparent opener motif for a dark aubergine CSS plate (#19142a). "
            "Do not draw a background rect or hardcode #19142a. Favor parchment, "
            "cream artifact, and restrained aubergine emphasis marks that remain "
            "legible on the dark plate."
        )
    return (
        "Transparent inline infographic for a cream paper CSS surface. Do not "
        "draw a full-page cream background; use dark ink, muted structure, and "
        "one restrained aubergine emphasis moment."
    )


def _first_parsed(response: Any) -> Any:
    if hasattr(response, "output_parsed") and response.output_parsed is not None:
        return response.output_parsed
    for output in getattr(response, "output", []):
        for item in getattr(output, "content", []):
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return parsed
    raise IllustrationGenerationUnavailable(
        "OpenAI response did not include parsed SVG candidates"
    )
