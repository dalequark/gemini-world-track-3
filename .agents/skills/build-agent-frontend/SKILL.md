---
name: build-agent-frontend
description: Build a simple plain-text chat web frontend for a deployed ADK / Agent Engine agent and wire it up (browser -> FastAPI proxy -> agent), then ship it to Cloud Run. Use when the user wants to build a frontend, a chat UI, or a web interface for their deployed agent, hook a UI up to their agent, set up the FastAPI proxy, or sort out the browser-to-proxy-to-agent auth. This is a plain chat UI; for A2UI rich UI (cards/tables) that renders in the ADK dev UI, use the enable-a2ui skill instead. A complete working template (FastAPI proxy + chat UI) ships alongside this skill in ./template. Don't use for agent-side logic unrelated to the UI.
---

# Build a chat frontend

Give a deployed agent a simple web **chat UI** and wire it to the agent. The
plumbing is a small **FastAPI proxy**: the browser talks only to the proxy, and
the proxy authenticates to the deployed agent. This is a **plain-text chat** — for
A2UI rich UI (cards/tables), see the `enable-a2ui` skill (it renders in the ADK
dev UI). A complete, working frontend ships in **`./template`** — copy it in,
don't rebuild it.

> **The one rule:** copy `./template` into the project as `frontend/` and change
> as little as possible. Do **NOT** build a React app, scaffold a new UI
> framework, or copy a large sample project. The template is enough.

## How it works

```
Browser (chat UI)  ->  FastAPI proxy (main.py)  ->  deployed agent
```

- The browser only talks to the proxy (same origin, no CORS, no cloud creds).
- The proxy authenticates with Application Default Credentials and forwards chat,
  reusing **one session per user** so the agent remembers the conversation.
- It shows the agent's **text** replies.

## Step 1 — Copy the template

Copy `./template` into the project as `frontend/`. Don't rewrite it — `main.py`
(the proxy) and `static/index.html` (the chat UI) already work together.

## Step 2 — Run locally

From `frontend/`:

```bash
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="<from deployment_metadata.json>"
python main.py     # -> http://localhost:8080
```

Send a message, then ask *"What did I just ask?"* to confirm the session works.

## Step 3 — Deploy to Cloud Run

The agent stays on Agent Engine; only the frontend ships to Cloud Run. Its
service account runs as a different identity than your local user, so it needs
**`roles/aiplatform.user`** or `/chat` returns 403:

```
Deploy the frontend to Cloud Run pointing at my AGENT_ENGINE_RESOURCE_NAME, and grant the Cloud Run service account roles/aiplatform.user.
```

## Want more than plain chat?

Ship pure chat first. If the user later wants controls (a side panel of inputs,
quick-action buttons, filters), add them **inside `static/index.html`** as a
small, self-contained block that composes a message and sends it — keep the chat
working and don't pull in a framework.

## What about A2UI (cards/tables)?

This frontend is **plain chat**. A2UI rich UI is an **agent-side** feature that
renders in the **ADK dev UI (`adk web`)** — see the **`enable-a2ui`** skill. If
an A2UI-enabled agent is queried here, the chat shows a short placeholder for the
rich-UI reply rather than rendering it (rendering A2UI in a custom frontend is a
separate, larger job).

## If something's wrong

- **403 from `/chat`:** ADC missing locally, or the Cloud Run service account
  lacks `roles/aiplatform.user`. (See the `troubleshoot-lab-setup` skill.)
- **Agent forgets the conversation ("What did I just ask?" fails):** the proxy
  must reuse one session per user — the template's `_session_for()` handles this.
- **Nothing renders / CORS error:** the browser is calling the agent directly; it
  must call the proxy (same origin) only.
- **Replies don't come through:** the streamed part shape can vary by SDK version
  — verify against your deployed agent with the Developer Knowledge MCP and adjust
  `_extract_parts` in `main.py`.

## Reference

- Template: `./template` (`main.py`, `requirements.txt`, `static/index.html`)
- A2UI (agent-side): the `enable-a2ui` skill · https://adk.dev/integrations/a2ui/
