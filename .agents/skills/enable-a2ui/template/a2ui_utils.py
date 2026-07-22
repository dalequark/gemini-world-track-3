"""Make an ADK agent's A2UI output render in the ADK dev UI (`adk web`).

`adk web` has a built-in A2UI renderer, but it only fires when a response part is
a text/plain Blob wrapped in <a2a_datapart_json>...</a2a_datapart_json> with
custom_metadata {"a2a:response": "true"}. This callback takes the A2UI JSON the
model emits as text and rewraps it into exactly that format.

Wire it up with `after_model_callback=a2ui_callback` on your Agent. Pin the A2UI
schema to **version 0.8** (this callback keys off v0.8 messages: beginRendering,
surfaceUpdate, dataModelUpdate). Copy this file next to your agent.py.
"""

import json
import re

from google.genai import types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse


def _wrap_a2ui_part(a2ui_message: dict) -> types.Part:
    """Wrap a single A2UI message for rendering in adk web."""
    datapart_json = json.dumps(
        {
            "kind": "data",
            "metadata": {"mimeType": "application/json+a2ui"},
            "data": a2ui_message,
        }
    )
    blob_data = (
        b"<a2a_datapart_json>" + datapart_json.encode("utf-8") + b"</a2a_datapart_json>"
    )
    return types.Part(
        inline_data=types.Blob(
            data=blob_data,
            mime_type="text/plain",
        )
    )


def a2ui_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Convert A2UI JSON in text output to rendered components."""
    if not llm_response.content or not llm_response.content.parts:
        return None
    for part in llm_response.content.parts:
        if not part.text:
            continue
        text = part.text.strip()
        if not text:
            continue
        if not any(
            k in text for k in ("beginRendering", "surfaceUpdate", "dataModelUpdate")
        ):
            continue
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3].strip()
        # Find where JSON starts (skip conversational prefix)
        json_start = None
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                json_start = i
                break
        if json_start is None:
            continue
        json_text = text[json_start:]
        # raw_decode parses JSON and ignores trailing text
        try:
            parsed, _ = json.JSONDecoder().raw_decode(json_text)
        except json.JSONDecodeError:
            # Handle concatenated JSON objects: {"a":1} {"b":2}
            try:
                fixed = "[" + re.sub(r"\}\s*\{", "},{", json_text) + "]"
                parsed, _ = json.JSONDecoder().raw_decode(fixed)
            except json.JSONDecodeError:
                continue
        if not isinstance(parsed, list):
            parsed = [parsed]
        a2ui_keys = {
            "beginRendering",
            "surfaceUpdate",
            "dataModelUpdate",
            "deleteSurface",
        }
        a2ui_messages = [
            msg
            for msg in parsed
            if isinstance(msg, dict) and any(k in msg for k in a2ui_keys)
        ]
        if not a2ui_messages:
            continue
        new_parts = [_wrap_a2ui_part(msg) for msg in a2ui_messages]
        return LlmResponse(
            content=types.Content(role="model", parts=new_parts),
            custom_metadata={"a2a:response": "true"},
        )
    return None
