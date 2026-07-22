"""Minimal FastAPI proxy for a deployed ADK / Agent Engine agent (plain chat).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed Agent Engine, returning the agent's text replies.

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  python main.py        # -> http://localhost:8080

NOTE: the exact Agent Engine query method and event/part shape can vary by SDK
version. If replies don't come through, confirm the current API with the Developer
Knowledge MCP and adjust `_extract_parts` / the `stream_query` call.
"""

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


def _extract_parts(event) -> list[dict]:
    """Pull text out of one streamed event as [{kind: 'text', text: ...}].

    This is a plain-text chat, so we forward text parts. If a part isn't text
    (e.g. an A2UI rich-UI blob from an A2UI-enabled agent), we show a short
    placeholder — A2UI renders in the ADK dev UI (`adk web`), not here.
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
        elif p.get("inline_data") or p.get("inlineData"):
            out.append(
                {
                    "kind": "text",
                    "text": "[rich UI response — view it rendered in the ADK playground]",
                }
            )
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
        parts = [{"kind": "text", "text": "(no response)"}]
    return JSONResponse({"parts": parts})


# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
