# TSP AI Service

**AI-powered add-on for the Training Solutions Platform (TSP)**
Curriculum Builder + Conversational Copilot, grounded entirely in real TSP data.

> **Built by**: Vini (Lead) · Week 5 Project
> **Grading areas**: Problem Definition (8%) + TSP Integration (12%)

---

## What This Is

Two AI features built as a FastAPI service that reads from the real TSP PostgreSQL database:

| Feature | How it works |
|---|---|
| **Curriculum Builder** | Fetches training profile + modules + audience from TSP → prompts Gemma → validates JSON → saves curriculum |
| **Conversational Copilot** | Fetches learner profile → retrieves relevant content chunks → prompts Gemma with grounded context → returns answer with source attribution |

Both features use **only real TSP data** — no fabricated content, no hardcoded training data.

---

## Quick Start (5 minutes)

### Prerequisites
- Python 3.12
- PostgreSQL `training_solutions` database (the real TSP DB — ask the lead for credentials)
- OpenRouter API key with `google/gemma-2-9b-it` access → [openrouter.ai/keys](https://openrouter.ai/keys)

### Setup

```bash
# 1. Navigate into this folder
cd tsp-ai-service

# 2. Create virtual environment
python3.12 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with real DB credentials and OpenRouter key

# 5. Create the two AI tables in Postgres (run once)
psql -U $TSP_DB_USER -d training_solutions -f docs/db_migrations.sql

# 6. Index demo training content into RAG table (run once)
python -m scripts.index_content 45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc

# 7. Start the API server
uvicorn app.main:app --reload --port 8000

# 8. In a second terminal, start the demo UI
source .venv/bin/activate
streamlit run demo/app.py --server.port 8501
```

**Verify it's working:**
```bash
curl http://localhost:8000/health
# → {"status": "healthy", "database_connected": true, "llm_connected": true}
```

OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)
Demo UI: [http://localhost:8501](http://localhost:8501)

---

## Project Structure

```
tsp-ai-service/
├── app/
│   ├── main.py          # FastAPI — /health, /curriculum/generate, /copilot/message
│   ├── tsp_client.py    # ONLY place that reads/writes TSP tables
│   ├── schemas.py       # Pydantic models — Curriculum, Module, Lesson, etc.
│   ├── llm.py           # Gemma via OpenRouter (call_gemma, call_gemma_json)
│   └── retrieval.py     # RAG: reads ai_content_chunks, cosine similarity in Python
├── scripts/
│   └── index_content.py # Chunks + embeds accepted content → ai_content_chunks table
├── demo/
│   └── app.py           # Streamlit demo — all 5 required scenarios
├── docs/
│   ├── README (this file)
│   ├── tsp_client_contract.md    ← Teammates: read this first
│   ├── teammate_handoff.md       ← Teammates: your build instructions
│   ├── tsp_schema_map.md         # Real DB schema (139 tables discovered live)
│   ├── tsp_er_diagram.md         # Mermaid ER diagram
│   ├── architecture.md           # Full system flowchart
│   ├── sequence_curriculum_generation.md
│   ├── sequence_copilot_interaction.md
│   ├── data_mapping.md           # TSP fields → AI usage
│   ├── integration_plan.md       # Data flow + sync strategy + error handling
│   ├── limitations.md            # 8 real limitations with reasoning
│   ├── setup.md                  # Detailed setup guide
│   ├── sample_requests.md        # curl examples for all endpoints
│   ├── evaluation_plan.md        # Test set + metrics for all 4 teammates
│   ├── contribution_statement.md # Lead's individual contribution record
│   ├── db_migrations.sql         # SQL to create the two AI tables
│   └── evaluation_results.md     # (create this — fill in test results)
├── .env.example         # Environment variable template
├── .gitignore
└── requirements.txt
```

---

## Demo Scenarios

All 5 required grading scenarios are wired in the Streamlit demo:

| # | Scenario | How to trigger |
|---|---|---|
| (a) | Normal curriculum generation | Click "Real training curriculum" in Curriculum tab |
| (b) | Copilot: unsupported question → fallback | Click "Unsupported" in Copilot tab |
| (c) | Prompt injection attempt → blocked | Click "Injection" in Copilot tab |
| (d) | Invalid training ID → 404 | Click "Invalid training ID" in Curriculum tab |
| (e) | Unauthorized learner access → blocked | Click "Unauthorized" in Copilot tab |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TSP_DB_HOST` | No (default: localhost) | PostgreSQL host |
| `TSP_DB_PORT` | No (default: 5432) | PostgreSQL port |
| `TSP_DB_USER` | No (default: vini) | PostgreSQL user |
| `TSP_DB_PASSWORD` | **Yes** | PostgreSQL password |
| `TSP_DB_NAME` | No (default: training_solutions) | Database name |
| `OPENROUTER_API_KEY` | **Yes** | OpenRouter key |
| `TSP_DB_POOL_MIN` | No (default: 2) | Min pool connections |
| `TSP_DB_POOL_MAX` | No (default: 10) | Max pool connections |

---

## For Teammates

| Teammate | Role | Start here |
|---|---|---|
| Teammate 2 | Curriculum Builder | `docs/teammate_handoff.md` → Teammate 2 section |
| Teammate 3 | RAG Pipeline | `docs/teammate_handoff.md` → Teammate 3 section |
| Teammate 4 | Copilot & Personalization | `docs/teammate_handoff.md` → Teammate 4 section |

**Critical rule**: All database access must go through `TSPClient` in `app/tsp_client.py`. Never write SQL anywhere else.

---

## Architecture

```
TSP PostgreSQL ──→ TSPClient ──→ FastAPI Service ──→ OpenRouter/Gemma
       │               │               │
       │         (only boundary)    /curriculum/generate
       │                            /copilot/message
       │                            /health
       ↓
ai_content_chunks (RAG index, float[] embeddings)
ai_generated_curricula (curriculum output, JSONB)
```

Full diagram: [docs/architecture.md](docs/architecture.md)

---

## Key Technical Decisions

| Decision | Reason |
|---|---|
| `float[]` instead of pgvector | pgvector not installed on this Postgres server |
| New `ai_generated_curricula` table | `ai_responses` has a CHECK constraint that rejects our `request_type` |
| Prompt-based JSON + retry | Gemma via OpenRouter doesn't reliably support native structured output |
| Singleton TSPClient with asyncpg pool | Avoids reconnecting per request |

Details: [docs/limitations.md](docs/limitations.md)
