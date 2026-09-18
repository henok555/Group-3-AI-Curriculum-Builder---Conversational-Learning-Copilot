# TSPClient API Contract

> **For Teammates 2, 3, and 4 — read this before writing any code.**
>
> `TSPClient` is the **only** class in this codebase allowed to touch TSP database tables directly.
> All other modules (Curriculum Builder, RAG pipeline, Copilot) call through it.
> Never write raw SQL outside of `app/tsp_client.py`.

**File**: [`app/tsp_client.py`](../app/tsp_client.py)
**Class**: `TSPClient`
**Instantiation**: Use the singleton via `get_tsp_client()` — do not instantiate directly.

---

## How to Use It in FastAPI

```python
from app.tsp_client import TSPClient, get_tsp_client
from fastapi import Depends

@app.post("/your-endpoint")
async def your_endpoint(tsp_client: TSPClient = Depends(get_tsp_client)):
    profile = await tsp_client.get_training_profile("45d3c920-...")
```

---

## Method Reference

### `get_training_profile(training_id: str) -> dict`

Returns the complete profile for a training: base info, audience profile, objectives tree, keywords, and purposes.

**Returns empty dict `{}` if training not found.**

**Real example** (training `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc`):

```json
{
  "training": {
    "id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc",
    "title": "Leyu Facilitators and Trainers Training",
    "rationale": "The Leyu Facilitators and Trainers Orientation is needed to ensure trainers fully understand the program's objectives, standards, and delivery expectations before engaging with trainees...",
    "scope": "This training equips Leyu trainers and facilitators with the skills, knowledge, and ethical frameworks required to effectively deliver data contributor training across Ethiopia. It covers:\n\nTrainer onboarding and Leyu standards\n\nSafeguarding and professional ethics\n\nGender and social inclusion practices...",
    "delivery_method": "VIRTUAL",
    "duration": 3,
    "duration_type": "HOURS",
    "start_date": "2025-10-26",
    "end_date": "2025-10-30",
    "total_participants": 20,
    "attendance_requirement_percentage": 100.0,
    "assessment_result_percentage": 0.0,
    "company_name": "Leyu",
    "training_type_name": "...",
    "is_deleted": false
  },
  "audience_profile": {
    "id": "51d97248-ef66-4846-8845-be0cdc44cbaf",
    "training_id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc",
    "education_level": "Professional Certification",
    "education_level_desc": "...",
    "language_name": "English",
    "language_code": "en",
    "learner_level": "Intermediate",
    "learner_level_desc": "...",
    "work_experience": "Professional Development",
    "work_experience_desc": "...",
    "certifications": null,
    "licenses": null
  },
  "objectives": [
    {
      "id": "uuid-...",
      "definition": "Equip trainers to deliver Leyu program effectively",
      "children": [
        {
          "id": "uuid-...",
          "definition": "Understand Leyu mission and safeguarding standards",
          "children": [],
          "outcomes": [
            { "id": "uuid-...", "definition": "Trainers can articulate Leyu's code of conduct" }
          ]
        }
      ]
    }
  ],
  "keywords": ["Capacity Building", "Safeguarding"],
  "purposes": ["Skill Development"]
}
```

---

### `get_modules_with_lessons(training_id: str) -> list[dict]`

Returns all modules for a training, each with lessons, instructional methods, materials, assessment types, and accepted content items.

**Real example** (abbreviated — training has 4 modules, 9 lessons total):

