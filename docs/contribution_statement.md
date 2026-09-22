# Individual Contribution Statement — Teammate 1 (Henok - Lead Architect)

**Name**: Henok (Teammate 1 - Lead)  
**Role**: TSP Integration, Service Architecture, Security Guardrails, RAG Pipeline & Handoff  
**Target System**: TSP AI Service (`tsp-ai-service/`)  

---

## Technical Accomplishments & Code Review Fixes

### 1. Lead TSP Integration & Database Client (`app/tsp_client.py`)
* Built asynchronous database connection pool (`asyncpg`) connecting to live `training_solutions` PostgreSQL.
* Executed SQL migrations (`docs/db_migrations.sql`) establishing `ai_content_chunks`, `ai_generated_curricula`, and `ai_responses`.
* Implemented `is_learner_enrolled(learner_id, training_id)` for cross-training authorization checks.
* Implemented idempotent curriculum saving (`save_generated_curriculum`) using PostgreSQL JSONB semantic equality (`curriculum_json = $2::jsonb`).

### 2. RAG Retrieval & Vector Embeddings (`app/retrieval.py` & `scripts/index_content.py`)
* Indexed 37 accepted training materials across 14 live trainings into `ai_content_chunks`.
* Built multi-mode embedding architecture with transparent embedder status tracking (`minilm` vs `fallback`).
* Documented `pgvector` host system absence (tested `CREATE EXTENSION vector` -> missing control files) and implemented in-Python numpy cosine similarity over `float[]` array columns.

### 3. FastAPI Web Service & Security Guardrails (`app/main.py`)
* Implemented endpoints `GET /health`, `POST /curriculum/generate`, and `POST /copilot/message`.
* Integrated 2-layer injection security guardrails: Fast regex (Layer 1) + LLM intent classifier (Layer 2).
* Added embedder health status reporting (`embedding_model_connected`, `embedding_model_status`) to `GET /health`.
* Added `embedder` tag to every `CopilotResponse` payload.

### 4. Automated Testing Suite (`tests/test_api.py`)
* Wrote 8 comprehensive integration tests against the live database (100% passing).
* Covered `/health` monitoring, regex & LLM injection guardrails, fallback behavior, cross-training authorization checks, malformed request validation (422), and curriculum save idempotency.

---

# Individual Contribution Statement — AI Curriculum Builder & Exporter

**Name**: Teammate 2  
**Role**: AI Curriculum Builder, Cold-Start Synthesis Engine, Word (.docx) Exporter, AI Drafting Assistant  
**Target System**: TSP AI Service (`tsp-ai-service/`)  

---

## Technical Accomplishments & Key Contributions

### 1. Cold-Start Curriculum Generation from Scratch (`app/curriculum_builder.py` & `app/main.py`)
* Implemented `POST /curriculum/generate-custom` endpoint and `CustomCurriculumRequest` schema.
* Designed synthesis pipeline in `app/curriculum_builder.py` so LLM infers module divisions, pacing, Bloom’s taxonomy objectives, rubrics, quizzes, and surveys purely from custom title, rationale, and scope.
* Integrated DB persistence: custom curriculums automatically create corresponding rows in `trainings` table and persist full JSON in `ai_generated_curricula`.

### 2. Multi-Modal Candidate Resources & Pedagogy Evaluation (`app/schemas.py` & `demo/app.py`)
* Upgraded `MediaResource` schema to support multi-modal learning categories (`VIDEO`, `DOCS`, `LAB`).
* Added evaluative metadata fields: `is_primary`, `difficulty_level`, `estimated_time`, and `pedagogy_notes`.
* Implemented rich visual cards in Streamlit UI with badges (`⭐ [Top Recommendation]`, `[DOCS]`, `[LAB]`) and video previews.

### 3. AI Drafting Assistant (`app/curriculum_builder.py` & `app/main.py`)
* Built `enhance_course_draft()` and exposed `POST /curriculum/enhance-draft`.
* Polishes spelling/tone, expands problem statements into business rationale with ROI metrics, structures technical scope boundaries, and recommends concrete prerequisites.
* Added interactive **✨ AI Assist: Polish & Expand Draft** button in Streamlit UI.

