# TSP AI Service

**AI-powered add-on for the Training Solutions Platform (TSP)**
Curriculum Builder + Conversational Copilot, grounded entirely in real TSP data.

> **Built by Group 3**:
> - **Teammate 1 (Henok - Lead)**: TSP Database Integration, FastAPI Service Architecture, Security Guardrails
> - **Teammate 2 (Natty)**: Curriculum Engineering, Cold-Start Synthesis & Word (.docx) Exporter
> - **Teammate 3 (Kibrewossen)**: RAG Retrieval Engine, Document Ingestion & Quantitative Evaluation Benchmark
> - **Teammate 4 (Abel)**: Copilot Multi-Turn Sessions, Evidence-Based Personalization & Next-Activity Engine
> 
> **Grading areas covered**: Problem Definition (8%) + TSP Integration (12%) + Curriculum Builder (12%) + RAG & Copilot (12%) + Personalization & Profiling (8%)

---

## What This Is

Two AI features built as a FastAPI service that reads from the real TSP PostgreSQL database:

| Feature | How it works |
|---|---|
| **Curriculum Builder** | Fetches training profile + modules + audience from TSP → prompts Gemma → validates JSON → saves curriculum (supports cold-start generation & `.docx` export) |
| **Conversational Copilot** | Fetches learner profile → retrieves relevant content chunks → prompts Gemma with grounded context → returns answer with source attribution & personalized next-activity recommendations |

Both features use **only real TSP data** — no fabricated content, no hardcoded training data.

---

## Quick Start (5 minutes)

### Prerequisites
- Python 3.12
- PostgreSQL `training_solutions` database (the real TSP DB — ask the lead for credentials)
- OpenRouter API key with `google/gemma-2-9b-it` access → [openrouter.ai/keys](https://openrouter.ai/keys)

### Setup

```bash
# 1. Navigate into the repository root folder
cd Group-3-AI-Curriculum-Builder---Conversational-Learning-Copilot

# 2. Create virtual environment
python3.12 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with real DB credentials and OpenRouter key

# 5. Create the AI tables in Postgres (run once)
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
Group-3-AI-Curriculum-Builder---Conversational-Learning-Copilot/
├── app/
│   ├── main.py          # FastAPI server routes (/health, /curriculum, /copilot)
│   ├── tsp_client.py    # ONLY place that reads/writes TSP tables
│   ├── schemas.py       # Pydantic models (Curriculum, Module, Copilot, etc.)
│   ├── llm.py           # Gemma LLM gateway via OpenRouter
│   ├── retrieval.py     # RAG engine, sentence tokenizer, vector retrieval
│   ├── curriculum_builder.py # Cold-start curriculum synthesis & draft enhancer
│   ├── docx_exporter.py # Publication-grade Word (.docx) exporter
│   └── session_store.py # Multi-turn session memory & DB hydration
├── scripts/
│   ├── index_content.py # Index TSP accepted content → ai_content_chunks
│   ├── evaluate_retrieval.py # Quantitative retrieval benchmarks (P@5, MRR)
│   ├── evaluate_personalization.py # Personalization & safety diff benchmarks
│   └── generate_curriculum.py # Standalone curriculum CLI generator
├── demo/
│   └── app.py           # Streamlit UI — all 5 required grading scenarios
├── tests/
│   ├── test_api.py      # Integration tests for FastAPI endpoints
│   ├── test_copilot.py  # Session memory & personalization unit tests
│   ├── test_curriculum_builder.py # Synthesis & validation unit tests
│   └── test_rag.py      # Tokenizer, extraction & vector similarity unit tests
├── docs/
│   ├── architecture.md           # Full system flowchart
│   ├── contribution_statement.md # Group contribution records (all 4 members)
│   ├── data_mapping.md           # TSP fields → AI usage mapping
│   ├── db_migrations.sql         # SQL schema migrations for AI tables
│   ├── evaluation_plan.md        # Evaluation protocol & metrics
│   ├── evaluation_results.md     # Final quantitative evaluation benchmark results
│   ├── integration_plan.md       # Data flow, sync strategy & error handling
│   ├── limitations.md            # System limitations with engineering rationale
│   ├── rag_and_copilot_architecture.md # RAG & Copilot detailed spec
│   ├── sample_requests.md        # curl examples for all API endpoints
│   ├── sequence_copilot_interaction.md # Sequence diagram for copilot
│   ├── sequence_curriculum_generation.md # Sequence diagram for curriculum
│   ├── setup.md                  # Comprehensive setup guide
│   ├── tsp_client_contract.md    # TSPClient API contract
│   ├── tsp_er_diagram.md         # Mermaid ER diagram
│   └── tsp_schema_map.md         # Schema map (139 TSP tables)
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

## Group Responsibilities & Architecture

| Team Member | Role & Component | Key Accomplishments | Documentation |
|---|---|---|---|
| **Teammate 1 (Henok - Lead)** | TSP Integration & Core Service | `asyncpg` pool, parameterization, 2-layer injection guardrails | `docs/contribution_statement.md` |
| **Teammate 2 (Natty)** | AI Curriculum Builder & Exporter | Cold-start synthesis, multi-modal resource evaluation, Word `.docx` exporter | `docs/contribution_statement.md` |
| **Teammate 3 (Kibrewossen)** | RAG Pipeline & Ingestion | Sentence tokenizer, MiniLM vector indexer, quantitative evaluation | `docs/rag_and_copilot_architecture.md` |
| **Teammate 4 (Abel)** | Copilot Sessions & Personalization | Multi-turn session memory, evidence-based profiling, next-activity engine | `docs/copilot_personalization.md` |

**Critical rule**: All database access must go through `TSPClient` in `app/tsp_client.py`. Never write raw SQL anywhere else in the application.

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
