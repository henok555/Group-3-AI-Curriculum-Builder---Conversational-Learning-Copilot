# Individual Contribution Statement — AI Curriculum Builder

**Role**: AI Curriculum Builder & Instructional Design Engineering  
**Branch**: `feat/curriculum-builder`  
**Focus Area**: End-to-End Curriculum Synthesis, Cold-Start Generation, Multi-Modal Resource Evaluation, AI Specification Assistant, and Word (.docx) Publication  

---

## Overview

As part of Group 3's AI Curriculum Builder & Conversational Learning Copilot, my primary responsibility was turning raw training profiles and client requirements into complete, pedagogically sound, and actionable curricula. 

While the initial scaffold supported basic curriculum generation for trainings that already had pre-populated modules in the database, real-world instructional designers often start from scratch with just a title, a rough paragraph, or a high-level problem statement. Furthermore, a curriculum is only as good as its learning resources and its final deliverable format. 

Over this milestone, I expanded the system into an end-to-end curriculum engineering engine that can generate complete courses from cold start, recommend multi-modal learning candidates with pedagogical rationale, assist creators in refining course drafts, persist full version histories in PostgreSQL, and export everything directly into clean, publication-ready Word documents.

---

## Key Features & What I Built

### 1. Cold-Start Curriculum Generation from Scratch
* **The Problem**: Previously, curriculum generation assumed pre-existing modules and audience rows in the TSP database. If an organization or trainer wanted to design a completely new course, the system had no way to handle it.
* **What I Did**:
  * Implemented the `POST /curriculum/generate-custom` endpoint and `CustomCurriculumRequest` schema.
  * Designed the prompting and synthesis pipeline in `app/curriculum_builder.py` so the LLM infers optimal module divisions, pacing, Bloom’s taxonomy objectives, rubrics, quizzes, and surveys purely from a topic title, business rationale, target learner level, and scope.
  * Integrated database persistence: when a custom curriculum is generated, it automatically creates a corresponding row in the PostgreSQL `trainings` table and saves the full curriculum JSON to `ai_generated_curricula`, ensuring full relational integrity.

### 2. Multi-Modal Candidate Resources & Pedagogy Evaluation
* **The Problem**: A single static link or automated video recommendation is rarely enough for a curriculum designer. Instructors need choices and need to understand *why* a particular resource is recommended.
* **What I Did**:
  * Upgraded `MediaResource` schema to support multi-modal learning categories:
    1. **Primary Video Lecture** (`VIDEO`) — focused architectural or conceptual walkthrough.
    2. **Authoritative Documentation / Standards** (`DOCS`) — technical documentation, whitepapers, and official guides.
    3. **Hands-on Sandbox / Code Lab** (`LAB`) — interactive playgrounds, repositories, or lab exercises.
  * Added evaluative metadata fields: `is_primary`, `difficulty_level`, `estimated_time`, and `pedagogy_notes`.
  * The AI now generates explanatory pedagogy notes for every resource explaining its instructional value, allowing curriculum creators to compare alternatives and pick the best option.
  * Implemented rich visual cards in the Streamlit UI with badges (`⭐ [Top Recommendation]`, `[DOCS]`, `[LAB]`) and integrated video players.

### 3. AI Drafting Assistant ("✨ AI Assist: Polish & Expand Draft")
* **The Problem**: When curriculum designers start writing a course proposal, their initial notes are often informal, grammatically rough, or lack structured technical boundaries.
* **What I Did**:
  * Built `enhance_course_draft()` in `app/curriculum_builder.py` and exposed `POST /curriculum/enhance-draft`.
  * When a user inputs a rough course idea, the AI assistant:
    - Polishes spelling, tone, and professional phrasing.
    - Transforms brief problem statements into business rationale with clear operational outcomes and ROI metrics.
    - Organizes rough scopes into structured technical domains and explicit out-of-scope boundaries.
    - Recommends concrete prerequisites and calibrated course durations.
  * Added an interactive **`✨ AI Assist: Polish & Expand Draft`** button in the Streamlit UI with safe, versioned form state handling.

