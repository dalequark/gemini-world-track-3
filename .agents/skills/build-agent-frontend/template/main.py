"""Minimal FastAPI proxy for a deployed ADK / Agent Engine agent.

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed Agent Engine, returning the agent's replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

If the agent has A2UI enabled (see the enable-a2ui skill) its replies arrive as
inline_data blobs wrapped in <a2a_datapart_json>...</a2a_datapart_json>; this
proxy unwraps them into {"kind": "a2ui"} parts. A plain-text agent just works too.

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  python main.py        # -> http://localhost:8080

NOTE: the exact Agent Engine query method and event/part shape can vary by SDK
version. If replies don't come through, confirm the current API with the Developer
Knowledge MCP and adjust `_extract_parts` / the `stream_query` call.
"""

import base64
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import vertexai
from vertexai import agent_engines

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]

vertexai.init()  # project/location come from ADC / env
_agent = agent_engines.get(RESOURCE)

app = FastAPI()

# Reuse ONE Agent Engine session per user so the agent remembers the conversation.
# Without a session_id, stream_query starts a NEW session every call (no memory),
# and "What did I just ask?" would fail.
_sessions: dict[str, str] = {}


def _session_for(user_id: str) -> str:
    if user_id not in _sessions:
        s = _agent.create_session(user_id=user_id)
        _sessions[user_id] = s["id"] if isinstance(s, dict) else s.id
    return _sessions[user_id]


_A2UI_OPEN = "<a2a_datapart_json>"
_A2UI_CLOSE = "</a2a_datapart_json>"


def _decode_inline_a2ui(inline: dict) -> dict | None:
    """Decode one inline_data A2UI blob into its A2UI message dict, or None.

    An A2UI-enabled agent emits parts like:
        inline_data.data = <a2a_datapart_json>{"kind":"data","metadata":{...},
                            "data":{"surfaceUpdate":{...}}}</a2a_datapart_json>
    The bytes may arrive as raw bytes, a list of ints, or a base64 string
    (depending on how the SDK serialized them), so we normalize first, strip the
    wrapper tags, and return the inner A2UI message ({"beginRendering":...} etc).
    """
    data = inline.get("data")
    if isinstance(data, (bytes, bytearray)):
        text = bytes(data).decode("utf-8", "replace")
    elif isinstance(data, list):
        try:
            text = bytes(data).decode("utf-8", "replace")
        except (ValueError, TypeError):
            return None
    elif isinstance(data, str):
        if _A2UI_OPEN in data:
            text = data
        else:  # most likely base64 (tolerate url-safe alphabet + missing padding)
            try:
                b64 = data.replace("-", "+").replace("_", "/")
                b64 += "=" * (-len(b64) % 4)
                text = base64.b64decode(b64).decode("utf-8", "replace")
            except (ValueError, TypeError):
                text = data
    else:
        return None

    start, end = text.find(_A2UI_OPEN), text.find(_A2UI_CLOSE)
    inner = text[start + len(_A2UI_OPEN) : end] if start != -1 and end != -1 else text
    try:
        obj = json.loads(inner)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    # Unwrap {"kind":"data","data":{...}} -> the A2UI message.
    if isinstance(obj.get("data"), dict):
        return obj["data"]
    return obj


def _extract_parts(event) -> list[dict]:
    """Turn one streamed event into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI inline_data blobs are
    unwrapped into {"kind": "a2ui", "data": <message>} so the UI can render the
    card; anything we can't decode becomes a short text placeholder.
    """
    if not isinstance(event, dict):
        event = getattr(event, "__dict__", {}) or {}
    content = event.get("content") or {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    out: list[dict] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("text"):
            out.append({"kind": "text", "text": p["text"]})
            continue
        inline = p.get("inline_data") or p.get("inlineData")
        if inline:
            msg = _decode_inline_a2ui(inline)
            if msg is not None:
                out.append({"kind": "a2ui", "data": msg})
            else:
                out.append({"kind": "text", "text": "[unrenderable response]"})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []
    for event in _agent.stream_query(
        message=message, user_id=user_id, session_id=_session_for(user_id)
    ):
        parts.extend(_extract_parts(event))
    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