```json
[
  {
    "id": "6cd77630-7421-4c7d-9a89-f5812086d7b7",
    "name": "Module 1: Orientation and Trainer's Role",
    "module_order": null,
    "description": "This module introduces facilitators to the Leyu Workforce Program...",
    "key_concepts": "Leyu mission, values, and program structure | Roles and responsibilities of facilitators | Code of conduct and professionalism | Safeguarding and gender inclusion principles",
    "duration": 45,
    "duration_type": "MINUTES",
    "teaching_strategy": null,
    "differentiation_strategies": null,
    "inclusion_strategy": null,
    "training_tag_name": null,
    "technology_integration_name": null,
    "digital_tools": "",
    "primary_materials": "",
    "secondary_materials": "",
    "instructional_methods": [
      { "name": "Lecture", "description": "..." },
      { "name": "Discussion-Based", "description": "..." }
    ],
    "assessment_types": ["Polling", "Portfolio"],
    "references": [],
    "lessons": [
      {
        "id": "56d4c1df-a709-44bc-b02c-e628ad6d4e9c",
        "name": "Lesson 1.1 Leyu Program Overview",
        "objective": "Explain the purpose, mission, and goals of Leyu Workforce Training.",
        "duration": 15,
        "duration_type": "HOURS",
        "description": null,
        "instructional_methods": [],
        "technology_integrations": []
      },
      {
        "id": "cb9a2310-2f5c-45bf-87f5-a01f609b3353",
        "name": "Lesson 1.2 Trainer Roles & Standards",
        "objective": "Identify key trainer responsibilities and ethical expectations.",
        "duration": 15,
        "duration_type": "HOURS",
        "description": null,
        "instructional_methods": [],
        "technology_integrations": []
      },
      {
        "id": "7db39109-38a9-432d-bf3a-25aca716e606",
        "name": "Lesson 1.3 Safeguarding & Inclusion",
        "objective": "Apply safeguarding and gender inclusion principles in training.",
        "duration": 15,
        "duration_type": "HOURS",
        "description": null,
        "instructional_methods": [],
        "technology_integrations": []
      }
    ],
    "accepted_contents": [
      {
        "id": "9237bc62-63ed-4553-80ec-970ade5b2118",
        "name": "Facilitators Orientation",
        "file_type": "PDF",
        "level": "MODULE",
        "link": "https://drive.google.com/...",
        "description": "Facilitators Orientation",
        "time_to_read_minutes": null
      }
    ]
  },
  {
    "id": "03cc820d-9eaa-4083-8d5b-0c542e5e0c66",
    "name": "Module 2: Training of Trainers (ToT)",
    "module_order": null,
    "duration": 105,
    "duration_type": "MINUTES",
    "key_concepts": "Adult learning and 4Es Framework (Engage, Explain, Elaborate, Evaluate) | Effective presentation and facilitation | Interactive and inclusive training methods | Session planning, time management, and feedback",
    "lessons": [
      { "id": "51d7ac81-...", "name": "Lesson 2.1 Adult Learning Principles", "objective": "Apply adult learning theories in facilitation.", "duration": 25, "duration_type": "HOURS" },
      { "id": "8fc35289-...", "name": "Lesson 2.2 The 4Es Framework", "objective": "Use the Engage–Explain–Elaborate–Evaluate approach in training.", "duration": 20, "duration_type": "HOURS" },
      { "id": "704f1a8f-...", "name": "Lesson 2.3 Facilitation & Presentation Skills", "objective": "Deliver content confidently using effective techniques.", "duration": 25, "duration_type": "HOURS" },
      { "id": "a8783d4f-...", "name": "Lesson 2.4 Managing Classrooms & Diversity", "objective": "Handle group dynamics and ensure inclusivity.", "duration": 20, "duration_type": "HOURS" }
    ],
    "accepted_contents": [
      { "id": "9dac9de7-...", "name": "TOT", "file_type": "PDF", "level": "MODULE", "description": "TOT" }
    ]
  },
  {
    "id": "663e1583-...",
    "name": "Module 3: Photography & Videography",
    "duration": 30,
    "duration_type": "MINUTES",
    "lessons": [
      { "id": "91a302a0-...", "name": "Lesson 3.1 Photography & Videography Basics", "objective": "Capture quality visuals using smartphones or cameras." },
      { "id": "5e8a452c-...", "name": "Lesson 3.2 Ethical Media & Consent", "objective": "Apply safeguarding and consent in all documentation." }
    ],
    "accepted_contents": [
      { "id": "4f6c901c-...", "name": "Photography and Videography", "file_type": "PDF", "level": "MODULE" }
    ]
  },
  {
    "id": "356c2af4-...",
    "name": "Module 4: Soft Skill",
    "duration": null,
    "duration_type": null,
    "key_concepts": null,
    "lessons": [],
    "accepted_contents": []
  }
]
```

---

### `get_audience_profile(training_id: str) -> dict`

Returns the audience profile with all base_data references resolved, plus specific courses and prerequisites.

**Returns empty dict `{}` if no audience profile exists.**

```json
{
  "id": "51d97248-ef66-4846-8845-be0cdc44cbaf",
  "training_id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc",
  "education_level_id": "uuid-...",
  "language_id": "uuid-...",
  "learner_level_id": "uuid-...",
  "work_experience_id": "uuid-...",
  "certifications": null,
  "licenses": null,
  "education_level": "Professional Certification",
  "education_level_desc": "...",
  "language_name": "English",
  "language_code": "en",
  "language_alternates": null,
  "learner_level": "Intermediate",
  "learner_level_desc": "...",
  "work_experience": "Professional Development",
  "work_experience_desc": "...",
  "specific_courses": [],
  "specific_prerequisites": []
}
```

