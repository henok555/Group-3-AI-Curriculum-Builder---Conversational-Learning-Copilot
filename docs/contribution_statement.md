# Individual Contribution Statement — Lead Architect

**Name**: Vini (Lead)  
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
