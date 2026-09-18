# TSP AI Service — Independent Audit Report

**Auditor**: Antigravity (AI code auditor, acting on behalf of the grading advisor Claude)  
**Date**: 2026-09-18  
**Repository**: `tsp-ai-service/`  
**Request**: Audit against the project brief checklist. Verify claims rather than restate them.

---

## ⚠️ Audit Limitation: Shell Execution Unavailable

**The shell execution environment was non-functional during this audit.** Every `run_command` call
returned `connection reset by peer`, which means:

- I could **not** start the FastAPI server and hit live endpoints
- I could **not** connect to the PostgreSQL database and verify table/column existence
- I could **not** run the test suite and capture real output
- I could **not** run the injection tests against a live endpoint
- I could **not** verify which embedding model actually produced the stored chunks

All findings below are based on **direct file reading and static analysis** of every source
file, documentation file, and configuration file in the repository. Where I quote code or
claim something is present or absent, I read it directly. Where a claim required a running
system to verify, I say so explicitly in the "Unable to Verify" section.

This report does not contain fabricated verification results. Everything labeled "verified"
was verified via source reading. Everything that needed a live system is explicitly deferred.

---

## Summary

The lead has built a **structurally sound, well-documented foundation** that teammates can
genuinely build on. The TSPClient is the correct architectural pattern, all SQL is
parameterized, and the documentation volume is high. However, **three issues need fixing
before this is hands-off correct**: one undocumented architectural contradiction that
appears across multiple files, one dead-code bug in the system prompt, and one demo scenario
that will silently fail because it uses a fake UUID instead of a real cross-training learner.
The codebase is safe to hand to teammates as a scaffold, but **not yet safe to present to
evaluators without fixing the items in the "Found Issues" section below**.

---

## Verified Working (via direct source reading)

### TSPClient — SQL Parameterization
- **Verified by reading every SQL string** in `tsp_client.py`, `retrieval.py`, and
  `index_content.py`: All values are passed via positional parameters (`$1`, `$2`). No
  f-string SQL, no `%s`-style interpolation, no string concatenation in query bodies. ✅

### Pydantic Schemas (`app/schemas.py`)
- All schemas present with correct field types: `LearnerProfile`, `RubricCriterion`,
  `Rubric`, `Assignment`, `Assessment`, `Lesson`, `Module`, `CurriculumRequest`, `Curriculum`,
  `SourceAttribution`, `CopilotRequest`, `CopilotResponse`, `HealthResponse`. ✅
- `CopilotResponse` correctly includes `guardrail_triggered: bool`, `guardrail_reason: Optional[str]`,
  and `embedder: str` fields. ✅

### Guardrail Logic — Layer 1 Regex
- **Verified by reading `app/main.py` lines 34-54**: Eight patterns cover
  `ignore.*instructions`, `disregard`, `forget.*everything`, `you are now a`, `act as a`,
  `pretend to be`, `unrestricted.*developer`, `jailbreak`, `system.*prompt`,
  `<|...|>` special tokens, and `###system/instruction` headers. ✅
- Layer 2 LLM classifier also present in `check_llm_injection()`. ✅

### Cross-Training Authorization Guard
- **Verified in `app/main.py` lines 337-347**: `is_learner_enrolled()` called before
  any data access, returns guardrail if not enrolled. ✅
- **Verified in `app/tsp_client.py` lines 391-397**: Queries `trainees` with
  `WHERE id = $1 AND training_id = $2`. ✅

### Idempotent Curriculum Save
- **Verified in `app/tsp_client.py` lines 377-389**: Checks `WHERE curriculum_json = $2::jsonb`
  before INSERT. Returns existing ID without re-insert if identical curriculum exists. ✅

### FallbackEmbedder Surfaced in Health Response
- `get_embedder_info()` returns `{"name": "minilm"/"fallback", "is_real": bool}`. ✅
- `/health` sets `embedding_model_connected` based on real vs. fallback. ✅
- Every `CopilotResponse` includes `embedder=active_embedder`. ✅

### Database Migrations (`docs/db_migrations.sql`)
- Two AI-owned tables: `ai_content_chunks` (float[], `UNIQUE(content_id, chunk_index)`,
  three indexes) and `ai_generated_curricula` (JSONB column `curriculum_json`). ✅
- Foreign key references: `contents(id)`, `modules(id)`, `lessons(id)`, `trainings(id)`. ✅

### "No Answer" Fallback
- **Verified in `app/main.py` lines 360-366**: Empty chunk result returns
  `"I don't have that information in the training materials."` without calling the LLM. ✅

### RAG Retrieval — Training Scope Isolation
- **Verified in `app/retrieval.py` lines 141-158**: SQL filters by `training_id`
  via `WHERE m.training_id = $1`. Chunks from other trainings cannot appear. ✅

### Evaluation Plan
- `docs/evaluation_plan.md` is real and detailed: test questions, threshold targets
  (Precision@5 ≥ 0.6, Recall@5 ≥ 0.5), safety test table, results template. ✅

### All 16 Documentation Files Exist with Real Content
- Verified by reading each file: no stubs or placeholders. ✅

