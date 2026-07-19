---
name: build-a2ui-frontend
description: Build and wire up a web frontend for a deployed ADK / Agent Engine agent that renders A2UI rich UI (cards, tables, forms, charts) instead of plain text. Use when the user wants to build a frontend, hook a UI up to their deployed agent, render A2UI payloads (mimeType application/json+a2ui), set up the FastAPI proxy + chat UI, or sort out the browser→proxy→agent auth. A reference template (FastAPI proxy + chat UI + minimal A2UI renderer) ships alongside this skill in ./template. Don't use for agent-side business logic unrelated to the UI.
---

# Build an A2UI frontend

Give a deployed agent a web face that renders **A2UI** — real UI (cards, tables,
forms, charts) the agent emits as structured JSON — with a graceful fallback to
plain text. A working starter lives in **`./template`** next to this skill; copy
it into the project as `frontend/` and adapt.

## Architecture (explain this first)

```
Browser (chat UI + A2UI renderer)
   │  same-origin fetch, no GCP creds in the browser
   ▼
FastAPI proxy  ──(ADC / service account)──►  Deployed Agent Engine
   │                                          (Vertex AI Agent Engine)
   └─ streams the agent's parts back, passing A2UI DataParts through untouched
```

Two rules that make this work:
- **The browser never holds Google Cloud credentials.** It only ever talks to
  the proxy (same origin → no CORS). The **proxy** authenticates to the agent.
- **A2UI is data, not code.** The agent returns A2UI as an A2A `DataPart` with
  MIME type `application/json+a2ui`. The proxy passes it through; the client
  renderer turns it into components. Plain text parts render as text.

## Prerequisites

- The agent is **deployed** and you have its `AGENT_ENGINE_RESOURCE_NAME`
  (from `deployment_metadata.json`).
- **A2UI is enabled on the agent** (see next section). If the agent doesn't emit
  A2UI parts, the frontend still works — it just shows text.

## Step 1 — Enable A2UI on the agent (if not already)

Install and wire the SDK (`pip install a2ui-agent-sdk`). The schema manager
generates a system prompt that teaches the model to emit valid A2UI JSON, and
you **validate before returning**:

```python
from a2ui.core.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.a2a import parse_response_to_parts

schema_manager = A2uiSchemaManager(catalogs=[BasicCatalog.get_config(examples_path="examples")])

instruction = schema_manager.generate_system_prompt(
    role_description="<one line describing what your agent is>",
    ui_description="Use cards for item details, tables for lists/comparisons, forms for input.",
    include_schema=True, include_examples=True,
    allowed_components=["Heading", "Text", "Card", "Image", "Button", "Table"],
)
# use `instruction` as your LlmAgent(instruction=...)

# When returning: validate + wrap as A2A parts (mimeType application/json+a2ui)
parts = parse_response_to_parts(
    llm_output_text,
    validator=schema_manager.get_selected_catalog().validator,
    fallback_text="Here's what I found.",
)
```

Prompt to have the agent do it for you:

```
Enable A2UI on my agent with the a2ui-agent-sdk and the Basic Catalog: build the system prompt with A2uiSchemaManager, allow Card/Table/Text/Image/Button, and validate the model's output with parse_response_to_parts before returning it.
```

Test in the ADK playground (`adk web`) — it renders A2UI out of the box, so you
can confirm the agent emits cards/tables before touching the frontend.

## Step 2 — Stand up the proxy

Copy `./template` into the project as `frontend/`. The proxy (`main.py`):
- authenticates to the agent with **Application Default Credentials**,
- calls the deployed Agent Engine identified by `AGENT_ENGINE_RESOURCE_NAME`,
- streams the response parts back to the browser, **passing A2UI DataParts
  through unchanged** (identified by `mimeType == "application/json+a2ui"`).

```
Copy the frontend template into ./frontend and wire the proxy to my deployed agent using AGENT_ENGINE_RESOURCE_NAME. Keep A2UI DataParts (mimeType application/json+a2ui) intact when streaming to the browser.
```

## Step 3 — Render A2UI on the client

The client (`static/index.html`) reads each part: if it's an A2UI part, hand its
JSON to the renderer; otherwise show text. The template ships a **minimal
starter renderer** (Card / Table / Text / Heading / Image / Button) so it works
out of the box — for full fidelity, swap in the official renderer / component
gallery from [a2ui.org](https://a2ui.org/reference/components/).

A2UI nodes look like `{"type": "Card", "props": {...}, "children": [...]}`.

## Step 4 — Run locally

From `frontend/`:

```bash
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="<from deployment_metadata.json>"
python main.py     # serves http://localhost:8080
```

Ask for something that returns rich UI — a list your agent knows about (→ table)
or the details of one item (→ card). Then ask *"What did I just ask?"* to confirm
the session is wired up.

## Step 5 — Deploy to Cloud Run (auth gotcha)

The frontend ships to **Cloud Run** (the agent stays on Agent Engine). The Cloud
Run service runs as a **different service identity** than your local user, so its
service account needs **`roles/aiplatform.user`** or `/chat` will 403.

```
Deploy the frontend to Cloud Run pointing at my AGENT_ENGINE_RESOURCE_NAME, and grant the Cloud Run service account roles/aiplatform.user.
```

## Gotchas
- **403 / PERMISSION_DENIED from `/chat`:** ADC missing locally, or the Cloud Run
  service account lacks `roles/aiplatform.user`. (See the `troubleshoot-lab-setup` skill.)
- **A2UI shows as raw JSON:** the client isn't detecting the part — check for
  `mimeType == "application/json+a2ui"` and that the proxy didn't stringify it.
- **Nothing renders / CORS errors:** the browser is calling the agent directly.
  It must call the *proxy* (same origin) only.
- **Agent emits invalid A2UI:** always validate server-side (Step 1); fall back
  to text rather than sending broken JSON to the client.

## Reference
- Template: `./template` (`main.py`, `requirements.txt`, `static/index.html`)
- A2UI spec + component gallery: https://a2ui.org/
- ADK A2UI sample (great to copy): https://github.com/a2ui-project/a2ui/tree/main/samples/agent/adk/restaurant_finder
- Verify exact Agent Engine query/stream APIs with the Developer Knowledge MCP if they've changed.
