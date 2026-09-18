# Integration Plan — TSP AI Service

## Overview

The AI service integrates with TSP via a **shared PostgreSQL database** boundary. There is no HTTP API between TSP and the AI service — the integration point is `TSPClient`, which holds all SQL and is the only code allowed to touch TSP tables directly.

---

## Data Flow Direction

```
TSP writes → PostgreSQL (source of truth)
                ↓
         TSPClient reads TSP tables (read-only for core TSP tables)
                ↓
         FastAPI builds prompts / retrieval queries
                ↓
         Gemma (OpenRouter) generates structured output
                ↓
         FastAPI validates + saves to:
           - ai_responses (existing TSP table) ← generated curricula
           - ai_content_chunks (AI-owned table) ← RAG index
```

---

## Where the Systems Meet: TSPClient Boundary

| Direction | Operation | Table | Notes |
|---|---|---|---|
| Read | `get_training_profile()` | `trainings`, `company_profiles`, objectives, keywords, purposes | Core TSP data |
| Read | `get_modules_with_lessons()` | `modules`, `lessons`, instructional_methods, materials, assessment_types, contents | Deep join |
| Read | `get_audience_profile()` | `audience_profiles`, `specific_courses`, `specific_prerequisites` | Base_data resolved |
| Read | `get_learner_profile()` | `trainees`, `users`, roles, base_data | Personalization |
| Read | `get_accepted_content()` | `contents` where `status='ACCEPTED'` | RAG source data |
| **Write** | `save_generated_curriculum()` | `ai_responses` | AI output logged |
| **Write** | Index upsert | `ai_content_chunks` | AI-owned table |

**Rule**: Every write to a TSP table goes through `TSPClient`. No other module may execute SQL directly.

---

## RAG Index Sync Strategy

### Current Implementation (Manual)
```
scripts/index_content.py <training_id>
```
- Fetches all `ACCEPTED` contents for the training
- Chunks text (400 words, 50 word overlap)
- Embeds with `all-MiniLM-L6-v2` (384 dimensions)
- Upserts to `ai_content_chunks` (ON CONFLICT content_id, chunk_index)

### When to Re-Index

| Trigger | How to Handle |
|---|---|
| New content accepted in TSP (`contents.status` → `ACCEPTED`) | Re-run `index_content.py <training_id>` |
| Content rejected / removed | Row will remain stale — run re-index to clean (upsert doesn't delete) |
| Training structure updated (new modules/lessons) | Re-run for that training_id |
| Embedding model upgrade | Truncate `ai_content_chunks`, re-index all trainings |

### Future Sync Options
1. **Postgres trigger**: `AFTER UPDATE ON contents` → notify AI service via `LISTEN/NOTIFY`
2. **Scheduled job**: Cron re-index every night for modified trainings (compare `updated_at`)
3. **Event queue**: TSP publishes content-accepted events to Redis/Kafka; AI service consumes

The current manual approach is correct for the demo phase. A trigger-based approach is recommended for production.

---

## Error Handling Strategy

| Error Type | Handling |
|---|---|
| DB connection failure | Pool raises `asyncpg.PostgresConnectionError`; FastAPI returns 500; health check shows degraded |
| Training not found | `TSPClient` returns `{}`; endpoint returns 404 |
| LLM JSON parse failure | Retry up to 3x with error appended to prompt; raise `LLMError` after cap |
| LLM API key missing | `LLMError` raised at startup test; `/health` shows `llm_connected: false` |
| OpenRouter rate limit / 429 | `LLMError` propagated; client receives 500 |
| Pydantic validation failure | Logged as validation error; treated as JSON parse failure → triggers retry |
| Curriculum save failure | Logged as warning; curriculum still returned (generation not rolled back) |
| Guardrail triggered | Returns 200 with `guardrail_triggered: true` and safe fallback message |
| No relevant chunks | Returns 200 with explicit "I don't have that information" answer |

---

## Security Posture

- **No secrets in code** — all credentials via environment variables
- **Parameterized SQL only** — `$1`, `$2` style throughout `TSPClient`; no f-string SQL
- **Single DB credential** — the AI service uses one Postgres user (`vini`) with write access to `public` schema; no per-user row-level security (see `limitations.md`)
- **Prompt injection guardrails** — 8 regex patterns covering common override attempts
- **Grounding enforcement** — system prompt instructs Gemma not to answer beyond provided chunks
