---
name: rag-engine-setup
description: >
  Set up a Vertex AI RAG Engine corpus (Agent Platform) in serverless mode and
  wire it into an ADK agent. Use when the user wants to "create a RAG corpus",
  "build a RAG store", "ground my agent on documents", "add retrieval to my
  agent", or hits Spanner/allowlist errors creating a corpus. Covers GCS upload,
  serverless-mode switch, the LLM parser (custom parsing prompt), import,
  standalone retrieval testing, and the agent-side retrieval tool.
---

# Vertex AI RAG Engine — serverless corpus + ADK integration

A RAG Engine **corpus** is a managed index: you point it at documents in Cloud
Storage (or Drive), it chunks + embeds them, and stores the vectors in a managed
vector database. An agent then queries the corpus at runtime through a
**retrieval tool** and grounds its answers on the returned passages.

This skill builds a corpus in **serverless mode** — the cheapest, no-allowlist,
fully-managed option — and shows how the agent consumes it.

## Mental model (how it works end to end)

```
Ingest (once):   docs in GCS ──▶ LLM parser ──▶ chunk ──▶ embed ──▶ managed Vector Search
                                (custom prompt)         (text-embedding-005)

Query (runtime): user turn ─▶ agent LLM decides to call the retrieval tool
                            ─▶ tool runs retrieval_query(corpus, text) ─▶ top-k chunks
                            ─▶ chunks injected into the model's context
                            ─▶ model writes a grounded answer (optionally cites)
```

Two moving parts: **the corpus** (built once, below) and **the retrieval tool**
the agent calls (last section). The agent never talks to the vector DB directly —
it calls a tool, the tool calls the RAG service.

## Deployment modes — pick serverless

| Mode | Backend | Allowlist? | Cost | When |
|------|---------|-----------|------|------|
| **Serverless** (preview) | managed Vector Search | No | No service charge | **Default / tutorials** |
| Spanner (Basic/Scaled tier) | `RagManagedDb` (Spanner) | Yes in us-central1/-east1/-east4 | Spanner infra | CMEK, data residency, dedicated instances |

Serverless is **us-central1 only** and needs the **`vertexai.preview.rag`**
namespace — the GA `vertexai.rag` namespace only exposes Spanner `tier=` and
cannot select serverless. Serverless does **not** support CMEK / data residency /
Access Approval.

## Prerequisites (one-time)

```bash
PROJECT=your-project-id
gcloud config set project "$PROJECT"

# Enable the APIs. vectorsearch is required because serverless uses it as backend.
gcloud services enable aiplatform.googleapis.com vectorsearch.googleapis.com --project="$PROJECT"

# Put your source docs in a GCS bucket (HTML/PDF/TXT/Google Docs supported).
gcloud storage cp ./my_docs/*.txt gs://your-bucket/rag/
```

## Build the corpus

`scripts/create_rag_corpus.py`:

```python
from vertexai.preview import rag                      # preview namespace = serverless support
from vertexai.preview.rag.utils import resources as rr
import vertexai

PROJECT_ID = "your-project-id"
LOCATION   = "us-central1"                             # serverless is us-central1 only
GCS_PATH   = "gs://your-bucket/rag/"                   # a file or a prefix

# Custom instruction for the LLM parser — extract what matters, drop noise.
PARSING_PROMPT = (
    "Extract the individual useful facts and recipes described in this text. "
    "Ignore and omit all metadata, boilerplate, and image captions. "
    "Output clean, self-contained prose."
)

vertexai.init(project=PROJECT_ID, location=LOCATION)

# 1. Switch the region's RAG managed DB to serverless mode (project-level, once).
cfg = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
rag.update_rag_engine_config(rag_engine_config=rag.RagEngineConfig(
    name=cfg,
    rag_managed_db_config=rag.RagManagedDbConfig(mode=rr.Serverless()),
))

# 2. Create the corpus. Serverless auto-selects the managed Vector Search backend;
#    you only choose the embedding model.
corpus = rag.create_corpus(
    display_name="my-corpus",
    embedding_model_config=rag.EmbeddingModelConfig(
        publisher_model="publishers/google/models/text-embedding-005"),
)
print("corpus:", corpus.name)   # save this — the agent needs it

# 3. Import + parse + chunk + embed. The LLM parser applies PARSING_PROMPT per file.
resp = rag.import_files(
    corpus_name=corpus.name,
    paths=[GCS_PATH],
    transformation_config=rag.TransformationConfig(
        chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=100)),
    llm_parser=rag.LlmParserConfig(
        model_name="gemini-2.5-flash",
        custom_parsing_prompt=PARSING_PROMPT),
)
print("imported:", resp.imported_rag_files_count)
```

