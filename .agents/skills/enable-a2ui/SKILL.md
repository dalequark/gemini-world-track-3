---
name: enable-a2ui
description: Make an ADK agent emit A2UI so its replies render as rich display UI (cards, and tables built from rows/columns) in the ADK dev UI (adk web) instead of plain text. Use when the user wants to add A2UI to their agent, render cards or tables in adk web, or when A2UI shows up as raw JSON or a blank card. Ships a ready-made a2ui_utils.py (the after_model_callback adk web's renderer needs) in ./template. Display-only in adk web (buttons, actions, and modals don't function); shipping A2UI to a custom production frontend is a separate concern.
---

# Enable A2UI (renders in adk web)

Make an ADK agent return **A2UI** so `adk web` renders cards instead of plain text.
You need **both** of these or you'll just see raw JSON:

1. A **system prompt** that teaches the model to emit A2UI JSON (`A2uiSchemaManager`).
2. An **`after_model_callback`** that rewraps that JSON into the format adk web's
   renderer detects — ships ready-made as **`./template/a2ui_utils.py`**. Copy it,
   don't rewrite it.

> **Use version `0.8` everywhere.** The callback keys off v0.8 messages
> (`beginRendering`, `surfaceUpdate`). v0.9 output won't render.

## Step 1 — Copy the callback

Copy `./template/a2ui_utils.py` next to your `agent.py`.

## Step 2 — Build the system prompt

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
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text — no Table or Heading "
        "(unsupported), and no Buttons/actions/forms (they do nothing in adk web). "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
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

Start a **New Session** and ask for something visual — you should see a card, not
JSON. **Turn Token Streaming OFF** first (dev UI gear icon): with it on, adk web
shows the raw streamed JSON and never swaps in the card.

## adk web renderer limits (design around these)

- **Display only.** Buttons, actions, and forms render but do nothing; there are
  no modals. For real interactivity, use a custom frontend — see the
  `build-agent-frontend` skill.
- **Supported components:** `Card, Column, Row, Text, Divider, List, Icon, Image`.
  **Not** `Table` or `Heading` — build tables from Rows/Columns of Text, and use
  `Text` + `usageHint` for headings.
- **Small and flat renders best.** Deep nesting and big cards render blank. The
  callback drops broken surfaces (invalid JSON, undefined root, dangling refs) and
  shows a short fallback instead of a blank bubble.
- **The renderer is genuinely flaky** — even a valid surface occasionally renders
  blank. That's an adk-web bug, not your agent.

## Troubleshooting

| What you see | Most likely fix |
| --- | --- |
| Raw JSON while it types | Token Streaming is ON — turn it off (gear), hard-refresh, New Session |
| Raw JSON (not streaming) | Callback not wired (`after_model_callback=a2ui_callback`), or wrong version (use `0.8`) |
| Blank card | Surface too big/complex — ask for something simpler; or stuck UI state — hard-refresh + New Session |

## Reference

- Template: `./template/a2ui_utils.py` (the `after_model_callback`)
- ADK A2UI integration: https://adk.dev/integrations/a2ui/
- A2UI spec (optional): https://a2ui.org/
