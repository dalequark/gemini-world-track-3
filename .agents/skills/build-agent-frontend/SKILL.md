---
name: build-agent-frontend
description: Build a chat web frontend for a deployed ADK / Agent Engine agent and wire it up (browser -> FastAPI proxy -> agent), then ship it to Cloud Run. The chat UI shows plain-text replies AND natively renders the agent's A2UI cards via a small built-in renderer, so it works whether or not the agent has A2UI enabled. Use when the user wants to build a frontend, a chat UI, or a web interface for their deployed agent, hook a UI up to their agent, set up the FastAPI proxy, or sort out the browser-to-proxy-to-agent auth. A2UI is an agent-side feature (see the enable-a2ui skill); this skill renders it in the custom frontend. A complete working template (FastAPI proxy + chat UI + A2UI renderer) ships in ./template. Don't use for agent-side logic unrelated to the UI.
---

# Build a chat frontend

Give a deployed agent a simple web **chat UI** and wire it to the agent. The
plumbing is a small **FastAPI proxy**: the browser talks only to the proxy, and
the proxy authenticates to the deployed agent. The UI shows **plain-text replies**
and also **renders the agent's A2UI cards** natively (a small built-in renderer),
so it works whether or not the agent has `enable-a2ui`. A complete, working
frontend ships in **`./template`** — copy it in, don't rebuild it.

> **The one rule:** copy `./template` into the project as `frontend/` and change
> as little as possible. Do **NOT** build a React app, scaffold a new UI
> framework, or copy a large sample project. The template is enough.

## How it works

```
Browser (chat UI)  ->  FastAPI proxy (main.py)  ->  deployed agent
```

- The browser only talks to the proxy (same origin, no CORS, no cloud creds).
- The UI sends a **stable per-browser `user_id`** (a `localStorage` UUID) with
  each message, so every visitor gets their own agent session and memory. If the
  browser sends no id the proxy falls back to a single shared `"web-user"` —
  fine for one person testing, but everyone would then share one conversation.
  Swap in a real signed-in user id if you add auth.
- The proxy authenticates with Application Default Credentials and forwards chat,
  reusing **one session per `user_id`** so the agent remembers the conversation.
- The proxy returns structured parts (`text` or `a2ui`); the UI shows text
  replies and renders A2UI cards.

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

Ship plain chat first. To add controls later (an input panel, quick-action
buttons, filters), put them inside `static/index.html` as a small self-contained
block that builds a message and sends it through the existing chat flow. That way
the UI grows without a new framework or build step.

## What about A2UI (cards)?

A2UI is an **agent-side** feature (see the **`enable-a2ui`** skill). This frontend
**renders it**: the proxy unwraps the agent's A2UI blobs into `a2ui` parts, and a
small built-in renderer in `static/index.html` draws them as cards.

- Supported components: `Card, Column, Row, Text` (with `usageHint`), `Divider`,
  `List`, `Image`, `Icon`. Anything else **falls back to plain text**, so a reply
  never blanks. (`Icon` uses the Material Symbols web font; if it can't load, the
  icon shows its name as text.)
- `Image` renders inline when its url is a public `http(s)` link. If the agent
  uploads a generated image to a public bucket and puts that URL in the `Image`,
  the picture shows in the chat. A bare artifact filename has no fetchable URL and
  shows as a broken image.
- It's **display-only**, matching `enable-a2ui`: buttons/actions aren't wired.
- Because you own this renderer, it's more reliable than `adk web` (no streaming
  quirks or stuck-renderer blanks).
- Keep the agent's A2UI output small and flat (the `enable-a2ui` guidance) so the
  renderer has less to trip on.

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
- **A2UI card shows as plain text instead of a card:** the renderer hit a
  component it doesn't support (or a broken surface) and fell back to text — this
  is intended, not a crash. Keep the agent's surfaces to the supported subset.
- **`(The agent didn't return a reply.)`:** the turn produced no text or UI —
  usually the agent only ran tools or a tool stalled server-side (an agent/deploy
  issue, not the frontend). Check the agent's logs.

## Reference

- Template: `./template` (`main.py`, `requirements.txt`, `static/index.html`)
- A2UI (agent-side): the `enable-a2ui` skill · https://adk.dev/integrations/a2ui/
