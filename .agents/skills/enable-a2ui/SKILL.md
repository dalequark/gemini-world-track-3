---
name: enable-a2ui
description: Make an ADK agent emit A2UI so its replies render as rich UI (cards, tables, buttons) in the ADK dev UI (adk web) instead of plain text. Use when the user wants to add A2UI to their agent, return rich or interactive UI, render cards/tables in adk web, or when A2UI is showing up as raw JSON. Ships a ready-made a2ui_utils.py (the after_model_callback that adk web's renderer needs) in ./template. This renders in adk web (the dev UI); shipping A2UI to a custom production frontend is a separate concern.
---

# Enable A2UI (renders in adk web)

Make an ADK agent return **A2UI** — cards, tables, buttons — that the **ADK dev UI
(`adk web`) renders natively**. Two pieces are required, and you need **both** or
you'll just see raw JSON:

1. A **system prompt** that teaches the model to output A2UI JSON (`A2uiSchemaManager`).
2. An **`after_model_callback`** that rewraps that JSON into the exact format
   `adk web`'s built-in renderer detects. It ships ready-made as
   **`./template/a2ui_utils.py`** — copy it in, don't rewrite it.

> **Pin version 0.8.** The callback keys off v0.8 messages (`beginRendering`,
> `surfaceUpdate`, `dataModelUpdate`). If you generate v0.9 (`updateComponents`),
> the callback never fires and you get raw JSON. Use `version="0.8"` everywhere.

## Step 1 — Copy the callback

Copy `./template/a2ui_utils.py` into your agent package (next to `agent.py`).

## Step 2 — Build the A2UI system prompt

```python
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="<what your agent is / does>",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Use cards for summaries, rows/columns for layout, buttons for actions. "
        "Do NOT use markdown in text values; use the usageHint property for headings. "
        "Respond ONLY with the A2UI JSON array — no text outside the JSON; put all "
        "explanations in Text components."
    ),
    include_schema=True,
    include_examples=True,
)
```

## Step 3 — Wire the callback onto the agent

```python
from google.adk.agents import Agent
from .a2ui_utils import a2ui_callback

root_agent = Agent(
    model="<your model>",
    name="<your agent>",
    instruction=instruction,
    tools=[...],
    after_model_callback=a2ui_callback,   # <- this is what makes adk web render it
)
```

## Step 4 — Test in adk web

```bash
adk web --port 8080 --allow_origins "*" --reload_agents
```

Start a **New Session**, then ask something that should produce UI. You should see
cards/tables, not JSON.

## If it still shows raw JSON

- **`after_model_callback=a2ui_callback` isn't wired** — the #1 cause.
- **Wrong version** — it must be `0.8` (the callback keys off v0.8 messages).
- **Stale tab** — refresh the browser and start a New Session after reloading.
- **Model wrapped the JSON in prose/markdown** — the callback strips fences, but
  keep the `ui_description` rule "respond ONLY with the A2UI JSON."

## Note

This renders in the **ADK dev UI** (`adk web`). A custom production frontend (e.g.
one shipped to Cloud Run) does **not** get this for free — that's a separate
renderer problem. The `build-agent-frontend` skill ships a plain chat UI.

## Reference

- Template: `./template/a2ui_utils.py` (the `after_model_callback`)
- ADK A2UI integration: https://adk.dev/integrations/a2ui/
- A2UI spec (optional): https://a2ui.org/