**Parser choice:** default parser (free, clean text) < **LLM parser** (semantic
extraction via a prompt — best for stripping boilerplate) < layout parser
(Document AI, best for tables/charts). Chunking still runs after parsing.

## Test WITHOUT touching agent code

Retrieval-only — confirms the index returns good passages, no LLM:

```python
from vertexai.preview import rag
import vertexai
vertexai.init(project="your-project-id", location="us-central1")

resp = rag.retrieval_query(
    text="what is good for a cough?",
    rag_resources=[rag.RagResource(rag_corpus="projects/.../ragCorpora/NNN")],
    rag_retrieval_config=rag.RagRetrievalConfig(top_k=5),
)
for c in resp.contexts.contexts:
    print(c.score, c.text[:200])
```

You can also test in the **Console**: Vertex AI → RAG Engine → your corpus →
Retrieve panel. After import, allow a short indexing lag (retrieval can 404
briefly even when the file shows `ACTIVE`).

## Wire it into the agent (ADK)

The agent accesses the corpus through a **retrieval tool**. In ADK use the
built-in `VertexAiRagRetrieval`:

```python
from google.adk.agents import Agent
from google.adk.tools.retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

rag_tool = VertexAiRagRetrieval(
    name="retrieve_herbal_lore",
    description="Search the herbal corpus for facts and recipes about a plant or ailment.",
    rag_resources=[rag.RagResource(rag_corpus="projects/.../ragCorpora/NNN")],
    similarity_top_k=5,
    vector_distance_threshold=0.5,
)

agent = Agent(
    model="gemini-2.5-flash",
    name="apothecary",
    instruction="Answer using the herbal corpus. Call retrieve_herbal_lore before answering.",
    tools=[rag_tool],
)
```

At runtime the model decides when to call `retrieve_herbal_lore`; ADK executes
`retrieval_query` against the corpus, feeds the top-k chunks back into the model,
and the model composes a grounded answer. The `description` matters — it's how the
model knows when to reach for the tool.

**Region gotcha (common in production):** a serverless corpus is `us-central1`
only, but your agent's model often runs elsewhere (e.g. `GOOGLE_CLOUD_LOCATION=global`).
`VertexAiRagRetrieval` runs `retrieval_query` against whatever region the
**aiplatform SDK** is initialized to — if that's not the corpus's region you get
`MethodNotImplemented / 404`. The genai model client (env-based) and ADK
session/memory services (explicit `location=`) do NOT use the aiplatform SDK's
initializer, so you can safely pin just the RAG client to the corpus region:

```python
import vertexai
# region parsed from projects/<p>/locations/<region>/ragCorpora/<id>
vertexai.init(project="...", location="us-central1")  # before building the tool
```

To steer the model on *how* to answer, put it in the agent instruction, e.g.:
"When you rely on the Herbal's words, quote the passage verbatim in quotation
marks and name it as Culpeper's Complete Herbal; otherwise paraphrase."

**Alternative (Gemini native grounding, no ADK):** pass a retrieval tool straight
to a `GenerativeModel` via `Tool.from_retrieval(rag.Retrieval(rag.VertexRagStore(...)))`.
Same corpus, retrieval handled inside `generate_content` instead of as an agent tool.

## Troubleshooting

- `INVALID_ARGUMENT ... Spanner mode ... restricted to allowlisted projects` →
  you're on the GA namespace or Spanner mode. Use `vertexai.preview.rag` +
  `mode=rr.Serverless()`.
- `PERMISSION_DENIED ... Vector Search API has not been used` → enable
  `vectorsearch.googleapis.com`, wait ~1 min, retry.
- `NOT_FOUND No vertex rag corpus found` right after import → indexing lag; retry
  after a few seconds.
