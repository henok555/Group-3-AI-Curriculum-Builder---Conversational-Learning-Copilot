"""
Unit tests for app/curriculum_builder.py

Tests:
- Bloom's taxonomy mapping
- Prompt building (no LLM, no DB)
- validate_and_fix_curriculum (all correction paths)
- Weight normalization edge cases
- Objectives mapping inference
"""

import pytest
from app.curriculum_builder import (
    LEARNER_LEVEL_TO_BLOOM,
    BLOOM_VERBS,
    _flatten_objectives,
    _normalize_weights,
    _make_default_criterion,
    _make_default_assignment,
    _make_default_assessment,
    _make_default_rubric,
    validate_and_fix_curriculum,
    build_curriculum_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _module(mid, name, **kw):
    base = dict(
        id=mid, name=name, description="desc", key_concepts="kc",
        duration=2.0, duration_type="HOURS", module_order=1,
        objective_ids=[], instructional_methods=[], assessment_types=[],
        lessons=[], assignments=[], assessments=[], rubrics=[],
    )
    base.update(kw)
    return base


def _valid_rubric(mid, name):
    return dict(
        id=f"rub-{mid}", title=f"{name} Rubric", total_weight=1.0,
        criteria=[
            dict(criterion="A", description="d", weight=0.33, levels={}),
            dict(criterion="B", description="d", weight=0.33, levels={}),
            dict(criterion="C", description="d", weight=0.34, levels={}),
        ],
    )


def _valid_assignment(mid):
    return dict(id=f"asgn-{mid}", title="T", description="D", type="practical", estimated_hours=1.0)


def _valid_assessment(mid):
    return dict(id=f"asmt-{mid}", title="T", description="D", type="quiz", duration_minutes=30, questions=[])


def _wrap(modules):
    return dict(
        training_id="test-uuid",
        training_title="Test Training",
        modules=modules,
        audience_profile_summary={},
        objectives_mapping={},
        metadata={},
    )


# ---------------------------------------------------------------------------
# 1. Bloom's Taxonomy mapping
# ---------------------------------------------------------------------------

def test_bloom_all_levels_have_verbs():
    for level in LEARNER_LEVEL_TO_BLOOM.values():
        assert level in BLOOM_VERBS, f"Missing verb list for bloom level: {level}"


def test_bloom_learner_level_intermediate_maps_to_apply():
    assert LEARNER_LEVEL_TO_BLOOM["Intermediate"] == "Apply"


def test_bloom_learner_level_advanced_maps_to_analyze():
    assert LEARNER_LEVEL_TO_BLOOM["Advanced"] == "Analyze"


# ---------------------------------------------------------------------------
# 2. _flatten_objectives
# ---------------------------------------------------------------------------

def test_flatten_objectives_flat_list():
    objectives = [
        {"id": "o1", "definition": "Root 1", "children": [], "outcomes": []},
        {"id": "o2", "definition": "Root 2", "children": [], "outcomes": []},
    ]
    flat = _flatten_objectives(objectives)
    assert len(flat) == 2
    assert flat[0]["id"] == "o1"
    assert flat[1]["id"] == "o2"


def test_flatten_objectives_with_children_and_outcomes():
    objectives = [
        {
            "id": "o1",
            "definition": "Root",
            "children": [
                {
                    "id": "o1-1",
                    "definition": "Child",
                    "outcomes": [{"id": "oc1", "definition": "Outcome A"}],
                }
            ],
            "outcomes": [],
        }
    ]
    flat = _flatten_objectives(objectives)
    # Root + Child + Outcome = 3
    assert len(flat) == 3
    assert any(f["id"] == "o1" for f in flat)
    assert any(f["id"] == "o1-1" for f in flat)
    outcome_entry = next(f for f in flat if f["id"] == "oc1")
    assert outcome_entry["definition"].startswith("Outcome:")


# ---------------------------------------------------------------------------
# 3. _normalize_weights
# ---------------------------------------------------------------------------

def test_normalize_weights_already_correct():
    criteria = [
        {"weight": 0.33}, {"weight": 0.33}, {"weight": 0.34},
    ]
    result, changed = _normalize_weights(criteria)
    assert changed is False
    assert abs(sum(c["weight"] for c in result) - 1.0) <= 0.01


def test_normalize_weights_rescales_out_of_range():
    criteria = [{"weight": 2.0}, {"weight": 3.0}, {"weight": 5.0}]
    result, changed = _normalize_weights(criteria)
    assert changed is True
    total = round(sum(c["weight"] for c in result), 4)
    assert abs(total - 1.0) <= 0.01


def test_normalize_weights_all_zero_distributes_equally():
    criteria = [{"weight": 0.0}, {"weight": 0.0}, {"weight": 0.0}]
    result, changed = _normalize_weights(criteria)
    assert changed is True
    for c in result:
        assert c["weight"] > 0


def test_normalize_weights_single_criterion():
    criteria = [{"weight": 5.0}]
    result, changed = _normalize_weights(criteria)
    assert changed is True
    assert result[0]["weight"] == 1.0


# ---------------------------------------------------------------------------
# 4. Default component factories
# ---------------------------------------------------------------------------

def test_make_default_criterion_has_four_levels():
    crit = _make_default_criterion(0, "Intro Module")
    assert set(crit["levels"].keys()) == {"4", "3", "2", "1"}
    assert crit["weight"] > 0


def test_make_default_rubric_has_three_criteria():
    rub = _make_default_rubric("mod-1", "Test Module")
    assert len(rub["criteria"]) == 3
    assert abs(sum(c["weight"] for c in rub["criteria"]) - 1.0) <= 0.01


def test_make_default_assignment_type_is_practical():
    asgn = _make_default_assignment("mod-1", "Test Module")
    assert asgn["type"] == "practical"
    assert asgn["estimated_hours"] > 0


def test_make_default_assessment_type_is_quiz():
    asmt = _make_default_assessment("mod-1", "Test Module")
    assert asmt["type"] == "quiz"
    assert asmt["duration_minutes"] > 0
    assert asmt["passing_score"] >= 70.0


# ---------------------------------------------------------------------------
# 5. validate_and_fix_curriculum — all paths
# ---------------------------------------------------------------------------

def test_validate_normalises_bad_rubric_weights():
    mod = _module("m1", "M", rubrics=[{
        "id": "r1", "title": "R", "total_weight": 10.0,
        "criteria": [
            {"criterion": "A", "description": "d", "weight": 2.0, "levels": {}},
            {"criterion": "B", "description": "d", "weight": 3.0, "levels": {}},
            {"criterion": "C", "description": "d", "weight": 5.0, "levels": {}},
        ],
    }], assignments=[_valid_assignment("m1")], assessments=[_valid_assessment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    weights = [c["weight"] for c in fixed["modules"][0]["rubrics"][0]["criteria"]]
    assert abs(sum(weights) - 1.0) <= 0.01
    assert report.rubrics_weight_normalized >= 1


def test_validate_pads_rubric_with_one_criterion():
    mod = _module("m1", "M", rubrics=[{
        "id": "r1", "title": "R", "total_weight": 1.0,
        "criteria": [{"criterion": "A", "description": "d", "weight": 1.0, "levels": {}}],
    }], assignments=[_valid_assignment("m1")], assessments=[_valid_assessment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    assert len(fixed["modules"][0]["rubrics"][0]["criteria"]) >= 3
    assert report.rubrics_criteria_padded >= 2


def test_validate_adds_missing_assignment():
    mod = _module("m1", "M",
                  rubrics=[_valid_rubric("m1", "M")],
                  assessments=[_valid_assessment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    assert len(fixed["modules"][0]["assignments"]) >= 1
    assert report.modules_assignment_added >= 1


def test_validate_adds_missing_assessment():
    mod = _module("m1", "M",
                  rubrics=[_valid_rubric("m1", "M")],
                  assignments=[_valid_assignment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    assert len(fixed["modules"][0]["assessments"]) >= 1
    assert report.modules_assessment_added >= 1


def test_validate_adds_missing_rubric():
    mod = _module("m1", "M",
                  assignments=[_valid_assignment("m1")],
                  assessments=[_valid_assessment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    assert len(fixed["modules"][0]["rubrics"]) >= 1
    assert report.modules_rubric_added >= 1


def test_validate_fills_empty_lesson_objective():
    lesson = dict(id="l1", name="Intro", description="d", objective="",
                  duration=1.0, duration_type="HOURS")
    mod = _module("m1", "M",
                  lessons=[lesson],
                  rubrics=[_valid_rubric("m1", "M")],
                  assignments=[_valid_assignment("m1")],
                  assessments=[_valid_assessment("m1")])
    fixed, report = validate_and_fix_curriculum(_wrap([mod]))
    assert len(fixed["modules"][0]["lessons"][0]["objective"]) > 0
    assert report.lessons_objective_filled >= 1


def test_validate_infers_objectives_mapping():
    mod = _module("m1", "M",
                  objective_ids=["obj-1", "obj-2"],
                  rubrics=[_valid_rubric("m1", "M")],
                  assignments=[_valid_assignment("m1")],
                  assessments=[_valid_assessment("m1")])
    data = _wrap([mod])
    data["objectives_mapping"] = {}
    fixed, report = validate_and_fix_curriculum(data)
    assert "obj-1" in fixed["objectives_mapping"]
    assert "m1" in fixed["objectives_mapping"]["obj-1"]
    assert report.objectives_mapping_inferred is True


def test_validate_does_not_overwrite_existing_mapping():
    mod = _module("m1", "M",
                  objective_ids=["obj-1"],
                  rubrics=[_valid_rubric("m1", "M")],
                  assignments=[_valid_assignment("m1")],
                  assessments=[_valid_assessment("m1")])
    data = _wrap([mod])
    data["objectives_mapping"] = {"already": ["here"]}   # pre-existing
    fixed, report = validate_and_fix_curriculum(data)
    assert report.objectives_mapping_inferred is False  # must NOT overwrite
    assert "already" in fixed["objectives_mapping"]


def test_validate_multiple_modules_all_fixed():
    """All three modules with bad rubrics should all be corrected."""
    modules = [
        _module(f"m{i}", f"Module {i}", rubrics=[{
            "id": f"r{i}", "title": "R", "total_weight": 100.0,
            "criteria": [{"criterion": f"C{i}", "description": "d", "weight": 100.0, "levels": {}}],
        }], assignments=[_valid_assignment(f"m{i}")], assessments=[_valid_assessment(f"m{i}")])
        for i in range(1, 4)
    ]
    fixed, report = validate_and_fix_curriculum(_wrap(modules))
    for mod in fixed["modules"]:
        for rub in mod["rubrics"]:
            total = round(sum(c["weight"] for c in rub["criteria"]), 4)
            assert abs(total - 1.0) <= 0.01
    assert report.rubrics_weight_normalized == 3
    assert report.rubrics_criteria_padded == 6  # each had 1 criterion, needs 2 more → 3*2=6


# ---------------------------------------------------------------------------
# 6. build_curriculum_prompt — smoke test (no LLM call)
# ---------------------------------------------------------------------------

def test_build_curriculum_prompt_contains_training_id():
    training_profile = {
        "training": {"title": "Test Training", "rationale": "R", "scope": "S",
                     "delivery_method": "OFFLINE", "duration": 5.0, "duration_type": "DAYS"},
        "objectives": [],
        "keywords": ["digital", "skills"],
        "purposes": ["Upskilling"],
    }
    modules = []
    audience = {
        "learner_level": "Intermediate",
        "education_level": "Bachelor",
        "language_name": "English",
        "language_code": "en",
        "work_experience": "1-3 years",
        "specific_courses": [],
        "specific_prerequisites": [],
    }
    prompt = build_curriculum_prompt(training_profile, modules, audience, "test-training-uuid")
    assert "test-training-uuid" in prompt
    assert "Test Training" in prompt
    assert "Apply" in prompt  # Bloom's target for Intermediate


def test_build_curriculum_prompt_includes_bloom_verbs():
    training_profile = {
        "training": {"title": "T", "rationale": "R", "scope": "S"},
        "objectives": [],
        "keywords": [],
        "purposes": [],
    }
    audience = {"learner_level": "Advanced", "specific_courses": [], "specific_prerequisites": []}
    prompt = build_curriculum_prompt(training_profile, [], audience, "uuid-1")
    # Intermediate → Apply, Advanced → Analyze
    assert "Analyze" in prompt or "analyze" in prompt
