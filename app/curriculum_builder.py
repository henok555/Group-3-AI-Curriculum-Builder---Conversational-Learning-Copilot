"""
Curriculum Builder — Core Logic Module

Responsible for:
  1. Building rich, pedagogically-informed prompts from TSP training data
  2. Calling the LLM and parsing the structured curriculum response
  3. Post-generation validation and auto-correction
  4. Rubric construction and weight normalization

This module is intentionally isolated from FastAPI so it can be tested,
used in CLI scripts, and attributed clearly to the Curriculum Builder role.

Author: Teammate 2 — Curriculum Builder
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from app.llm import call_gemma_json, LLMError
from app.schemas import (
    GeneratedCurriculum,
    CurriculumValidationReport,
    RubricCriterion,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bloom's Taxonomy — cognitive level mapping
# ---------------------------------------------------------------------------

# Ordered from lowest to highest cognitive demand
BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

BLOOM_VERBS: dict[str, str] = {
    "Remember":   "list, recall, name, identify, define, match, recognise",
    "Understand": "summarize, explain, interpret, classify, describe, paraphrase, compare",
    "Apply":      "use, execute, implement, demonstrate, solve, carry out, compute",
    "Analyze":    "differentiate, organise, distinguish, attribute, examine, deconstruct",
    "Evaluate":   "judge, justify, critique, assess, defend, recommend, prioritise",
    "Create":     "design, construct, produce, plan, assemble, develop, formulate",
}

# Map TSP learner_level name → Bloom's target level
LEARNER_LEVEL_TO_BLOOM: dict[str, str] = {
    "Beginner":     "Understand",
    "Basic":        "Remember",
    "Elementary":   "Understand",
    "Intermediate": "Apply",
    "Advanced":     "Analyze",
    "Expert":       "Evaluate",
    "Master":       "Create",
}

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

CURRICULUM_SYSTEM_PROMPT = """\
You are an expert curriculum designer applying Bloom's Taxonomy and constructive alignment.
Generate a pedagogically sound, structured curriculum for the TSP (Training Solution Platform).

## Pedagogical Principles
- Constructive alignment: objectives → teaching activities → assessments must all align
- Write lesson objectives using action verbs from the target Bloom's cognitive level
- Scaffold learning: each module builds on knowledge from the previous one
- Vary instructional methods across modules (lecture, discussion, practical, case study)

## Structural Requirements
- Minimum 3 modules, each with 2–4 lessons
- Each module MUST have: at least 1 assignment, 1 assessment, and 1 rubric
- Each rubric MUST have EXACTLY 3 criteria; weights must sum to 1.0 (use 0.33, 0.33, 0.34)
- Each rubric criterion MUST include 4 performance levels keyed "4", "3", "2", "1"
- All IDs must be unique strings (format: "mod-1", "les-1-1", "asgn-1", "asmt-1", "rub-1", "crit-1-1")
- Use ONLY information from the provided training profile — do not invent facts

## Required JSON Fields
The top-level object must include:
  - training_id (string UUID)
  - training_title (string)
  - modules (array, min 3)
  - audience_profile_summary (object)
  - objectives_mapping (object: objective_id → [module_id, ...])

## Few-Shot Rubric Example
```json
{
  "id": "rub-1",
  "title": "Module 1 Assignment Rubric",
  "description": "Evaluates quality of practical demonstration",
  "criteria": [
    {
      "criterion": "Content Accuracy",
      "description": "Correctness of information presented",
      "weight": 0.33,
      "levels": {
        "4": "All content is accurate, fully supported by training materials",
        "3": "Most content is accurate with minor errors",
        "2": "Some inaccuracies that affect understanding",
        "1": "Significant inaccuracies throughout"
      }
    },
    {
      "criterion": "Practical Application",
      "description": "Ability to apply concepts to real-world scenarios",
      "weight": 0.33,
      "levels": {
        "4": "Demonstrates clear, creative real-world application",
        "3": "Applies concepts correctly in most cases",
        "2": "Limited application with prompting needed",
        "1": "Unable to apply concepts without significant support"
      }
    },
    {
      "criterion": "Communication",
      "description": "Clarity and professionalism of presentation",
      "weight": 0.34,
      "levels": {
        "4": "Exceptionally clear, professional, and well-structured",
        "3": "Clear and organised with minor issues",
        "2": "Somewhat unclear or disorganised",
        "1": "Difficult to understand; lacks structure"
      }
    }
  ],
  "total_weight": 1.0
}
```

