# TSP Database Schema Map

**Database**: `training_solutions` (PostgreSQL)
**Discovered**: 2026-01-18 via direct inspection
**Total tables**: 139 (public schema) + 31 (base_data schema)

---

## Core Training Tables

### `public.trainings` — Central entity
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| created_at / updated_at | timestamp(6) | Audit |
| created_by / updated_by | varchar(255) | User emails |
| title | text | Training name |
| executive_summary | text | Brief overview |
| rationale | text | Why this training exists |
| scope | text | What's covered (structured text with +| separators) |
| professional_background | text | Expected trainer background |
| delivery_method | varchar(255) | CHECK: OFFLINE, VIRTUAL, BLENDED |
| duration | double precision | |
| duration_type | varchar(255) | CHECK: MINUTES..YEARS |
| attendance_requirement_percentage | double precision | |
| assessment_result_percentage | double precision | Pass threshold |
| start_date / end_date | date | |
| total_participants | integer | |
| is_deleted | boolean | Soft delete |
| is_edge_product | boolean | |
| is_synced_with_edge | boolean | |
| product_key | varchar(255) | |
| certificate_description | text | |
| company_profile_id | uuid | FK → company_profiles.id |
| training_type_id | uuid | FK → base_data.training_types.id |

**Referenced by**: 30+ tables (modules, audience_profiles, assessments, surveys, cohorts, contents, objectives, etc.)

---

### `public.audience_profiles` — One per training
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id, UNIQUE |
| education_level_id | uuid | FK → base_data.education_levels.id |
| language_id | uuid | FK → base_data.languages.id |
| learner_level_id | uuid | FK → base_data.learner_levels.id |
| work_experience_id | uuid | FK → base_data.work_experiences.id |
| certifications | text | Free text |
| licenses | text | Free text |

**Referenced by**: specific_courses, specific_prerequisites

---

### `public.modules` — Training modules (ordered)
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| module_id | uuid | FK → modules.id (self-ref for sub-modules) |
| name | varchar(255) | Module title |
| description | text | |
| key_concepts | text | Core topics |
| teaching_strategy | text | |
| differentiation_strategies | text | |
| inclusion_strategy | text | |
| duration | double precision | |
| duration_type | varchar(255) | CHECK: MINUTES..YEARS |
| technology_integration_description | text | |
| technology_integration_id | uuid | FK → base_data.technology_integrations.id |
| training_tag_id | uuid | FK → base_data.training_tags.id |
| module_order | integer | Display order |

**Referenced by**: lessons, contents, training_references, module_* tables, modules_users, modules_assessment_types, modules_instructional_methods, module_digital_tools

---

### `public.lessons` — Lessons within modules
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| module_id | uuid | FK → modules.id |
| name | varchar(255) | Lesson title |
| description | text | |
| objective | text | Learning objective |
| duration | double precision | NOT NULL |
| duration_type | varchar(255) | CHECK: MINUTES..YEARS |

**Referenced by**: session_lessons, contents, lesson_instructional_methods, lesson_technology_integrations

---

### `public.contents` — Content Requests (called "contents" in DB)
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| module_id | uuid | FK → modules.id |
| lesson_id | uuid | FK → lessons.id (nullable) |
| assessment_id | uuid | FK → assessments.id (nullable) |
| user_id | uuid | FK → users.id (content developer) |
| name | varchar(255) | Content title |
| description | text | |
| file_type | varchar(255) | CHECK: PDF, VIDEO, LINK |
| level | varchar(255) | CHECK: MODULE, LESSON, ASSESSMENT |
| status | varchar(255) | CHECK: PENDING, ACCEPTED, REJECTED |
| link | text | Google Drive / external URL |
| reference_link | text | Additional reference |
| rejection_reason | text | If rejected |
| time_to_read_minutes | integer | Estimated read time |

**Note**: This is the "Content Requests" entity from the manual. Only `status = 'ACCEPTED'` content is usable for RAG.

---

### `public.assessments` — Training-level assessments
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| content_developer_id | uuid | FK → users.id |
| name | varchar(255) | |
| description | text | |
| assessment_type | varchar(255) | CHECK: PRE_POST, CAT, OTHER |
| assessment_target | varchar(255) | CHECK: INDIVIDUAL, GROUP |
| assessment_approval_status | varchar(255) | CHECK: PENDING, APPROVED, REJECTED |
| duration | integer | Minutes |
| is_timed | boolean | |
| max_attempts | integer | |

