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
CRITICAL: You must output ONLY a valid JSON object.
DO NOT output any pre-amble, scratchpad, drafting, reasoning, or text explanations.
Your response MUST start immediately with the character '{' on line 1.

You are a senior curriculum architect with expertise in Bloom's Taxonomy, constructive alignment, and adult learning theory.
Your task is to produce a rich, deployment-ready curriculum for the TSP (Training Solution Platform).

## Pedagogical Principles
- Constructive alignment: lesson objectives → teaching activities → assignments → assessments must all align
- Every lesson objective MUST start with a precise Bloom's action verb from the instructed cognitive level
- LESSON OBJECTIVE vs DESCRIPTION RULE:
    * objective: a single sentence starting with a Bloom's action verb (e.g. "Differentiate X from Y")
    * description: 2–3 sentences giving learning context, scenario, and what participants will explore — NEVER copy the objective verbatim
- Scaffold learning: each module explicitly builds on knowledge from the previous module
- Vary instructional methods per lesson: choose from [Lecture, Demonstration, Discussion-Based, Case Study, Practical, Role Play, Simulation, Peer Review]
- Vary assignment types across modules: choose from [individual, group, practical, written, presentation, portfolio]

## Structural Requirements
- 3–5 modules, each with 2–4 lessons
- Each module MUST have: at least 1 assignment, 1 assessment, and 1 rubric
- Each rubric MUST have EXACTLY 3 criteria; weights [0.33, 0.33, 0.34]
- Each rubric criterion MUST include 4 performance levels keyed "4", "3", "2", "1" with specific descriptors
- RUBRIC SPECIFICITY RULE: All 3 criteria MUST be domain-specific to the module topic. NO generic criteria like "Clarity and Coherence" unless it is the 3rd criterion. Criteria 1 and 2 must evaluate technical/operational competencies directly related to the module.
- RUBRIC LINKING RULE: Each assignment's rubric_id MUST reference its module's rubric id (e.g. assignment rubric_id = "rub-1" when module rubric id is "rub-1")
- ASSESSMENT QUESTIONS RULE: Every assessment MUST include 3–5 questions. Each question must have: id, question (text), type ("multiple_choice" | "short_answer" | "scenario"), points (integer), and for multiple_choice: options (list of 4 strings) and correct_answer (string)
- DIFFERENTIATION RULE: Every module MUST populate differentiation_strategies (e.g. scaffolding for less experienced, extension tasks for advanced, visual aids for different learning styles)
- INSTRUCTIONAL METHODS RULE: Every lesson MUST list at least 1 instructional method
- All IDs must be unique strings (format: "mod-1", "les-1-1", "asgn-1", "asmt-1", "rub-1", "crit-1-1")
- Use ONLY information from the provided training profile — do not invent facts

## Duration Rules
- Lesson durations must be realistic: 0.5–2.0 HOURS each. Never output > 8 HOURS for a single lesson.
- Module duration = sum of its lesson durations. Never output module duration > 24 HOURS.

## Required JSON Fields
The top-level object must include:
  - training_id (string UUID)
  - training_title (string)
  - modules (array, min 3)
  - audience_profile_summary (object with keys: education_level, language, learner_level, work_experience, participants, delivery_mode)
  - objectives_mapping (object: objective_id → [module_id, ...])