OUTPUT: Respond ONLY with valid JSON. No markdown fences, no explanation, no extra text.
Start with { and end with }.
"""


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

def _flatten_objectives(objectives: list) -> list[dict]:
    """
    Recursively flatten the objectives tree returned by TSPClient
    into a flat list of {id, definition} dicts.
    """
    flat: list[dict] = []
    for obj in objectives:
        flat.append({"id": str(obj["id"]), "definition": obj.get("definition", "")})
        for child in obj.get("children", []):
            flat.append({"id": str(child["id"]), "definition": child.get("definition", "")})
            for outcome in child.get("outcomes", []):
                flat.append({
                    "id": str(outcome["id"]),
                    "definition": f"Outcome: {outcome.get('definition', '')}",
                })
    return flat


def _format_module_block(module: dict, fallback_order: int = 0) -> str:
    """Format one TSP module + its lessons and content into a prompt block."""
    # module_order is NULL for some records — fallback to row position
    order = module.get("module_order") or fallback_order

    lines = [
        f"MODULE {order}: {module.get('name', 'Unnamed')}",
        f"  Description: {module.get('description', 'N/A')}",
        f"  Key concepts: {module.get('key_concepts', 'N/A')}",
        f"  Duration: {module.get('duration', '?')} {module.get('duration_type', 'HOURS')}",
        f"  Teaching strategy: {module.get('teaching_strategy', 'N/A')}",
        f"  Instructional methods: {', '.join(im['name'] for im in module.get('instructional_methods', [])) or 'N/A'}",
        f"  Assessment types: {', '.join(module.get('assessment_types', [])) or 'N/A'}",
        f"  Primary materials: {module.get('primary_materials', 'N/A')}",
        f"  Secondary materials: {module.get('secondary_materials', 'N/A')}",
        f"  Digital tools: {module.get('digital_tools', 'N/A')}",
        f"  Differentiation strategies: {module.get('differentiation_strategies', 'N/A')}",
        f"  Inclusion strategy: {module.get('inclusion_strategy', 'N/A')}",
        f"  Technology integration: {module.get('technology_integration_description', 'N/A')}",
    ]

    for lesson in module.get("lessons", []):
        methods = [im["name"] for im in lesson.get("instructional_methods", [])]
        lines += [
            f"  LESSON: {lesson.get('name', 'Unnamed')}",
            f"    Duration: {lesson.get('duration', '?')} {lesson.get('duration_type', 'HOURS')}",
            f"    Objective: {lesson.get('objective', 'N/A')}",
            f"    Methods: {', '.join(methods) or 'N/A'}",
        ]

    for content in module.get("accepted_contents", []):
        desc = content.get("description", "")
        lines.append(
            f"  CONTENT [{content['id']}]: {content.get('name', 'Unnamed')} "
            f"({content.get('file_type', '?')}, level={content.get('level', '?')}, "
            f"{content.get('time_to_read_minutes', '?')} min read)"
        )
        if desc:
            lines.append(f"    → {desc[:180]}")

    for ref in module.get("references", []):
        lines.append(f"  REFERENCE: {ref}")

    return "\n".join(lines)


def build_curriculum_prompt(
    training_profile: dict,
    modules: list[dict],
    audience: dict,
    training_id: str,
) -> str:
    """
    Build a rich, pedagogically-informed curriculum generation prompt.

    Args:
        training_profile: Result of TSPClient.get_training_profile()
        modules: Result of TSPClient.get_modules_with_lessons()
        audience: Result of TSPClient.get_audience_profile()
        training_id: UUID string — injected into the prompt so the LLM
                     includes it in training_id field of the response

    Returns:
        Full prompt string ready to send to call_gemma_json().
    """
    training = training_profile.get("training", {})
    all_objectives = _flatten_objectives(training_profile.get("objectives", []))

    # Resolve Bloom's target from learner level
    learner_level = audience.get("learner_level", "Intermediate") or "Intermediate"
    bloom_target = LEARNER_LEVEL_TO_BLOOM.get(learner_level, "Apply")
    bloom_verbs = BLOOM_VERBS[bloom_target]

    # Objectives block
    if all_objectives:
        obj_lines = [f"  [{o['id']}] {o['definition']}" for o in all_objectives]
        objectives_block = "\n".join(obj_lines)
    else:
        objectives_block = "  (none defined — infer from training scope)"

    # Module blocks — pass row index as fallback for NULL module_order values
    module_blocks = [_format_module_block(m, i + 1) for i, m in enumerate(modules)]
    modules_block = "\n\n".join(module_blocks) if module_blocks else "No modules defined yet."

    # Audience block
    audience_lines = [
        f"  Education level: {audience.get('education_level', 'N/A')} — {audience.get('education_level_desc', '')}",
        f"  Language: {audience.get('language_name', 'N/A')} ({audience.get('language_code', '')})",
        f"  Learner level: {learner_level} — {audience.get('learner_level_desc', '')}",
        f"  Work experience: {audience.get('work_experience', 'N/A')} — {audience.get('work_experience_desc', '')}",
        f"  Prior courses: {', '.join(audience.get('specific_courses', [])) or 'None'}",
        f"  Prerequisites: {', '.join(audience.get('specific_prerequisites', [])) or 'None'}",
    ]
    audience_block = "\n".join(audience_lines)

    # Objective IDs for mapping instructions
    obj_ids_sample = ", ".join(f'"{o["id"]}"' for o in all_objectives[:8])

    return f"""\