### Teammate Handoff Accuracy
- Handoff doc correctly describes what is done. One documentation lag: `is_learner_enrolled()`
  is marked as Teammate 4's task to build (line 186-190) but is **already implemented**.
  Teammate 4 should be told this is done to avoid duplicate work.

### `limitations.md` Accuracy
- Every limitation corroborated by source: pgvector absent, fallback embedder surfaced,
  Gemma prompt-based JSON retry, content is links/metadata only. ✅

---

## Found Issues

### ISSUE 1 — `retrieval.py` and `index_content.py` bypass the TSPClient boundary
**Severity**: Documentation gap + code inconsistency

**What's wrong**: `app/retrieval.py` line 140 calls `tsp_client._pool.acquire()` and
executes SQL directly against `modules` and `lessons` tables. `scripts/index_content.py`
lines 53 and 101 do the same.

**How confirmed**: Grep for `_pool.acquire` returns results in:
`tsp_client.py` (correct), `retrieval.py` (line 140), `main.py` (line 258 — health check),
and `index_content.py` (lines 53, 101).

**Impact**: The docs (`tsp_client_contract.md`, `teammate_handoff.md` rules section line 239,
`architecture.md`, `integration_plan.md`) all state: *"Never write SQL outside
`app/tsp_client.py`"*. These statements are factually false. Teammate who inspects code
will find the contradiction immediately. SQL itself is safe (parameterized, scoped correctly),
but the stated rule is not followed by the lead's own code.

**Fix**: Either (a) add `get_content_chunks(training_id)` method to `TSPClient` and
call it from `retrieval.py`; or (b) update docs to clarify the rule applies to TSP core
tables only and `ai_content_chunks` access via pool directly is exempt. Be consistent.

---

### ISSUE 2 — `CURRICULUM_SYSTEM_PROMPT` has dead `{placeholder}` text
**Severity**: Cosmetic / minor LLM quality impact

**What's wrong**: `app/main.py` lines 87-102, `CURRICULUM_SYSTEM_PROMPT` ends with:
```
Context:
- Training: {training_title}
- Audience: {audience_summary}
- Objectives: {objectives_summary}
- Modules with lessons: {modules_summary}
- Accepted content: {content_summary}
```

These `{...}` strings are **never formatted**. Grep for `.format(` in `app/` returns zero
results. The string is used directly as `system_prompt=CURRICULUM_SYSTEM_PROMPT` at line 301
with no `.format()` call. The LLM receives the literal brace-notation text.

**Impact**: Context section of system prompt is dead code. Real training data is correctly
in the user prompt, so generation still works — but the system prompt is misleading.

**Fix**: Delete the `Context:` block from `CURRICULUM_SYSTEM_PROMPT` (data is already
in the user prompt), or call `.format(...)` with actual values before passing it.

---

### ISSUE 3 — Demo Scenario (e) "Unauthorized access" uses a fabricated UUID
**Severity**: Blocks the demo scenario from being fully convincing

**What's wrong**: `demo/app.py` line 27:
```python
UNAUTHORIZED_LEARNER = "ffffffff-ffff-ffff-ffff-ffffffffffff"
```
This UUID almost certainly does not exist in `trainees`. `is_learner_enrolled()` returns
`False` (UUID not found) — but this is because the UUID doesn't exist, not because a
real learner from Training B is denied access to Training A. The demo is supposed to show
cross-learner boundary protection with a *valid* learner.

**How confirmed**: `tests/test_api.py` line 87 uses a real trainee UUID
`b822e3a3-58ca-4c5e-913d-4e4fbcac3078` (enrolled in `74fa89c5-...`) for the same test.
That UUID should be in `demo/app.py` instead.

**Fix**: Replace `UNAUTHORIZED_LEARNER` with the real trainee ID from `test_api.py` line 87.

---

### ISSUE 4 — Four documentation files say curricula are saved to `ai_responses`; code uses `ai_generated_curricula`
**Severity**: Documentation contradiction that evaluators will notice

**Files with wrong table name**:
- `docs/integration_plan.md` line 36: `save_generated_curriculum()` → `ai_responses`
- `docs/data_mapping.md` lines 67-69: outputs mapped to `ai_responses.output/.prompt/.request_type`
- `docs/architecture.md` line 72: `INSERT ai_responses`
- `docs/sequence_curriculum_generation.md` lines 58, 69: `INSERT INTO ai_responses`

**How confirmed**: Grep for `ai_responses` shows 4 doc files with the wrong name. Actual
code (`tsp_client.py` lines 384-389) and `db_migrations.sql` use `ai_generated_curricula`.
`README.md` correctly explains why `ai_responses` was rejected.

**Fix**: Update all four doc files to reference `ai_generated_curricula`.

---

### ISSUE 5 — Test count is inconsistent across documents
**Severity**: Minor documentation credibility issue

**What's wrong**:
- `LEAD_IMPLEMENTATION_REPORT.md` line 22: "4/4 pytest cases"; line 234: "4 passed in 5.44s"
- `contribution_statement.md` line 29: "8 comprehensive integration tests"
- Actual `tests/test_api.py`: **7 test functions**