### 4. Publication-Ready Word (.docx) Export Engine (`app/docx_exporter.py`)
* Built standalone document generator using `python-docx` creating publication-grade Word documents.
* Designed layout with styled tables, headers, executive summaries, lesson outlines, rubrics, and survey instruments.
* Exposed via `POST /curriculum/export-docx` and integrated one-click download in Streamlit UI.

---

# Individual Contribution Statement — RAG & Copilot Architect

**Name**: Teammate 3  
**Role**: RAG Pipeline, Document Ingestion, Retrieval Optimization, Personalization Engine & Benchmarking  
**Target System**: TSP AI Service (`tsp-ai-service/`)  

---

## Technical Accomplishments & Key Contributions

### 1. Document Extraction & Semantic Chunking Engine (`app/retrieval.py` & `scripts/index_content.py`)
* **Multi-Format Document Extraction**: Implemented robust extraction for PDF training manuals and external learning documents (`extract_text_from_pdf_bytes`, `extract_text_from_link`) using `pypdf` with fallback resilience.
* **Abbreviation-Aware Sentence Tokenizer**: Engineered `split_into_sentences()` to handle punctuation edge cases, numbered lists, and academic/professional abbreviations (`e.g.`, `i.e.`, `Dr.`, `vs.`, `etc.`), preventing arbitrary sentence fragmentation.
* **Hierarchical Context Prefixing**: Developed `semantic_chunk_text()` injecting structured domain headers `[Training | Module | Lesson | Level | Type]` into each chunk, boosting semantic alignment during vector search.
* **Contextual Overlap**: Enforced 2-sentence rolling window overlap (~350 words per chunk) to preserve conceptual continuity across chunk boundaries.

### 2. Scalable Ingestion & Index Synchronization Pipeline (`scripts/index_content.py`)
* **Batch Multi-Training Sync**: Built CLI support for indexing individual trainings or synchronizing all active TSP trainings (`--all`).
* **Clean State Refresh**: Added `--force-refresh` flag leveraging `delete_training_chunks()` in `TSPClient` to eliminate stale orphan chunks.
* **Batch Vectorization**: Streamlined batch embedding generation (`embed_texts`) with `sentence-transformers/all-MiniLM-L6-v2` producing L2-normalized 384-dimensional vectors.

### 3. Metadata-Filtered Retrieval & Source Attribution (`app/retrieval.py`)
* **Granular Filtering**: Upgraded `retrieve_relevant_chunks()` to support dynamic metadata filters (`module_id`, `lesson_id`, `level`, `file_type`) alongside strict `training_id` tenant isolation.
* **Deduplication & Calibration**: Added chunk deduplication and calibrated similarity thresholding (`0.30`) to block ungrounded retrieval.
* **Strict Provenance**: Delivered structured `SourceAttribution` mapping each response to exact TSP module and lesson entities.

### 4. 3-Tier Learner Personalization Engine (`app/main.py`)
* **Dynamic Pedagogical Profiling**: Built `derive_learner_pedagogy()` and `get_personalized_copilot_system_prompt()`, categorizing trainees into 3 distinct tiers (Beginner, Intermediate, Advanced) based on `academic_level`, `employment_status`, and `has_training_experience`.
* **Adaptive Pacing & Vocabulary**: Dynamically customizes explanation tone, analogy style, and next-activity recommendations (quizzes vs. practical assignments vs. peer mentoring).
* **Multi-Turn Context**: Enhanced conversation history window (last 6 turns) with contextual query resolution.

### 5. Quantitative Evaluation Suite & Automated Testing (`scripts/evaluate_retrieval.py` & `tests/test_rag.py`)
* **Automated Evaluation Benchmark**: Developed `scripts/evaluate_retrieval.py` calculating Mean Precision@5, Mean Reciprocal Rank (MRR), and Out-of-Domain Refusal Accuracy.
* **Comprehensive Test Suite**: Authored `tests/test_rag.py` covering sentence splitting, semantic chunking, cosine similarity properties, embedder normalization, and extraction error resilience (100% test pass rate).