## Few-Shot Example: Module with all required fields
```json
{
  "id": "mod-1",
  "name": "Example Module",
  "description": "Participants examine the operational structure of the platform and deconstruct how user roles interact with core system workflows.",
  "key_concepts": "Role-based access, workflow orchestration, audit trail, case escalation",
  "teaching_strategy": "Scenario-based learning with live system demonstration and guided Q&A",
  "differentiation_strategies": "Scaffolding: provide step-by-step role guides for less experienced learners. Extension: challenge advanced learners to map edge-case escalation paths.",
  "inclusion_strategy": "Use visual role-interaction diagrams and bilingual glossary cards for diverse literacy levels.",
  "duration": 3.0,
  "duration_type": "HOURS",
  "module_order": 1,
  "objective_ids": ["<uuid-from-objectives-list>"],
  "instructional_methods": ["Demonstration", "Discussion-Based"],
  "lessons": [
    {
      "id": "les-1-1",
      "name": "Platform Overview",
      "description": "Learners explore the platform dashboard, examining how the system is structured to support multiple user roles. They trace a sample customer case from submission to resolution.",
      "objective": "Deconstruct the platform's user-role structure and attribute each role's responsibilities within a standard case lifecycle.",
      "bloom_level": "Analyze",
      "duration": 1.5,
      "duration_type": "HOURS",
      "instructional_methods": ["Demonstration", "Discussion-Based"],
      "content_references": []
    }
  ],
  "assignments": [
    {
      "id": "asgn-1",
      "title": "Role-Workflow Mapping Exercise",
      "description": "Participants map all user roles to their corresponding system actions in a given scenario, highlighting decision points and escalation triggers.",
      "type": "written",
      "estimated_hours": 1.5,
      "rubric_id": "rub-1"
    }
  ],
  "assessments": [
    {
      "id": "asmt-1",
      "title": "Module 1 Knowledge Check",
      "description": "Tests comprehension of platform structure, user roles, and case workflows.",
      "type": "quiz",
      "duration_minutes": 20,
      "max_attempts": 2,
      "passing_score": 70.0,
      "rubric_id": "rub-1",
      "questions": [
        {
          "id": "q-1-1",
          "question": "Which user role is responsible for escalating unresolved cases?",
          "type": "multiple_choice",
          "points": 10,
          "options": ["Customer", "Agent", "Supervisor", "System"],
          "correct_answer": "Supervisor"
        },
        {
          "id": "q-1-2",
          "question": "Describe the steps the system follows when a dispute is flagged by a customer.",
          "type": "scenario",
          "points": 20
        }
      ]
    }
  ],
  "rubrics": [
    {
      "id": "rub-1",
      "title": "Role-Workflow Mapping Rubric",
      "description": "Evaluates accuracy of role mapping and workflow analysis",
      "criteria": [
        {
          "criterion": "Role-Action Accuracy",
          "description": "Correctness of mapping each user role to its system actions",
          "weight": 0.33,
          "levels": {
            "4": "All roles accurately mapped with all system actions identified",
            "3": "Most roles correctly mapped with minor omissions",
            "2": "Some roles mapped but key actions missing",
            "1": "Role-action mapping is largely inaccurate or missing"
          }
        },
        {
          "criterion": "Escalation & Decision Point Identification",
          "description": "Ability to identify decision points and escalation triggers in the workflow",
          "weight": 0.33,
          "levels": {
            "4": "All decision points and escalation triggers correctly identified with justification",
            "3": "Most decision points identified; minor gaps in escalation paths",
            "2": "Some decision points noted but escalation logic is incomplete",
            "1": "Fails to identify key decision points or escalation triggers"
          }
        },
        {
          "criterion": "Clarity and Structure",
          "description": "Coherence and professional presentation of the workflow map",
          "weight": 0.34,
          "levels": {
            "4": "Exceptionally clear, professionally structured, and easy to follow",
            "3": "Clear and organised with minor presentation issues",
            "2": "Somewhat unclear or disorganised in structure",
            "1": "Difficult to follow; lacks logical structure"
          }
        }
      ],
      "total_weight": 1.0
    }
  ]
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


def _to_hours(value: float, duration_type: str) -> float:
    """Convert DB duration value to hours for prompt display."""
    dt = (duration_type or "HOURS").upper()
    if dt == "MINUTES":
        return round(value / 60, 2)
    if dt == "DAYS":
        return round(value * 8, 2)  # treat 1 day = 8 hours
    return value  # already hours


def _format_module_block(module: dict, fallback_order: int = 0) -> str:
    """Format one TSP module + its lessons and content into a prompt block."""
    order = module.get("module_order") or fallback_order

    raw_dur = module.get('duration', '?')
    raw_type = module.get('duration_type', 'HOURS')
    if isinstance(raw_dur, (int, float)):
        display_dur = f"{_to_hours(raw_dur, raw_type)} HOURS"
    else:
        display_dur = f"{raw_dur} {raw_type}"

    lines = [
        f"MODULE {order}: {module.get('name', 'Unnamed')}",
        f"  Description: {module.get('description', 'N/A')}",
        f"  Key concepts: {module.get('key_concepts', 'N/A')}",
        f"  Duration: {display_dur}",
        f"  Teaching strategy: {module.get('teaching_strategy', 'N/A')}",
        f"  Instructional methods: {', '.join(im['name'] for im in module.get('instructional_methods', [])) or 'N/A'}",
        f"  Primary materials: {module.get('primary_materials', 'N/A')}",
        f"  Secondary materials: {module.get('secondary_materials', 'N/A')}",
        f"  Digital tools: {module.get('digital_tools', 'N/A')}",
        f"  Differentiation strategies: {module.get('differentiation_strategies', 'N/A')}",
        f"  Inclusion strategy: {module.get('inclusion_strategy', 'N/A')}",
    ]

    for lesson in module.get("lessons", []):
        methods = [im["name"] for im in lesson.get("instructional_methods", [])]
        lesson_dur = lesson.get('duration', '?')
        lesson_type = lesson.get('duration_type', 'HOURS')
        if isinstance(lesson_dur, (int, float)):
            lesson_display = f"{_to_hours(lesson_dur, lesson_type)} HOURS"
        else:
            lesson_display = f"{lesson_dur} {lesson_type}"
        lines += [
            f"  LESSON: {lesson.get('name', 'Unnamed')}",
            f"    Duration: {lesson_display}",
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
    obj_ids_sample = ", ".join(f'"{o["id"]}"' for o in all_objectives[:8]) if all_objectives else '"obj-1", "obj-2"'

    # Compute total training hours budget for duration guidance
    raw_duration = training.get('duration', 0) or 0
    raw_dur_type = training.get('duration_type', 'HOURS')
    total_hours = _to_hours(float(raw_duration), raw_dur_type) if raw_duration else 0
    lesson_budget_hint = (
        f"Total training duration: {total_hours:.1f} hours. "
        f"Distribute lesson durations proportionally so all lesson durations sum to approximately {total_hours:.1f} hours. "
        f"Each lesson must be 0.5–2.0 HOURS. Never assign > 8 HOURS to a single lesson."
        if total_hours > 0 else
        "Each lesson must be 0.5–2.0 HOURS. Module duration = sum of lesson durations."
    )

    delivery = training.get('delivery_method', 'N/A') or 'N/A'
    n_participants = training.get('total_participants', 'N/A')

    return f"""\
Generate a complete, deployment-ready curriculum for the following TSP training.

═══════════════════════════════════════════════
TRAINING OVERVIEW
═══════════════════════════════════════════════
training_id:   {training_id}
Title:         {training.get('title', 'Unknown')}
Organization:  {training.get('company_name', 'N/A')}
Industry:      {training.get('industry_type', 'N/A')} ({training.get('business_type', 'N/A')})
Rationale:     {training.get('rationale', 'N/A')}
Scope:         {training.get('scope', 'N/A')}
Delivery mode: {delivery}
Duration:      {raw_duration} {raw_dur_type} (= {total_hours:.1f} HOURS total)
Participants:  {n_participants}
Keywords:      {', '.join(training_profile.get('keywords', [])) or 'N/A'}
Purposes:      {', '.join(training_profile.get('purposes', [])) or 'N/A'}

═══════════════════════════════════════════════
AUDIENCE PROFILE
═══════════════════════════════════════════════
{audience_block}

Bloom's cognitive target: "{bloom_target}"
Required action verbs for ALL lesson objectives: {bloom_verbs}

═══════════════════════════════════════════════
TRAINING OBJECTIVES  (use these IDs in objectives_mapping and module.objective_ids)
═══════════════════════════════════════════════
{objectives_block}

═══════════════════════════════════════════════
TSP MODULES AND ACCEPTED CONTENT
(If modules exist below, use them as the structural foundation — enrich don't discard.
If no modules are defined yet, derive 3–5 modules from the training scope and rationale.)
═══════════════════════════════════════════════
{modules_block}

═══════════════════════════════════════════════
GENERATION INSTRUCTIONS
═══════════════════════════════════════════════
TOKEN BUDGET: Output must fit in 7500 tokens. Be precise and concise: 1 sentence per description, no padding.

DURATION: {lesson_budget_hint}

1.  Create 3–5 modules aligned to the TSP module structure above
2.  Each module: 2–3 lessons — lesson objective MUST start with a Bloom's verb from "{bloom_target}" level
    - lesson.description: 1–2 sentences of context (NEVER identical to objective)
    - lesson.objective: one Bloom's verb sentence
    - lesson.instructional_methods: REQUIRED — at least 1 method
3.  Each module: exactly 1 assignment — set assignment.rubric_id = that module's rubric id
4.  Each module: exactly 1 assessment
    - Include exactly 2–3 questions. Mix types: multiple_choice, short_answer, scenario
    - multiple_choice: must include options (4 strings) and correct_answer
5.  Each module: exactly 1 rubric, EXACTLY 3 criteria, weights [0.33, 0.33, 0.34]
    - Criteria 1 & 2 MUST be domain-specific technical competencies for this module
    - Criterion 3 may be communication/presentation quality
6.  Every module MUST have a non-empty differentiation_strategies (scaffolding + extension, 1 sentence each)
7.  Fill module.objective_ids with objective IDs from the list above
8.  Fill top-level objectives_mapping: {{ "objective_id": ["mod-id", ...] }}
9.  Reference accepted content IDs in lesson.content_references where relevant
10. Set duration_type to "HOURS" throughout
11. Adapt language and examples to {learner_level} learners at {training.get('company_name', 'the organization')}
12. Do NOT invent facts — only use information from the training data above
13. Set training_id to: "{training_id}"
14. audience_profile_summary: education_level, language, learner_level, work_experience, participants, delivery_mode

Available objective IDs: [{obj_ids_sample}]

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
        # String fields that LLMs sometimes output as lists or None
        string_fields = [
            "key_concepts", "teaching_strategy", "differentiation_strategies",
            "inclusion_strategy", "primary_materials", "secondary_materials", "digital_tools"
        ]
        for sf in string_fields:
            val = mod.get(sf)
            if isinstance(val, list):
                mod[sf] = ", ".join(str(item) for item in val if item) or None
            elif val is not None and not isinstance(val, str):
                mod[sf] = str(val)

        # key_concepts fallback
        if not mod.get("key_concepts"):
            mod["key_concepts"] = mod.get("description") or mod.get("name") or "Core concepts"
        # description fallback
        if not mod.get("description"):
            mod["description"] = mod.get("key_concepts") or mod.get("name") or "Module description"
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

    # ── 6. Link rubric_id on assignments/assessments if missing ─────────────
    for mod in curriculum_data.get("modules", []):
        rubric_ids = [r.get("id") for r in mod.get("rubrics", []) if r.get("id")]
        if rubric_ids:
            primary = rubric_ids[0]
            for asgn in mod.get("assignments", []):
                if not asgn.get("rubric_id"):
                    asgn["rubric_id"] = primary
            for asmt in mod.get("assessments", []):
                if not asmt.get("rubric_id"):
                    asmt["rubric_id"] = primary

    # ── 7. Clamp unrealistic lesson/module durations ─────────────────────────
    for mod in curriculum_data.get("modules", []):
        for lesson in mod.get("lessons", []):
            dur = lesson.get("duration", 1.0)
            if isinstance(dur, (int, float)) and dur > 8.0:
                lesson["duration"] = round(dur / 60, 2) if dur > 60 else 1.0
            lesson["duration_type"] = "HOURS"
        # Recalculate module duration as sum of lesson durations
        lesson_durs = [l.get("duration", 1.0) for l in mod.get("lessons", [])]
        if lesson_durs and isinstance(lesson_durs[0], (int, float)):
            total = round(sum(lesson_durs), 2)
            if total > 0:
                mod["duration"] = total
        mod["duration_type"] = "HOURS"

    # ── 8. De-duplicate lesson description == objective ──────────────────────
    for mod in curriculum_data.get("modules", []):
        for lesson in mod.get("lessons", []):
            desc = (lesson.get("description") or "").strip()
            obj = (lesson.get("objective") or "").strip()
            if desc and obj and desc == obj:
                # Generate a distinct context-setting description
                lesson["description"] = (
                    f"In this lesson, participants explore {lesson.get('name', 'this topic')} "
                    f"through guided activities and examples drawn from the training context. "
                    f"Learners engage with relevant scenarios and apply key concepts before "
                    f"completing the lesson objective."
                )

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
