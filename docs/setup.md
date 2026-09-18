# Setup — TSP AI Service

## Prerequisites

- Python 3.11+
- PostgreSQL 16 (with `training_solutions` database — the existing TSP DB)
- An [OpenRouter](https://openrouter.ai/keys) API key with access to `google/gemma-2-9b-it`
- `pip` / `venv` or `conda`

---

## Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# TSP PostgreSQL connection
TSP_DB_HOST=localhost
TSP_DB_PORT=5432
TSP_DB_USER=<your_db_user>
TSP_DB_PASSWORD=<your_db_password>
TSP_DB_NAME=training_solutions

# OpenRouter API key — get from https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional connection pool sizing
TSP_DB_POOL_MIN=2
TSP_DB_POOL_MAX=10
```

> **Never commit `.env` to version control.** The `.env.example` file shows required variable names with placeholder values — commit that instead.

---

## Installation

```bash
# 1. Clone / navigate to project directory
cd your-sand-box

# 2. Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
```

---

## Database Setup

### Step 1 — Verify TSP database exists

```bash
PGPASSWORD=$TSP_DB_PASSWORD psql -U $TSP_DB_USER -d training_solutions -c "SELECT COUNT(*) FROM trainings;"
```

### Step 2 — Create the AI service table (`ai_content_chunks`)

This table stores RAG embeddings. Run once:

```bash
PGPASSWORD=$TSP_DB_PASSWORD psql -U $TSP_DB_USER -d training_solutions -f - <<'SQL'
CREATE TABLE IF NOT EXISTS ai_content_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    module_id         UUID NOT NULL REFERENCES modules(id),
    lesson_id         UUID REFERENCES lessons(id),
    chunk_text        TEXT NOT NULL,
    chunk_index       INTEGER NOT NULL,
    embedding         float[] NOT NULL,
    file_type         VARCHAR(50),
    level             VARCHAR(50),
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE(content_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_ai_chunks_content ON ai_content_chunks(content_id);
CREATE INDEX IF NOT EXISTS idx_ai_chunks_module  ON ai_content_chunks(module_id);
SQL
```

> **Note on pgvector**: The PostgreSQL server does not have `pgvector` installed. Embeddings are stored as `float[]` and cosine similarity is computed in Python. See `docs/limitations.md` for the pgvector migration path.

### Step 3 — Index content for your demo training

Replace `<training_id>` with a real training UUID from TSP:

```bash
python -m scripts.index_content <training_id>
```

Example (demo training from `tsp_schema_map.md`):
```bash
python -m scripts.index_content 45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc
```

Expected output:
```
Found 5 accepted content items for training 45d3c920-...
  Orientation Module PDF (PDF): 1 chunk(s)
  ...
Total chunks in DB for this training: 5
Upserted 5 chunk(s) total.
```

---

## Running the FastAPI Service

```bash
# Load .env and start with hot-reload
source .env  # or set env vars in your shell
uvicorn app.main:app --reload --port 8000
```

Verify it's running:
```bash
curl http://localhost:8000/health
# → {"status":"healthy","database_connected":true,"llm_connected":true,...}
```

OpenAPI docs (auto-generated):
```
http://localhost:8000/docs
```

---

## Running the Streamlit Demo

In a second terminal (API must be running):

```bash
source .venv/bin/activate
streamlit run demo/app.py --server.port 8501
```

Open: `http://localhost:8501`

---

## Running the Demo Scenarios

### (a) Normal curriculum generation
- Enter training ID: `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc`
- Click **Generate Curriculum**

### (b) No data fallback
- In Copilot tab, click **"Unsupported question"**
- Ask: "What is the capital of France?"

### (c) Prompt injection blocked
- In Copilot tab, click **"Prompt injection attempt"**

### (d) Invalid training ID → 404
- In Curriculum tab, click **"Broken request (bad ID)"**

---

## Required Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TSP_DB_HOST` | No | `localhost` | PostgreSQL hostname |
| `TSP_DB_PORT` | No | `5432` | PostgreSQL port |
| `TSP_DB_USER` | No | `vini` | PostgreSQL username |
| `TSP_DB_PASSWORD` | **Yes** | — | PostgreSQL password |
| `TSP_DB_NAME` | No | `training_solutions` | Database name |
| `OPENROUTER_API_KEY` | **Yes** | — | OpenRouter API key |
| `TSP_DB_POOL_MIN` | No | `2` | Min connection pool size |
| `TSP_DB_POOL_MAX` | No | `10` | Max connection pool size |

---

## Useful Commands

```bash
# Check DB chunks indexed
PGPASSWORD=$TSP_DB_PASSWORD psql -U $TSP_DB_USER -d training_solutions \
  -c "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM ai_content_chunks;"

# Re-index a training (idempotent upsert)
python -m scripts.index_content <training_id>

# Test LLM connection only
python -c "
import asyncio; from app.llm import test_gemma_connection
asyncio.run(test_gemma_connection())
"

# Run API in production mode (no reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```
