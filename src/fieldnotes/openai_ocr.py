"""OpenAI-backed OCR for notebook photos and screenshots."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from fieldnotes.schemas import OCRResult


class OCRUnavailable(RuntimeError):
    pass


class OpenAIOCRClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def transcribe_image(self, path: Path) -> OCRResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OCRUnavailable("openai package is not installed") from exc

        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        image_url = f"data:{mime_type};base64,{encoded}"
        client = OpenAI()
        response = client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a careful OCR engine for notebook photos, "
                                "screenshots, and source material. Transcribe only "
                                "visible text. Preserve line breaks where useful. "
                                "Do not infer missing words; record uncertainty."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract the visible text."},
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "high",
                        },
                    ],
                },
            ],
            text_format=OCRResult,
        )
        parsed = _first_parsed(response)
        if isinstance(parsed, OCRResult):
            return parsed
        return OCRResult.model_validate(parsed)


def _first_parsed(response: Any) -> Any:
    if hasattr(response, "output_parsed") and response.output_parsed is not None:
        return response.output_parsed
    for output in getattr(response, "output", []):
        for item in getattr(output, "content", []):
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return parsed
    raise OCRUnavailable("OpenAI response did not include parsed OCR output")