### 4. Direct Word Document (.docx) Export Engine
* **The Problem**: Instructors and training managers need formatted, offline deliverables to submit to stakeholders, clients, or accreditation boards.
* **What I Did**:
  * Built a standalone document generator in `app/docx_exporter.py` using `python-docx`.
  * Designed a publication-ready document layout with styled tables, headers, and callouts:
    - Executive summary and metadata table (duration, delivery method, target audience).
    - Detailed module outlines with lesson descriptions, Bloom's levels, and candidate resource tables.
    - Assessment rubrics with criteria descriptions and point weights.
    - Pre/post assessment question banks and baseline/endline survey instruments.
  * Exposed this via `POST /curriculum/export-docx` and added a one-click **`📥 Download Complete Curriculum Document (.docx)`** button in Streamlit.
  * Configured automatic persistence so every exported document is also saved directly into the workspace `resources/` folder.

### 5. Database History & Saved Curriculum Browser
* **The Problem**: Trainers needed a way to revisit past generations, compare iterations, and download documents without having to re-generate from the LLM each time.
* **What I Did**:
  * Added `get_all_recent_curricula()` and `get_curriculum_by_db_id()` in `app/tsp_client.py`.
  * Implemented `GET /curriculum/recent` and `GET /curriculum/version/{curriculum_db_id}` in `app/main.py`.
  * Built the **`📜 Recent Curriculums (Saved in DB)`** subtab in Streamlit. Users can browse all saved runs from PostgreSQL, view timestamps and module counts, load the full curriculum into the viewer, and export `.docx` files on demand without consuming API tokens.

### 6. Resilience & Fail-Fast Rate Limit Handling
* **The Problem**: Free-tier OpenRouter keys would hit the daily 50-request limit (`429`), causing exponential backoff sleep loops (10s, 20s, 40s, 80s) that froze the backend and triggered browser timeout errors.
* **What I Did**:
  * Updated `call_gemma()` in `app/llm.py` to immediately detect `openrouter_free_tier_daily` / `free-models-per-day`.
  * Made it fail fast with a clear, actionable message advising the user to update their key, eliminating multi-minute UI freezes.
  * Added non-blocking timeouts to the startup LLM check in `app/main.py` so server reboots are instantaneous.

---

## Files Modified and Created

- **`app/curriculum_builder.py`**: Multi-modal resource generator, pedagogy notes synthesis, draft enhancement logic, and prompt engineering.
- **`app/docx_exporter.py`** *(New)*: Standalone document generator creating publication-grade Word `.docx` files.
- **`app/tsp_client.py`**: Custom training table creation, recent curricula history queries, and DB id lookups.
- **`app/schemas.py`**: Added `DraftEnhanceRequest`, `DraftEnhanceResponse`, and enhanced `MediaResource` with pedagogy and evaluation fields.
- **`app/main.py`**: Added `/curriculum/generate-custom`, `/curriculum/enhance-draft`, `/curriculum/recent`, `/curriculum/version/{id}`, and `/curriculum/export-docx` endpoints.
- **`demo/app.py`**: Integrated the custom scratch builder, AI draft assistant, recent curriculum browser, resource evaluation viewer, and Word export buttons.
- **`app/llm.py`**: Fail-fast daily quota error handling to prevent UI timeouts.

---

## How to Test My Work

1. **Start the services**:
   ```bash
   uvicorn app.main:app --port 8000
   streamlit run demo/app.py --server.port 8501
   ```
2. **Test AI Assist**:
   - Open Streamlit → Curriculum tab → **✨ Create from Scratch (Custom Specification)**.
   - Enter a rough title and draft scope, then click **`✨ AI Assist: Polish & Expand Draft`**.
   - Notice how the business rationale, technical scope, and prerequisites are automatically expanded and structured.
3. **Test Generation & Multi-Modal Resources**:
   - Click **`🚀 Generate Curriculum from Scratch`**.
   - Expand any module/lesson to inspect the curated candidate resources (`VIDEO`, `DOCS`, `LAB`), their difficulty levels, estimated times, and pedagogy notes.
4. **Test Word Export**:
   - Click **`📥 Download Complete Curriculum Document (.docx)`** to download the full syllabus.
   - Check the `resources/` folder to see the saved document asset.
5. **Test History Browser**:
   - Switch to the **`📜 Recent Curriculums (Saved in DB)`** subtab.
   - Click **`👁️ Load`** on any saved item to retrieve and inspect previous curriculum generations directly from PostgreSQL.