**Referenced by**: assessment_sections, assessment_cohorts, group_assessments, contents

---

### `public.assessment_sections` — Sections within assessment
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| assessment_id | uuid | FK → assessments.id |
| title | varchar(255) | |
| description | text | |
| section_number | integer | Order |

---

### `public.assessment_entries` — Questions within sections
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| section_id | uuid | FK → assessment_sections.id |
| question | text | |
| question_type | varchar(255) | CHECK: TEXT, RADIO, CHECKBOX, FILE_UPLOAD |
| question_number | integer | |
| weight | numeric(38,2) | |
| question_image_url | text | |
| allowed_file_types | varchar(255) | |
| max_file_size_mb | integer | |

**Referenced by**: assessment_entry_choices, assessment_answers

---

### `public.surveys` — Training surveys
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| session_id | uuid | FK → sessions.id |
| name | varchar(255) | |
| description | text | |
| survey_type | varchar(255) | CHECK: BASELINE, ENDLINE, OTHER |

---

### `public.survey_sections` / `survey_entries` — Survey structure (similar to assessments)

---

### `public.objectives` — Training objectives (hierarchical)
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| objective_id | uuid | FK → objectives.id (parent, nullable) |
| definition | text | Objective text |

**Referenced by**: outcomes

---

### `public.outcomes` — Measurable outcomes per objective
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| objective_id | uuid | FK → objectives.id |
| definition | text | Outcome statement |

---

### `public.users` — All system users
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| email | varchar(255) | |
| username | varchar(255) | UNIQUE |
| first_name / last_name | varchar(255) | |
| role_id | uuid | FK → roles.id |
| is_active | boolean | NOT NULL |
| is_email_verified | boolean | |
| password | varchar(255) | Hashed |

---

### `public.roles` — Role definitions
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| name | varchar(255) | CHECK: ROLE_CURRICULUM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_CONTENT_DEVELOPER, ROLE_TRAINEE, etc. |
| color_code | varchar(255) | UNIQUE |

---

### `public.trainees` — Learner profiles (extends users)
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → users.id |
| training_id | uuid | FK → trainings.id |
| cohort_id | uuid | FK → cohorts.id |
| first_name / last_name / middle_name | varchar(255) | |
| email | varchar(255) | |
| date_of_birth | date | |
| gender | varchar(255) | CHECK: MALE, FEMALE |
| field_of_study | varchar(255) | |
| academic_level_id | uuid | FK → base_data.academic_levels.id |
| language_id | uuid | FK → base_data.languages.id |
| city_id / zone_id | uuid | FK → base_data.cities/zones |
| employment_status | varchar(255) | CHECK: EMPLOYED, UNEMPLOYED, STUDENT, etc. |
| marital_status | varchar(255) | |
| has_smart_phone | boolean | |
| has_training_experience | boolean | |
| training_experience_description | varchar(255) | |
| number_of_children | integer | |
| is_self_registered | boolean | |
| consent_form_url | text | |
| did_sign_consent_form | boolean | |

---

## Module Detail Tables (Many-to-Many via base_data)

### `public.modules_instructional_methods` (module_id, instructional_method_id)
→ `base_data.instructional_methods` (id, name, description)

### `public.module_digital_tools` (module_id, digital_tools text)
Free-text field (not normalized)

### `public.module_primary_materials` (module_id, primary_materials text)
Free-text field

### `public.module_secondary_materials` (module_id, secondary_materials text)
Free-text field

### `public.modules_assessment_types` (module_id, assessment_type_id)
→ `base_data.assessment_types` (id, name)

### `public.lesson_instructional_methods` (lesson_id, instructional_method_id)
→ `base_data.instructional_methods`

### `public.lesson_technology_integrations` (lesson_id, technology_integration_id)
→ `base_data.technology_integrations` (id, name, description)

### `public.training_references` (id, module_id, definition)
References/bibliography per module

---

## Cohort / Session Tables (Runtime)

### `public.cohorts` — Training cohorts
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| name | varchar(255) | |
| start_date / end_date | date | |
| status | varchar(255) | |

### `public.sessions` — Training sessions
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| cohort_id | uuid | FK → cohorts.id |
| module_id | uuid | FK → modules.id |
| trainer_id | uuid | FK → trainers.id |
| start_time / end_time | timestamp | |