**How confirmed**: Counted `def test_` in `test_api.py` — seven functions.

**Fix**: Update both documents to say 7 tests. Note two tests require a live LLM call.

---

### ISSUE 6 — OpenRouter API key in `.env` is still the placeholder value
**Severity**: Blocks all LLM-dependent functionality

**What's wrong**: `.env` line 9: `OPENROUTER_API_KEY=your_openrouter_key_here`.
`app/llm.py` line 43 only raises `LLMError` if the key is falsy — a non-empty placeholder
passes this check, causing a 401 from OpenRouter at runtime.

**How confirmed**: Read `.env` lines 8-9 and `llm.py` line 43.

**Impact**: `/curriculum/generate` and `/copilot/message` return 500 errors. `/health`
reports `"llm_connected": false`. Any teammate using this `.env` without noticing gets
opaque failures.

**Fix**: Replace placeholder with a real key, or add a format check at startup.

---

### ISSUE 7 — `LearnerProfile` schema declares `first_name` as required; query returns `user_first_name`
**Severity**: Latent bug; copilot addresses learners with empty name

**What's wrong**: `app/schemas.py` lines 18-20 declare `first_name: str`, `last_name: str`
as required. But `get_learner_profile()` aliases `u.first_name as user_first_name` (lines
306-307) to disambiguate from `trainees.first_name` in the JOIN.

The dict returned has key `user_first_name`, not `first_name`. The current code never
validates the dict against `LearnerProfile`, so no crash — but `build_copilot_prompt()`
calls `learner_profile.get('first_name', '')` which silently returns `''`. Learners are
addressed with no name.

**How confirmed**: Read `tsp_client.py` query aliases, `schemas.py` fields, and
`main.py` lines 204-207.

**Fix**: Either (a) add `tr.first_name` from `trainees` table directly to SELECT,
(b) map `user_first_name → first_name` before returning, or (c) change prompt builder
to use the actual alias key.

---

### ISSUE 8 — No timeout/dependency failure demo scenario wired
**Severity**: Missing required demo scenario per project brief Section 7

The brief Section 7 requires: *"One failure-handling scenario (e.g., timeout or dependency failure)."*

The demo (`demo/app.py`, read in full) covers only scenarios (a)–(e). No timeout or
service failure scenario exists in the demo, evaluation plan, or handoff doc.

**Fix**: Add a button that triggers a simulated failure — e.g., request to a bad URL,
or a `/test/timeout` endpoint that sleeps to trigger the httpx 120s timeout.

---

### ISSUE 9 — `docs/evaluation_results.md` does not exist
**Severity**: Missing required deliverable per brief Section 9

`README.md` line 103 and `evaluation_plan.md` line 6 both reference this file. It does
not exist. The template is already in `evaluation_plan.md` lines 162-197.

**Fix**: Create the file and fill it in after running the test suite.

---

## Unable to Verify (Requires Running System)

1. Whether TSP tables (`trainings`, `modules`, `lessons`, `contents`, `audience_profiles`,
   `trainees`, `users`, `objectives`, `outcomes`, `base_data.*`) exist with the columns
   TSPClient queries — cross-checked against `tsp_schema_map.md` only; cannot confirm live

2. Whether `ai_content_chunks` and `ai_generated_curricula` tables have been created in DB

3. Whether chunks exist in `ai_content_chunks` and whether they were produced by real
   MiniLM or the fallback hasher — `limitations.md` claims 37 chunks across 14 trainings

4. Whether `/health`, `/curriculum/generate`, and `/copilot/message` return valid responses

5. Whether the 7 tests actually pass (two require live LLM + DB; OpenRouter key is a placeholder)

6. Whether Layer 2 LLM injection classifier catches rephrased injections in practice

7. Whether Gemma produces valid JSON matching the `Curriculum` schema within 3 retries

8. Whether retrieved chunks for real questions are topically relevant (not just above threshold)

9. Whether demo training `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc` exists with the 4 modules shown

---

## Recommended Fix Order

| Priority | Action | Effort |
|---|---|---|
| 1 | Set real OpenRouter API key in `.env` | 5 min |
| 2 | Update 4 doc files: `ai_responses` → `ai_generated_curricula` | 15 min |
| 3 | Replace fake UUID in `demo/app.py` with real cross-training trainee ID | 5 min |
| 4 | Fix `get_learner_profile()` to return `first_name`/`last_name` correctly | 10 min |
| 5 | Remove or fill the `{placeholder}` lines in `CURRICULUM_SYSTEM_PROMPT` | 5 min |
| 6 | Tell Teammate 4 that `is_learner_enrolled()` is already built | 5 min |
| 7 | Add timeout/failure demo scenario to `demo/app.py` | 30 min |
| 8 | Update test count in report and contribution statement to 7 | 5 min |
| 9 | Decide and document the TSPClient boundary rule (Issue 1) | 15 min |
| 10 | Create `docs/evaluation_results.md` with actual test run output | After fixing above |

---

*Report prepared by: Antigravity audit agent, 2026-09-18.  
All findings based on direct file reading. No findings are inferred or fabricated.  
Shell execution was unavailable; live system verification remains outstanding.*
