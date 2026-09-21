# Data Mapping — TSP Fields → AI Service Usage

## Curriculum Generation Inputs

| TSP Field | Table | Used For |
|---|---|---|
| `title` | `trainings` | Curriculum title, prompt heading |
| `rationale` | `trainings` | Why this training exists (prompt context) |
| `scope` | `trainings` | Coverage scope for module design |
| `executive_summary` | `trainings` | High-level overview in prompt |
| `delivery_method` | `trainings` | Informs instructional method selection |
| `duration` / `duration_type` | `trainings` | Total time allocation guidance |
| `definition` | `objectives` | Learning objective hierarchy in prompt |
| `definition` | `outcomes` | Measurable outcomes per objective |
| `name` (module) | `modules` | Module title (LLM uses as structural scaffold) |
| `description` | `modules` | Module summary |
| `key_concepts` | `modules` | Core topics the LLM expands on |
| `teaching_strategy` | `modules` | Pedagogical approach hint |
| `module_order` | `modules` | Ordering constraint for LLM |
| `duration` / `duration_type` | `modules` | Per-module time budget |
| `name` (lesson) | `lessons` | Lesson titles in prompt |
| `objective` | `lessons` | Per-lesson learning goal |
| `duration` | `lessons` | Per-lesson time |
| `name` (instructional method) | `instructional_methods` | Informs generated assignment/lesson types |
| `name` (assessment type) | `assessment_types` | Informs generated assessment types |
| `primary_materials` | `module_primary_materials` | Reference materials for generated content |
| `name` (content) | `contents` | Accepted content referenced in curriculum |
| `education_level` | `base_data.education_levels` | Audience calibration in prompt |
| `learner_level` | `base_data.learner_levels` | Difficulty calibration (e.g., Intermediate) |
| `work_experience` | `base_data.work_experiences` | Professional context |
| `language_name` | `base_data.languages` | Output language guidance |
| `specific_courses` | `specific_courses` | Prerequisite context |
| `specific_prerequisites` | `specific_prerequisites` | Prerequisite context |
| `certifications` / `licenses` | `audience_profiles` | Target credential level |

## Copilot Personalization Inputs

| TSP Field | Table | Used For |
|---|---|---|
| `first_name` / `last_name` | `trainees` | Personalized greeting in response |
| `employment_status` | `trainees` | Tailor answer to work context |
| `academic_level` | `base_data.academic_levels` | Adjust answer complexity |
| `language_name` | `base_data.languages` | Language preference note |
| `field_of_study` | `trainees` | Domain-specific framing |
| `has_training_experience` | `trainees` | Level of jargon to use |
| `role_name` | `roles` (via `users`) | Role-appropriate framing |
| `city_name` / `zone_name` | `base_data.cities/zones` | Geographic context (if relevant) |

## RAG Retrieval Inputs

| TSP Field | Table | Indexed Into `ai_content_chunks` |
|---|---|---|
| `id` | `contents` | `content_id` — primary FK |
| `name` | `contents` | Resource title in chunk body |
| `description` | `contents` | Resource summary text |
| `link` | `contents` | PDF / external document full text extracted via `pypdf` |
| `key_concepts` | `modules` | Module key learning concepts & frameworks (e.g. 4Es) |
| `teaching_strategy` | `modules` | Instructional & facilitation strategies |
| `objective` | `lessons` | Lesson-specific learning goals & competencies |
| `description` | `lessons` | Lesson-specific instructional details |
| `file_type` | `contents` | Stored as metadata, returned in source attribution |
| `level` | `contents` | `MODULE` / `LESSON` / `ASSESSMENT` (filter option) |
| `status = 'ACCEPTED'` | `contents` | **Filter** — only accepted content is indexed |
| `module_id` | `contents` | Attribution & filter: which module a chunk came from |
| `lesson_id` | `contents` | Attribution & filter: which lesson (nullable) |

## Output Mapping (AI → TSP)

| AI Service Output | Stored In | Notes |
|---|---|---|
| Generated curriculum (dict) | `ai_generated_curricula.curriculum_json` | AI-service table; full JSONB blob |
| Embedded content chunks | `ai_content_chunks.embedding` | `float[]` array, service-owned table |
| Copilot session history | In-memory session store & DB | Preserves multi-turn dialogue |

## Fields NOT Currently Used (Identified, Not Wired)

| Field | Table | Reason |
|---|---|---|
| `assessment_sections`, `assessment_entries` | `assessments.*` | Seed demo training has 0 pre-existing assessments |
| `survey_sections`, `survey_entries` | `surveys.*` | Seed demo training has 0 pre-existing surveys |
| `time_to_read_minutes` | `contents` | Informational reading estimate |
| `cohort_id` / session data | `cohorts`, `sessions` | Not required for curriculum generation or RAG search |
