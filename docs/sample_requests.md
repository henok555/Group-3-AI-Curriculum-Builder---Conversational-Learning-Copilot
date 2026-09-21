# Sample Requests & Responses

Real curl examples against the running API (`uvicorn app.main:app --port 8000`).

---

## GET /health

```bash
curl http://localhost:8000/health
```

**Response 200:**
```json
{
  "status": "healthy",
  "database_connected": true,
  "llm_connected": true,
  "timestamp": "2026-09-18T16:00:00.000000"
}
```

**Degraded (LLM key missing):**
```json
{
  "status": "degraded",
  "database_connected": true,
  "llm_connected": false,
  "timestamp": "2026-09-18T16:00:00.000000"
}
```

---

## POST /curriculum/generate

```bash
curl -X POST http://localhost:8000/curriculum/generate \
  -H "Content-Type: application/json" \
  -d '{
    "training_id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc"
  }'
```

**Request body schema:**
```json
{
  "training_id": "string (UUID, required)",
  "learner_id": "string (UUID, optional)",
  "options": {}
}
```

**Response 200 — generated curriculum:**
```json
{
  "training_id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc",
  "training_title": "Leyu Facilitators and Trainers Training",
  "generated_at": "2026-09-18T16:00:00.000000",
  "audience_profile_summary": {
    "education_level": "Professional Certification",
    "language": "English",
    "learner_level": "Intermediate"
  },
  "objectives_mapping": {
    "obj-uuid-1": ["module-1", "module-2"]
  },
  "metadata": {
    "ai_response_id": "generated-curricula-uuid"
  },
  "modules": [
    {
      "id": "gen-module-1",
      "name": "Orientation and Trainer's Role",
      "description": "...",
      "key_concepts": "Leyu mission, values, safeguarding, code of conduct",
      "duration_hours": 1.5,
      "duration_type": "HOURS",
      "module_order": 1,
      "instructional_methods": ["Lecture", "Discussion-Based"],
      "assessment_types": ["Polling", "Portfolio"],
      "primary_materials": null,
      "secondary_materials": null,
      "digital_tools": null,
      "references": [],
      "lessons": [
        {
          "id": "gen-lesson-1-1",
          "name": "Leyu Program Overview",
          "description": "Introduction to the Leyu Workforce Program",
          "objective": "Explain the purpose, mission, and goals of Leyu Workforce Training.",
          "duration_hours": 0.5,
          "duration_type": "HOURS",
          "instructional_methods": ["Lecture"],
          "technology_integrations": [],
          "assignments": [],
          "content_references": ["9237bc62-63ed-4553-80ec-970ade5b2118"]
        }
      ],
      "assignments": [
        {
          "id": "gen-assign-1",
          "title": "Trainer Code of Conduct Reflection",
          "description": "Write a 1-page reflection on Leyu's code of conduct and how you will apply it.",
          "type": "written",
          "estimated_hours": 1.0,
          "rubric_id": "gen-rubric-1"
        }
      ],
      "assessments": [
        {
          "id": "gen-assess-1",
          "title": "Module 1 Quiz",
          "description": "Knowledge check on Leyu program structure and safeguarding",
          "type": "quiz",
          "questions": [
            {
              "question": "What is Leyu's primary mission?",
              "type": "RADIO",
              "choices": ["Workforce excellence", "Profit maximization", "Government compliance", "None"]
            }
          ],
          "duration_minutes": 20,
          "max_attempts": 2,
          "passing_score": 70.0
        }
      ],
      "rubrics": [
        {
          "id": "gen-rubric-1",
          "title": "Code of Conduct Reflection Rubric",
          "description": "Evaluates depth of understanding and personal application",
          "criteria": [
            {
              "criterion": "Understanding of Leyu Standards",
              "description": "Demonstrates clear grasp of Leyu's ethical expectations",
              "weight": 0.4,
              "levels": {
                "4": "Exceptional understanding with specific examples",
                "3": "Good understanding, mostly accurate",
                "2": "Partial understanding, some gaps",
                "1": "Little to no understanding shown"
              }
            },
            {
              "criterion": "Personal Application",
              "description": "Connects standards to own training practice",
              "weight": 0.6,
              "levels": {
                "4": "Concrete, specific personal commitments stated",
                "3": "General commitments, plausible",
                "2": "Vague or generic",
                "1": "No personal connection made"
              }
            }
          ],
          "total_weight": 1.0
        }
      ]
    }
  ]
}
```

**Response 404 — invalid training ID:**
```json
{
  "detail": "Training 00000000-0000-0000-0000-000000000000 not found"
}
```

