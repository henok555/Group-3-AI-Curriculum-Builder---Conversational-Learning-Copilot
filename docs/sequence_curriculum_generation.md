# Sequence Diagram — Curriculum Generation

```mermaid
sequenceDiagram
    actor Client as Client / Demo UI
    participant API as FastAPI<br/>(app/main.py)
    participant TSP as TSPClient<br/>(app/tsp_client.py)
    participant DB as PostgreSQL<br/>(training_solutions)
    participant LLM as LLM Client<br/>(app/llm.py)
    participant OR as OpenRouter<br/>API
    participant Gemma as Gemma 2<br/>(google/gemma-2-9b-it)

    Client->>API: POST /curriculum/generate<br/>{ training_id }

    API->>TSP: get_training_profile(training_id)
    TSP->>DB: SELECT trainings, company_profiles, objectives, outcomes, keywords, purposes
    DB-->>TSP: rows
    TSP-->>API: training_profile dict

    alt Training not found
        API-->>Client: 404 Not Found
    end

    API->>TSP: get_modules_with_lessons(training_id)
    TSP->>DB: SELECT modules, lessons, instructional_methods,<br/>materials, assessment_types, contents (ACCEPTED)
    DB-->>TSP: rows (N+1 per module, resolved in loop)
    TSP-->>API: list[module dict]

    API->>TSP: get_audience_profile(training_id)
    TSP->>DB: SELECT audience_profiles + base_data lookups<br/>+ specific_courses + specific_prerequisites
    DB-->>TSP: rows
    TSP-->>API: audience dict

    API->>API: build_curriculum_prompt()<br/>(assemble objectives, modules, audience into text)

    loop Max 3 attempts
        API->>LLM: call_gemma_json(prompt, schema)
        LLM->>OR: POST /chat/completions<br/>model=google/gemma-2-9b-it<br/>temperature=0.1
        OR->>Gemma: Forward request
        Gemma-->>OR: Generated text (JSON)
        OR-->>LLM: Response
        LLM->>LLM: json.loads(response)

        alt JSON valid
            LLM-->>API: dict
        else JSON parse error
            LLM->>LLM: Append error to prompt, retry
        end
    end

    alt All retries failed
        API-->>Client: 500 LLM generation failed
    end

    API->>API: Curriculum.model_validate(dict)<br/>(Pydantic validation)

    API->>TSP: save_generated_curriculum(training_id, curriculum)
    TSP->>DB: INSERT INTO ai_responses (training_id, output, request_type)
    DB-->>TSP: ai_response.id
    TSP-->>API: response_id

    API-->>Client: 200 Curriculum JSON<br/>(modules, lessons, assessments, rubrics, sources)
```

## Notes

- The prompt includes real TSP data: training title, rationale, scope, objectives hierarchy, module/lesson structure, audience profile, and accepted content metadata.
- Validation failure triggers a retry with the specific Pydantic error appended to the prompt (max 3 attempts).
- The generated curriculum is saved to `ai_responses` (existing TSP table) rather than a new table, preserving write access simplicity.
- If save fails, the curriculum is still returned to the client — generation is not rolled back.
