"""Minimal FastAPI proxy for a deployed ADK / Agent Engine agent.

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed Agent Engine, passing A2UI DataParts through
unchanged so the client can render them.

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  python main.py        # -> http://localhost:8080

NOTE: the exact Agent Engine query method and event/part shape can vary by SDK
version. If parts don't come through, confirm the current API with the Developer
Knowledge MCP and adjust `_extract_parts` / the `stream_query` call.
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import vertexai
from vertexai import agent_engines

A2UI_MIME = "application/json+a2ui"
RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]

vertexai.init()  # project/location come from ADC / env
_agent = agent_engines.get(RESOURCE)

app = FastAPI()


def _extract_parts(event) -> list[dict]:
    """Normalize one streamed event into [{kind: 'text'|'a2ui', ...}].

    A2UI parts arrive as DataParts whose metadata mimeType is
    'application/json+a2ui'. Everything else is treated as text.
    """
    if not isinstance(event, dict):
        event = getattr(event, "__dict__", {}) or {}
    content = event.get("content") or {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    out: list[dict] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        meta = p.get("metadata") or {}
        if str(meta.get("mimeType", "")).find("a2ui") != -1:
            out.append({"kind": "a2ui", "data": p.get("data") or p.get("inline_data")})
        elif p.get("text"):
            out.append({"kind": "text", "text": p["text"]})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []
    for event in _agent.stream_query(message=message, user_id=user_id):
        parts.extend(_extract_parts(event))
    if not parts:
        parts = [{"kind": "text", "text": "(no response)"}]
    return JSONResponse({"parts": parts})


# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