**Response 500 — LLM failure:**
```json
{
  "detail": "LLM generation failed: Failed to get valid JSON after 3 attempts: JSON parse error: ..."
}
```

---

## POST /copilot/message

```bash
curl -X POST http://localhost:8000/copilot/message \
  -H "Content-Type: application/json" \
  -d '{
    "training_id": "45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc",
    "question": "What are the key responsibilities of a trainer in the Leyu program?",
    "max_sources": 5
  }'
```

**Request body schema:**
```json
{
  "training_id": "string (UUID, required)",
  "learner_id": "string (UUID, optional — enables personalization)",
  "question": "string (required)",
  "session_id": "string (optional — pass the session_id from a previous response to continue that conversation server-side; omit to start a new session)",
  "conversation_history": [
    {"role": "user", "content": "previous question"},
    {"role": "assistant", "content": "previous answer"}
  ],
  "max_sources": 5
}
```

**Multi-turn conversation (server-side session — no need to re-send history):**
```bash
# Turn 1 — response includes "session_id"
curl -X POST http://localhost:8000/copilot/message \
  -H "Content-Type: application/json" \
  -d '{
    "training_id": "ea7953f9-e773-4d2c-a895-b8ecf2e969ed",
    "learner_id": "855be580-6c2e-4626-a44c-df5995e7faaf",
    "question": "What do the financial literacy materials cover?"
  }'

# Turn 2 — same conversation, context restored from the server session
curl -X POST http://localhost:8000/copilot/message \
  -H "Content-Type: application/json" \
  -d '{
    "training_id": "ea7953f9-e773-4d2c-a895-b8ecf2e969ed",
    "learner_id": "855be580-6c2e-4626-a44c-df5995e7faaf",
    "question": "Can you explain that more simply?",
    "session_id": "<session_id from turn 1 response>"
  }'
```

**Personalized response additions** (present when `learner_id` is given):
```json
{
  "session_id": "992b541e-6396-446b-b07c-cd5e1a3d04cf",
  "personalization": {
    "tier": "Intermediate / Applied",
    "performance_level": "on_track",
    "evidence_summary": "Learner evidence from TSP: attended 4/4 recorded sessions (100%); overall assessment score 71.4%."
  },
  "recommended_next_activity": {
    "activity": "Attend \"Financial Literacy Training - Session 3\".",
    "reason": "TSP shows this is the next session in your cohort schedule (2025-05-24), following \"Digital Literacy Training - Session 2\" which you already attended."
  }
}
```

**Response 200 — answer with sources:**
```json
{
  "answer": "Trainers in the Leyu program are responsible for delivering training sessions in alignment with Leyu's mission and standards. Key responsibilities include: maintaining the code of conduct, applying safeguarding principles, facilitating inclusive sessions that respect gender equality, and reporting through established communication channels. [Module: Orientation and Trainer's Role]",
  "sources": [
    {
      "content_id": "9237bc62-63ed-4553-80ec-970ade5b2118",
      "module_id": "6cd77630-7421-4c7d-9a89-f5812086d7b7",
      "lesson_id": null,
      "module_name": "Module 1: Orientation and Trainer's Role",
      "lesson_name": null,
      "excerpt": "Facilitators Orientation Leyu mission, values, and program structure Roles and responsibilities of facilitators Code of conduct and professionalism...",
      "similarity_score": 0.742
    }
  ],
  "confidence": 0.742,
  "guardrail_triggered": false,
  "guardrail_reason": null
}
```

**Response 200 — no relevant content (fallback):**
```json
{
  "answer": "I don't have that information in the training materials.",
  "sources": [],
  "confidence": 0.0,
  "guardrail_triggered": false,
  "guardrail_reason": null
}
```

**Response 200 — guardrail triggered:**
```json
{
  "answer": "I can't process that request. It appears to contain instructions that override my guidelines.",
  "sources": [],
  "confidence": 0.0,
  "guardrail_triggered": true,
  "guardrail_reason": "Potential injection detected: ignore\\s+(?:previous|all|above)\\s+instructions?"
}
```

**Response 200 — unauthorized access attempt (cross-training):**
```json
{
  "answer": "I can only answer questions about the training you are enrolled in.",
  "sources": [],
  "confidence": 0.0,
  "guardrail_triggered": true,
  "guardrail_reason": "Cross-training access attempt: learner not enrolled in requested training"
}
```

---

## OpenAPI Interactive Docs

Once the server is running, visit:
```
http://localhost:8000/docs
```
This auto-generated Swagger UI lets you test all endpoints interactively with real request/response schemas.