---

### `get_learner_profile(learner_id: str) -> dict`

Returns a learner (trainee) profile. Accepts either `trainee.id` or `user.id` — tries both automatically.

**Returns empty dict `{}` if not found.**

```json
{
  "id": "trainee-uuid-...",
  "user_id": "user-uuid-...",
  "training_id": "45d3c920-...",
  "cohort_id": "cohort-uuid-...",
  "first_name": "Abebe",
  "last_name": "Kebede",
  "email": "abebe.kebede@example.com",
  "date_of_birth": "1990-05-15",
  "gender": "MALE",
  "field_of_study": "Education",
  "academic_level": "Bachelor's Degree",
  "language_name": "English",
  "language_code": "en",
  "city_name": "Addis Ababa",
  "zone_name": "Bole",
  "employment_status": "EMPLOYED",
  "marital_status": "MARRIED",
  "has_smart_phone": true,
  "has_training_experience": true,
  "training_experience_description": "5 years as a community trainer",
  "number_of_children": 2,
  "user_email": "abebe.kebede@example.com",
  "username": "abebe.kebede",
  "user_first_name": "Abebe",
  "user_last_name": "Kebede",
  "role_name": "ROLE_TRAINEE"
}
```

---

### `get_accepted_content(training_id: str) -> list[dict]`

Returns all `status = 'ACCEPTED'` content items for a training (across all modules).
**This is the primary data source for RAG indexing (Teammate 3).**

```json
[
  {
    "id": "9237bc62-63ed-4553-80ec-970ade5b2118",
    "module_id": "6cd77630-7421-4c7d-9a89-f5812086d7b7",
    "lesson_id": null,
    "assessment_id": null,
    "user_id": "content-developer-uuid",
    "name": "Facilitators Orientation",
    "description": "Facilitators Orientation",
    "file_type": "PDF",
    "level": "MODULE",
    "status": "ACCEPTED",
    "link": "https://drive.google.com/file/d/...",
    "reference_link": null,
    "rejection_reason": null,
    "time_to_read_minutes": null,
    "module_name": "Module 1: Orientation and Trainer's Role",
    "module_order": null,
    "lesson_name": null
  },
  {
    "id": "9dac9de7-619a-4243-9033-9503033cc6e3",
    "module_id": "03cc820d-9eaa-4083-8d5b-0c542e5e0c66",
    "lesson_id": null,
    "name": "TOT",
    "description": "TOT",
    "file_type": "PDF",
    "level": "MODULE",
    "status": "ACCEPTED",
    "link": "https://drive.google.com/file/d/...",
    "module_name": "Module 2: Training of Trainers (ToT)",
    "lesson_name": null
  }
]
```

> **Note for Teammate 3 (RAG)**: Content items have a `link` (Google Drive URL) but no inline text body. The `description` field is usually just the content title repeated. PDF text extraction from the Drive link is the next step to improve RAG quality. See `docs/limitations.md` §5.

---

### `save_generated_curriculum(training_id: str, curriculum: dict) -> str`

Saves the generated curriculum JSON to `ai_generated_curricula` table.
Returns the new row's UUID as a string.

**Note for Teammate 2 (Curriculum Builder)**: Call this after Pydantic validation passes. If save fails, the curriculum is still returned to the caller — not rolled back.

---

## Important: What Is NOT in TSPClient

These things do **not** exist in the current TSP database for the demo training:

| Missing | Impact |
|---|---|
| `assessments` rows | Demo training has 0 assessments — AI generates them from scratch |
| `surveys` rows | Same — 0 surveys |
| Trainee progress / attendance | Cannot personalize based on completion |
| Inline PDF text | Content is links only; RAG uses metadata |

---

## Demo Training IDs (use these for testing)

| Entity | ID |
|---|---|
| Training | `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc` |
| Audience Profile | `51d97248-ef66-4846-8845-be0cdc44cbaf` |
| Module 1 | `6cd77630-7421-4c7d-9a89-f5812086d7b7` |
| Module 2 | `03cc820d-9eaa-4083-8d5b-0c542e5e0c66` |
| Module 3 | `663e1583-6ea9-4b0c-b706-14cdf8194b3a` |
