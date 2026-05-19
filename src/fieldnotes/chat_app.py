"""Chainlit chat surface for the Field Notes workbench."""

from __future__ import annotations

import json
from typing import Any

import chainlit as cl


async def collect_chat_context(message: str) -> dict[str, str | dict[str, Any] | None]:
    """Stub for source, chapter, and review-state retrieval."""

    return {
        "message": message,
        "project": "Oahu AI Field Notes",
        "next_hook": "retrieve chapter briefs, source chunks, and review candidates",
        "selected_book_chunk": cl.user_session.get("selected_book_chunk"),
    }


async def run_fieldnotes_assistant(
    message: str,
    context: dict[str, str | dict[str, Any] | None],
) -> str:
    """Stub for the eventual model/tool orchestration layer."""

    if message.startswith("[Book Text]"):
        return (
            "Book Text context received.\n\n"
            "I can use this selection as the active passage for follow-up critique, "
            "source grounding, or a more specific rewrite request. The panel owns "
            "versioned text changes, so any applied rewrite should be reversible "
            "from the draft version controls.\n\n"
            f"{message[:1200]}"
        )

    selected = context.get("selected_book_chunk")
    selected_note = ""
    if isinstance(selected, dict):
        selected_note = (
            "\n\nSelected book chunk: "
            f"{selected.get('chapter_title')} / {selected.get('chunk_id')}"
        )

    return (
        "The Field Notes assistant panel is wired to Chainlit, but its "
        "retrieval and generation hooks are still stubs.\n\n"
        f"Received: {message}\n\n"
        "Next hooks to implement: load active chapter context, surface candidate "
        "source material, draft or revise manuscript sections, and record review "
        f"actions back into the workbench.{selected_note}"
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("fieldnotes_chat_ready", True)
    await cl.Message(
        content=(
            "Field Notes assistant ready. Ask about chapter briefs, source "
            "material, review candidates, or draft revisions."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    if getattr(message, "type", None) == "system_message":
        await handle_system_message(message)
        return

    context = await collect_chat_context(message.content)
    response = await run_fieldnotes_assistant(message.content, context)
    await cl.Message(content=response).send()


async def handle_system_message(message: cl.Message) -> None:
    try:
        payload = json.loads(message.content)
    except json.JSONDecodeError:
        return

    event = payload.get("event")
    if event == "book_chunk_selected":
        cl.user_session.set("selected_book_chunk", payload)
        await cl.Message(
            content=(
                "Selected book chunk received.\n\n"
                f"Chunk: `{payload.get('chunk_id')}`\n"
                f"Chapter: {payload.get('chapter_title')}\n\n"
                f"{payload.get('text', '')[:700]}"
            )
        ).send()
        return

    if event == "book_chunk_edit_saved":
        await cl.Message(
            content=(
                "Stub edit save received. No manuscript or draft was changed.\n\n"
                f"Chunk: `{payload.get('chunk_id')}`"
            )
        ).send()
        return

    if event == "book_chunk_edit_cleared":
        await cl.Message(
            content=f"Cleared local edits for `{payload.get('chunk_id')}`."
        ).send()


@cl.on_chat_end
async def on_chat_end() -> None:
    cl.user_session.set("fieldnotes_chat_ready", False)