---

## Base Data Reference Tables (31 tables in `base_data` schema)

Key ones used:
- `education_levels` (id, name, description) — e.g., "Professional Certification"
- `languages` (id, name, code, alternate_names) — e.g., "English" (en)
- `learner_levels` (id, name, description) — e.g., "Intermediate"
- `work_experiences` (id, name, description) — e.g., "Professional Development"
- `instructional_methods` (id, name, description) — "Lecture", "Discussion-Based", etc.
- `technology_integrations` (id, name, description) — "Presentation tools (PowerPoint/Canva)"
- `assessment_types` (id, name) — "Polling", "Portfolio"
- `training_purposes` (id, name) — "Skill Development"
- `training_tags` (id, name) — Module tags
- `cities`, `zones`, `regions` — Geographic
- `academic_levels`, `age_groups`, `economic_backgrounds`, `marginalized_groups`, `disabilities` — Demographics

---

## Demo Training Identified

**Training**: `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc` — "Leyu Facilitators and Trainers Training"
- **Audience Profile**: `51d97248-ef66-4846-8845-be0cdc44cbaf`
  - Education: Professional Certification
  - Language: English
  - Learner Level: Intermediate
  - Work Experience: Professional Development
- **Modules**: 4 (3 with lessons, 1 empty)
  - Module 1: Orientation and Trainer's Role (3 lessons)
  - Module 2: Training of Trainers (ToT) (4 lessons)
  - Module 3: Photography & Videography (2 lessons)
  - Module 4: Soft Skill (0 lessons)
- **Total Lessons**: 9
- **Accepted Contents**: 5 (all MODULE-level PDFs on Google Drive)
- **Objectives**: 6 (1 parent + 5 children)
- **Outcomes**: 4
- **Assessments**: 0
- **Surveys**: 0
- **Module Instructional Methods**: Lecture, Discussion-Based
- **Module Assessment Types**: Polling, Portfolio (Module 1 only)
- **Primary Materials**: Slide decks per module
- **Training Keywords**: "Capacity Building", "Safeguarding"

---

## Discrepancies vs. Manual Expectations

| Manual Entity | Actual Table | Notes |
|---------------|--------------|-------|
| Training Profiles | `audience_profiles` + `objectives` + `trainings` | Split across 3 tables |
| Content Requests | `contents` | Same data, different name |
| Module Details | `modules` + `module_*` tables | Normalized into 7 tables |
| Lessons/Sub-modules | `lessons` | No sub-module level (modules self-ref) |
| Surveys | `surveys` + `survey_sections` + `survey_entries` | Matches |
| Assessments | `assessments` + `assessment_sections` + `assessment_entries` | Matches |
| Users/Roles | `users` + `roles` + `trainees` | Trainees separate from users |

---

## Write Access Test

```sql
BEGIN; SELECT 1; ROLLBACK;
```
**Result**: SUCCESS — credentials have write access to `public` schema.

---

## pgvector Status

**NOT INSTALLED** on the PostgreSQL server (`/usr/share/postgresql/16/extension/vector.control` missing). Cannot use `vector` type or `ivfflat` index natively. Workaround: store embeddings as `float[]` and compute cosine similarity in application layer (see `app/retrieval.py`).

---

## AI Service–Owned Tables (created by this service, not TSP)

### `public.ai_content_chunks` — RAG vector index (float[] fallback)
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| content_id | uuid | FK → contents.id |
| module_id | uuid | FK → modules.id |
| lesson_id | uuid | FK → lessons.id (nullable) |
| chunk_text | text | 300–500 word chunk |
| chunk_index | integer | chunk position within content |
| embedding | float[] | 384-dim L2-normalized vector (all-MiniLM-L6-v2) |
| file_type | varchar(50) | mirrored from contents |
| level | varchar(50) | MODULE / LESSON / ASSESSMENT |
| created_at | timestamp | index time |

### `public.ai_generated_curricula` — AI curriculum output store
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| training_id | uuid | FK → trainings.id |
| curriculum_json | jsonb | Full generated Curriculum object |
| generated_at | timestamp | generation time |
| generated_by | varchar(255) | default: 'ai_service' |

**Note**: `ai_responses` (existing TSP table) was not used for curriculum storage because its `request_type` CHECK constraint only allows `'EXECUTIVE_SUMMARY'` and `'DIFFERENTIATION_STRATEGY'`.