---

# Individual Contribution Statement — Copilot Sessions & Evidence-Based Personalization

**Name**: Abel (Teammate 4)
**Role**: Conversational Copilot — Multi-Turn Context, Learner Profiling, Performance-Based Personalization, Next-Activity Engine
**Grading areas fed**: RAG/Copilot (12%, shared) + Learner Profiling & Personalization (8%)

---

## Technical Accomplishments

### 1. Server-Side Multi-Turn Session Architecture (`app/session_store.py`, `app/tsp_client.py`, `docs/db_migrations.sql`)
* Designed and built a two-layer conversation memory: an in-memory `SessionStore` (20-turn window, per-session isolation) backed by a new `ai_copilot_sessions` PostgreSQL table (one row per turn, indexed by session and by learner).
* `POST /copilot/message` now accepts and returns a `session_id` — clients continue conversations without re-sending history; sessions survive service restarts through DB hydration (`get_copilot_session_history`).
* Persistence is best-effort by design: a missing table or failed write degrades gracefully to memory-only, never breaking answering. Guardrail refusals are also recorded so multi-turn context stays faithful.
* Implemented `get_recent_learner_interactions()` — the learner's previous copilot interactions across sessions, a required learner-profile element.

### 2. Evidence-Based Learner Progress Aggregation (`TSPClient.get_learner_progress`)
* Aggregates real TSP evidence per learner: attendance rate from `attendances`/`sessions`, cohort session timeline (last attended + next unattended session), and **weight-normalized** assessment percentages (`Σ score / Σ weight`) from `assessment_answers` → `assessment_entries` → `assessments`, including the weakest assessment area.
* Resolves `learner_id` as either `trainee.id` or `user.id` within the training; returns `{}` when no evidence exists so nothing downstream can fabricate progress.

### 3. Performance-Adaptive Personalization (`derive_performance_adaptation` in `app/main.py`)
* Layered a data-driven performance dimension (struggling / on_track / excelling / no_evidence, with explicit thresholds) on top of the demographic 3-tier system, satisfying the assignment's "personalization must be based on actual learner evidence from TSP, not only prompt wording".
* Struggling learners get remedial framing pointed at their actual weakest assessment area; excelling learners get depth and stretch work; the evidence summary and adaptation directive are injected into both system and user prompts and surfaced in a structured `personalization` response field.

### 4. Deterministic Next-Activity Recommendation Engine (`recommend_next_activity` in `app/main.py`)
* Computes the recommended next activity **in code from TSP records** — never hallucinated by the LLM — with an explicit "why" citing real scores, schedule dates, and attendance (assignment: "Recommend the next learning activity" + "Explain why an activity is recommended").
* Five-rule decision order: remediate weakest area → attend next scheduled cohort session → stretch work when excelling → consolidate when schedule complete → honest profile-only fallback when TSP holds no evidence.

### 5. Personalization, Multi-Turn & Safety Evaluation (`scripts/evaluate_personalization.py`, `tests/test_copilot.py`)
* Built the live evaluation required of Teammate 4 by `docs/evaluation_plan.md`: same question asked as 3 real learners (distinct academic levels) with pairwise Jaccard differentiation scoring; multi-turn coherence verified against both the in-memory store and `ai_copilot_sessions`; safety suite re-verifying injection blocking, honest refusal, and cross-training access denial — results written to `docs/evaluation_personalization.md`.
* Authored `tests/test_copilot.py` — 18 unit tests (no DB/LLM required) covering performance thresholds, recommendation decision order, session round-trip/isolation/trimming/hydration, prompt assembly, and injection-pattern regression.

### 6. Documentation (`docs/copilot_personalization.md`)
* Full design specification: session architecture, TSP-evidence data mapping, adaptation rules, API changes, evaluation methodology, and known limitations.