Generate a complete, pedagogically sound curriculum for the following TSP training.

═══════════════════════════════════════════════
TRAINING OVERVIEW
═══════════════════════════════════════════════
training_id:  {training_id}
Title:        {training.get('title', 'Unknown')}
Rationale:    {training.get('rationale', 'N/A')}
Scope:        {training.get('scope', 'N/A')}
Delivery:     {training.get('delivery_method', 'N/A')}
Duration:     {training.get('duration', '?')} {training.get('duration_type', 'HOURS')}
Keywords:     {', '.join(training_profile.get('keywords', [])) or 'N/A'}
Purposes:     {', '.join(training_profile.get('purposes', [])) or 'N/A'}

═══════════════════════════════════════════════
AUDIENCE PROFILE
═══════════════════════════════════════════════
{audience_block}

Bloom's guidance: ALL lesson objectives must use action verbs from the "{bloom_target}" level.
Example verbs: {bloom_verbs}

═══════════════════════════════════════════════
TRAINING OBJECTIVES  (use these IDs in objectives_mapping and module.objective_ids)
═══════════════════════════════════════════════
{objectives_block}

═══════════════════════════════════════════════
TSP MODULES AND ACCEPTED CONTENT
(Use each module's actual description, key concepts, teaching strategy, differentiation
strategies, inclusion strategy, materials, and lesson objectives as the foundation.
Do NOT replace or ignore any field that already has content — enrich, don't invent.)
═══════════════════════════════════════════════
{modules_block}

═══════════════════════════════════════════════
GENERATION INSTRUCTIONS
═══════════════════════════════════════════════
1.  Create 3–5 modules — use the existing TSP module structure as the foundation
2.  Each module: 2–4 lessons, each with a Bloom's-aligned objective and bloom_level field
3.  Each module: exactly 1 assignment (type: individual | group | practical | written | presentation)
4.  Each module: exactly 1 assessment (type: quiz | exam | project | portfolio | presentation | practical)
5.  Each module: exactly 1 rubric with EXACTLY 3 criteria, weights [0.33, 0.33, 0.34]
6.  Fill module.objective_ids with the relevant objective IDs from the list above
7.  Fill top-level objectives_mapping: {{ "objective_id": ["mod-id", ...] }}
8.  Reference accepted content IDs in lesson.content_references where relevant
9.  Set duration_type to "HOURS" throughout (matches TSP DB convention)
10. Adapt language and depth to {learner_level} learners
11. Do NOT invent facts — only use information from the training data above
12. Set training_id to: "{training_id}"

Available objective IDs for mapping: [{obj_ids_sample}]

Output the complete JSON curriculum now.\
"""


# ---------------------------------------------------------------------------
# Validation and Auto-Fix
# ---------------------------------------------------------------------------

# Default rubric criterion weights that sum exactly to 1.0
_DEFAULT_WEIGHTS = [0.33, 0.33, 0.34]

_DEFAULT_CRITERION_NAMES = ["Content Accuracy", "Practical Application", "Communication"]


def _make_default_criterion(index: int, module_name: str) -> dict:
    """Synthesize a rubric criterion with 4 performance levels."""
    name = _DEFAULT_CRITERION_NAMES[index % len(_DEFAULT_CRITERION_NAMES)]
    return {
        "criterion": name,
        "description": f"{name} as demonstrated in {module_name}",
        "weight": _DEFAULT_WEIGHTS[index % len(_DEFAULT_WEIGHTS)],
        "levels": {
            "4": "Excellent — exceeds expectations in all aspects",
            "3": "Proficient — meets expectations consistently",
            "2": "Developing — partially meets expectations",
            "1": "Beginning — does not yet meet expectations",
        },
    }


def _normalize_weights(criteria: list[dict]) -> tuple[list[dict], bool]:
    """
    Proportionally scale criteria weights so they sum to 1.0.

    Returns:
        (criteria, was_changed) — was_changed is True if any weight was adjusted.
    """
    if not criteria:
        return criteria, False

    total = sum(c.get("weight", 0.0) for c in criteria)
    if abs(total - 1.0) <= 0.01:
        return criteria, False  # already fine

    if total == 0.0:
        # All weights zero — distribute equally
        equal = round(1.0 / len(criteria), 4)
        for c in criteria:
            c["weight"] = equal
    else:
        # Proportional rescale
        for c in criteria:
            c["weight"] = round(c.get("weight", 0.0) / total, 4)

    # Absorb floating-point remainder into last criterion
    remainder = round(1.0 - sum(c["weight"] for c in criteria), 4)
    if remainder != 0.0:
        criteria[-1]["weight"] = round(criteria[-1]["weight"] + remainder, 4)

    return criteria, True


def _make_default_assignment(module_id: str, module_name: str) -> dict:
    return {
        "id": f"asgn-auto-{module_id}",
        "title": f"{module_name} — Practical Assignment",
        "description": (
            f"Demonstrate your understanding of {module_name} concepts "
            "through a structured practical exercise."
        ),
        "type": "practical",
        "estimated_hours": 2.0,
        "rubric_id": f"rub-auto-{module_id}",
    }


def _make_default_assessment(module_id: str, module_name: str) -> dict:
    return {
        "id": f"asmt-auto-{module_id}",
        "title": f"{module_name} — Knowledge Check",
        "description": f"Assess comprehension of key concepts from {module_name}.",
        "type": "quiz",
        "questions": [
            {
                "id": f"q-auto-{module_id}-1",
                "question": f"What are the most important concepts covered in {module_name}?",
                "type": "short_answer",
                "points": 10,
            }
        ],
        "duration_minutes": 30,
        "max_attempts": 2,
        "passing_score": 70.0,
    }


def _make_default_rubric(module_id: str, module_name: str) -> dict:
    criteria = [_make_default_criterion(i, module_name) for i in range(3)]
    return {
        "id": f"rub-auto-{module_id}",
        "title": f"{module_name} — Assessment Rubric",
        "description": f"Evaluation rubric for {module_name} assignments and assessments",
        "criteria": criteria,
        "total_weight": 1.0,
    }


def _normalize_llm_output(data: dict) -> dict:
    """
    Remap common LLM field-name variations to match our Pydantic schema.

    LLMs frequently use 'title' instead of 'name', omit 'module_order',
    use 'order' instead, etc. This function normalises these before
    Pydantic validation so generation never fails on trivial naming issues.
    """
    for i, mod in enumerate(data.get("modules", [])):
        # title → name
        if "name" not in mod and "title" in mod:
            mod["name"] = mod.pop("title")
        # order / module_order
        if "module_order" not in mod:
            mod["module_order"] = mod.pop("order", i + 1)
        # key_concepts fallback
        if "key_concepts" not in mod:
            mod["key_concepts"] = mod.get("description", mod.get("name", ""))
        # description fallback
        if "description" not in mod:
            mod["description"] = mod.get("key_concepts", mod.get("name", ""))
        # duration fallback
        if "duration" not in mod:
            mod["duration"] = mod.pop("duration_hours", 2.0)
        if "duration_type" not in mod:
            mod["duration_type"] = "HOURS"

        # Lessons
        for lesson in mod.get("lessons", []):
            if "name" not in lesson and "title" in lesson:
                lesson["name"] = lesson.pop("title")
            if "description" not in lesson:
                lesson["description"] = lesson.get("objective", lesson.get("name", ""))
            if "duration" not in lesson:
                lesson["duration"] = lesson.pop("duration_hours", 1.0)
            if "duration_type" not in lesson:
                lesson["duration_type"] = "HOURS"
            if "objective" not in lesson:
                lesson["objective"] = lesson.get("description", "")

        # Assignments
        for asgn in mod.get("assignments", []):
            if "description" not in asgn:
                asgn["description"] = asgn.get("title", "Assignment")
            if "estimated_hours" not in asgn:
                asgn["estimated_hours"] = 2.0

        # Assessments
        for asmt in mod.get("assessments", []):
            if "description" not in asmt:
                asmt["description"] = asmt.get("title", "Assessment")
            if "questions" not in asmt:
                asmt["questions"] = []
            if "duration_minutes" not in asmt:
                asmt["duration_minutes"] = 30

    return data


def validate_and_fix_curriculum(
    curriculum_data: dict,
) -> tuple[dict, CurriculumValidationReport]:
    """
    Post-generation validation and auto-correction pass.

    Problems fixed automatically (never raises — always returns corrected data):
      0. LLM field-name normalization (title→name, order→module_order, etc.)
      1. Rubric weight normalization  (weights must sum ≈ 1.0)
      2. Rubric criteria padding      (rubrics must have ≥ 3 criteria)
      3. Module completeness          (every module needs assignment + assessment + rubric)
      4. Lesson objective backfill    (empty objectives get a fallback string)
      5. objectives_mapping inference (built from module.objective_ids when map is empty)

    Returns:
        (fixed_curriculum_data, CurriculumValidationReport) — report documents all changes.
    """
    report = CurriculumValidationReport()

    # ── 0. Normalize LLM field names ────────────────────────────────────
    curriculum_data = _normalize_llm_output(curriculum_data)

    for mod in curriculum_data.get("modules", []):
        mod_id  = str(mod.get("id", "unknown"))
        mod_name = mod.get("name", "Module")

        # ── 1 + 2. Fix rubrics ──────────────────────────────────────────────
        for rubric in mod.get("rubrics", []):
            criteria = rubric.get("criteria", [])

            # Pad to minimum 3 criteria
            while len(criteria) < 3:
                criteria.append(_make_default_criterion(len(criteria), mod_name))
                report.rubrics_criteria_padded += 1
            rubric["criteria"] = criteria

            # Normalize weights
            rubric["criteria"], changed = _normalize_weights(rubric["criteria"])
            if changed:
                report.rubrics_weight_normalized += 1

            rubric["total_weight"] = 1.0

        # ── 3. Ensure every module has all required components ───────────────
        if not mod.get("assignments"):
            mod["assignments"] = [_make_default_assignment(mod_id, mod_name)]
            report.modules_assignment_added += 1

        if not mod.get("assessments"):
            mod["assessments"] = [_make_default_assessment(mod_id, mod_name)]
            report.modules_assessment_added += 1

        if not mod.get("rubrics"):
            mod["rubrics"] = [_make_default_rubric(mod_id, mod_name)]
            report.modules_rubric_added += 1

        # ── 4. Fill empty lesson objectives ─────────────────────────────────
        for lesson in mod.get("lessons", []):
            if not lesson.get("objective", "").strip():
                lesson["objective"] = (
                    f"Demonstrate understanding of {lesson.get('name', 'lesson content')} "
                    "as covered in the training materials."
                )
                report.lessons_objective_filled += 1

    # ── 5. Infer objectives_mapping from module.objective_ids ───────────────
    if not curriculum_data.get("objectives_mapping"):
        mapping: dict[str, list[str]] = {}
        for mod in curriculum_data.get("modules", []):
            for obj_id in mod.get("objective_ids", []):
                mapping.setdefault(str(obj_id), []).append(str(mod["id"]))
        if mapping:
            curriculum_data["objectives_mapping"] = mapping
            report.objectives_mapping_inferred = True

    return curriculum_data, report


# ---------------------------------------------------------------------------
# Main generation entrypoint
# ---------------------------------------------------------------------------

async def generate_curriculum(
    training_id: str,
    training_profile: dict,
    modules: list[dict],
    audience: dict,
    max_retries: int = 3,
) -> tuple[GeneratedCurriculum, CurriculumValidationReport]:
    """
    Full curriculum generation pipeline:
      1. Build prompt from TSP data
      2. Call Gemma E4B via OpenRouter
      3. Validate and auto-fix the response
      4. Parse into GeneratedCurriculum model

    Args:
        training_id: UUID string of the training.
        training_profile: From TSPClient.get_training_profile().
        modules: From TSPClient.get_modules_with_lessons().
        audience: From TSPClient.get_audience_profile().
        max_retries: LLM retry budget for JSON parse failures.

    Returns:
        (GeneratedCurriculum, CurriculumValidationReport)

    Raises:
        LLMError: If LLM call fails after all retries.
        ValidationError: If the response cannot be parsed into GeneratedCurriculum
                         even after auto-correction.
    """
    prompt = build_curriculum_prompt(training_profile, modules, audience, training_id)

    logger.info("[CurriculumBuilder] Calling LLM for training_id=%s", training_id)
    raw: dict = await call_gemma_json(
        prompt=prompt,
        system_prompt=CURRICULUM_SYSTEM_PROMPT,
        schema=GeneratedCurriculum.model_json_schema(),
        max_retries=max_retries,
    )

    # Inject required top-level fields the LLM may have omitted
    raw.setdefault("training_id", training_id)
    raw.setdefault(
        "training_title",
        training_profile.get("training", {}).get("title", "Generated Curriculum"),
    )
    raw.setdefault("generated_at", datetime.utcnow().isoformat())
    raw.setdefault("audience_profile_summary", {
        "learner_level": audience.get("learner_level"),
        "language": audience.get("language_name"),
        "education_level": audience.get("education_level"),
    })

    logger.info(
        "[CurriculumBuilder] LLM returned %d modules — running validation pass",
        len(raw.get("modules", [])),
    )

    fixed, report = validate_and_fix_curriculum(raw)

    if report.rubrics_weight_normalized or report.rubrics_criteria_padded:
        logger.warning(
            "[CurriculumBuilder] Auto-corrections: %d rubrics renormalised, %d criteria padded",
            report.rubrics_weight_normalized,
            report.rubrics_criteria_padded,
        )

    curriculum = GeneratedCurriculum(**fixed)

    logger.info(
        "[CurriculumBuilder] Done — %d modules, %d total lessons",
        len(curriculum.modules),
        sum(len(m.lessons) for m in curriculum.modules),
    )

    return curriculum, report
