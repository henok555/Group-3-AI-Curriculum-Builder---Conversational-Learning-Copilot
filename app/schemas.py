"""
Pydantic v2 schemas for the TSP AI Service API.

All types, field names, and enum literals are derived directly from the
training-solutions.sql database schema. Constraints that exist as PostgreSQL
CHECK constraints are mirrored here as Literal types so we get validation
at the Python layer before anything hits the DB.

Schema mapping (DB table → Pydantic model):
  public.trainings              → TrainingInfo
  public.audience_profiles      → AudienceProfile
  public.objectives             → Objective
  public.outcomes               → Outcome
  public.modules                → ModuleInfo (TSP source), GeneratedModule (AI output)
  public.lessons                → LessonInfo (TSP source), GeneratedLesson (AI output)
  public.contents               → ContentItem
  public.trainees + users       → LearnerProfile
  AI-owned tables               → GeneratedCurriculum, CopilotResponse, etc.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared / base types
# ---------------------------------------------------------------------------

# Mirrors the duration_type CHECK constraint used across modules, lessons, trainings
DurationType = Literal["MINUTES", "HOURS", "DAYS", "WEEKS", "MONTHS", "YEARS"]

# Mirrors trainings.delivery_method CHECK
DeliveryMethod = Literal["OFFLINE", "VIRTUAL", "BLENDED"]

# Mirrors contents.file_type CHECK
ContentFileType = Literal["PDF", "VIDEO", "LINK"]

# Mirrors contents.level CHECK
ContentLevel = Literal["MODULE", "LESSON", "ASSESSMENT"]

# Mirrors contents.status CHECK
ContentStatus = Literal["PENDING", "ACCEPTED", "REJECTED"]

# Mirrors trainees.employment_status CHECK
EmploymentStatus = Literal[
    "EMPLOYED", "EMPLOYED_PART_TIME", "UNEMPLOYED",
    "SELF_EMPLOYED", "STUDENT", "NEVER_EMPLOYED", "OTHER",
]

# Mirrors trainees.gender CHECK
Gender = Literal["MALE", "FEMALE"]

# Mirrors trainees.marital_status CHECK
MaritalStatus = Literal["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "PREFER_NOT_TO_SAY"]

# Bloom's Taxonomy cognitive levels (not in DB schema)
BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]


# ---------------------------------------------------------------------------
# TSP source-of-truth models (read from DB, never written by AI)
# These reflect real DB columns as returned by TSPClient queries.
# ---------------------------------------------------------------------------

class TrainingInfo(BaseModel):
    """
    Reflects public.trainings columns returned by get_training_profile().
    Only fields actually used by the curriculum builder are declared.
    """
    id: UUID
    title: Optional[str] = None
    rationale: Optional[str] = None
    scope: Optional[str] = None
    executive_summary: Optional[str] = None
    professional_background: Optional[str] = None
    delivery_method: Optional[DeliveryMethod] = None
    duration: Optional[float] = None
    duration_type: Optional[DurationType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_participants: Optional[int] = None
    attendance_requirement_percentage: Optional[float] = None
    assessment_result_percentage: Optional[float] = None
    is_deleted: bool = False
    # Joined fields
    company_name: Optional[str] = None
    training_type_name: Optional[str] = None

    model_config = ConfigDict(extra="ignore")  # silently ignore extra DB columns


class AudienceProfile(BaseModel):
    """
    Reflects public.audience_profiles joined with base_data lookup tables.
    Note: the DB table stores *_id FKs; TSPClient resolves them to names.
    """
    id: UUID
    training_id: Optional[UUID] = None
    certifications: Optional[str] = None
    licenses: Optional[str] = None
    # Resolved from base_data.education_levels
    education_level: Optional[str] = None
    education_level_desc: Optional[str] = None
    # Resolved from base_data.languages
    language_name: Optional[str] = None
    language_code: Optional[str] = None
    # Resolved from base_data.learner_levels
    learner_level: Optional[str] = None
    learner_level_desc: Optional[str] = None
    # Resolved from base_data.work_experiences
    work_experience: Optional[str] = None
    work_experience_desc: Optional[str] = None
    # From public.specific_courses (one-to-many, collected as list)
    specific_courses: List[str] = Field(default_factory=list)
    # From public.specific_prerequisites (one-to-many, collected as list)
    specific_prerequisites: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class Outcome(BaseModel):
    """Reflects public.outcomes."""
    id: UUID
    definition: Optional[str] = None
    objective_id: Optional[UUID] = None

    model_config = ConfigDict(extra="ignore")


class Objective(BaseModel):
    """
    Reflects public.objectives.
    objective_id (self-FK) is the parent objective; None means root-level.
    TSPClient builds this into a tree — children and outcomes are appended.
    """
    id: UUID
    definition: Optional[str] = None
    parent_id: Optional[UUID] = None   # mapped from objectives.objective_id
    children: List["Objective"] = Field(default_factory=list)
    outcomes: List[Outcome] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")

Objective.model_rebuild()  # required for self-referential model


class InstructionalMethod(BaseModel):
    """Reflects base_data.instructional_methods as returned by JOIN queries."""
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ContentItem(BaseModel):
    """
    Reflects public.contents columns.
    Only ACCEPTED contents are returned for curriculum/RAG use.
    """
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    file_type: Optional[ContentFileType] = None
    level: Optional[ContentLevel] = None
    status: Optional[ContentStatus] = None
    link: Optional[str] = None
    time_to_read_minutes: Optional[int] = None
    module_id: Optional[UUID] = None
    lesson_id: Optional[UUID] = None

    model_config = ConfigDict(extra="ignore")


class LessonInfo(BaseModel):
    """
    Reflects public.lessons columns as returned by get_modules_with_lessons().
    duration is float (double precision in DB), not duration_hours.
    """
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    # DB column name: duration (double precision NOT NULL)
    duration: float = 0.0
    duration_type: Optional[DurationType] = None
    module_id: Optional[UUID] = None
    # Joined from lesson_instructional_methods + base_data.instructional_methods
    instructional_methods: List[InstructionalMethod] = Field(default_factory=list)
    # Joined from lesson_technology_integrations + base_data.technology_integrations
    technology_integrations: List[InstructionalMethod] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class ModuleInfo(BaseModel):
    """
    Reflects public.modules columns as returned by get_modules_with_lessons().
    duration is float (double precision in DB).
    module_id (self-FK) allows sub-modules; training_tag_id and
    technology_integration_id are UUIDs to base_data tables.
    """
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    key_concepts: Optional[str] = None
    teaching_strategy: Optional[str] = None
    differentiation_strategies: Optional[str] = None
    inclusion_strategy: Optional[str] = None
    technology_integration_description: Optional[str] = None
    # DB column: duration (double precision), duration_type varchar with CHECK
    duration: Optional[float] = None
    duration_type: Optional[DurationType] = None
    module_order: Optional[int] = None
    training_id: Optional[UUID] = None
    # Self-FK: sub-module parent
    module_id: Optional[UUID] = None
    # Joined data
    instructional_methods: List[InstructionalMethod] = Field(default_factory=list)
    assessment_types: List[str] = Field(default_factory=list)
    digital_tools: Optional[str] = None
    primary_materials: Optional[str] = None
    secondary_materials: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    lessons: List[LessonInfo] = Field(default_factory=list)
    accepted_contents: List[ContentItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class LearnerProfile(BaseModel):
    """
    Reflects public.trainees with explicit column selection (no SELECT *).
    All field names match the column names returned by get_learner_profile().
    """
    id: UUID
    training_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    # Direct trainee columns
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    email: Optional[str] = None
    contact_phone: Optional[str] = None
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    field_of_study: Optional[str] = None
    employment_status: Optional[EmploymentStatus] = None
    marital_status: Optional[MaritalStatus] = None
    has_smart_phone: Optional[bool] = None
    has_training_experience: Optional[bool] = None
    training_experience_description: Optional[str] = None
    number_of_children: Optional[int] = None
    cohort_id: Optional[UUID] = None
    is_self_registered: Optional[bool] = None
    # Joined from users
    username: Optional[str] = None
    user_email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_active: Optional[bool] = None
    # Joined from roles
    role_name: Optional[str] = None
    # Joined from base_data lookup tables
    academic_level: Optional[str] = None
    academic_level_code: Optional[str] = None
    language_name: Optional[str] = None
    language_code: Optional[str] = None
    city_name: Optional[str] = None
    zone_name: Optional[str] = None

    @property
    def display_name(self) -> str:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) or self.username or str(self.id)

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------------------
# AI-generated curriculum models
# These are created by the LLM and stored in ai_generated_curricula.
# They do NOT map 1-to-1 to any TSP table.
# ---------------------------------------------------------------------------

class RubricCriterion(BaseModel):
    """One criterion within a rubric. Weights across all criteria must sum ≈ 1.0."""
    criterion: str = Field(description="Short name for the criterion, e.g. 'Content Accuracy'")
    description: str = Field(description="What this criterion measures")
    weight: float = Field(ge=0.0, le=1.0, description="Proportion of total score, e.g. 0.33")
    # Performance levels keyed by score string: "4", "3", "2", "1"
    levels: Dict[str, str] = Field(
        default_factory=dict,
        description="Score → description mapping, e.g. {'4': 'Excellent', '3': 'Good', ...}",
    )


class Rubric(BaseModel):
    """
    Assessment rubric for an assignment or assessment.
    Enforces: ≥ 3 criteria, weights summing to ≈ 1.0.
    """
    id: str
    title: str
    description: Optional[str] = None
    criteria: List[RubricCriterion] = Field(min_length=3)
    total_weight: float = Field(default=1.0, ge=0.99, le=1.01)

    @model_validator(mode="after")
    def validate_weight_sum(self) -> "Rubric":
        if not self.criteria:
            return self
        total = round(sum(c.weight for c in self.criteria), 4)
        if abs(total - 1.0) > 0.05:
            raise ValueError(
                f"Rubric '{self.title}': criteria weights sum to {total}, must be ≈ 1.0. "
                "Run validate_and_fix_curriculum() before constructing this object."
            )
        return self

    @property
    def weight_sum(self) -> float:
        return round(sum(c.weight for c in self.criteria), 4)


class GeneratedAssignment(BaseModel):
    """AI-generated assignment for a module."""
    id: str
    title: str
    description: str
    type: Literal["individual", "group", "practical", "written", "presentation"]
    estimated_hours: float = Field(gt=0)
    rubric_id: Optional[str] = None
    due_date: Optional[str] = None


class GeneratedAssessment(BaseModel):
    """AI-generated assessment for a module."""
    id: str
    title: str
    description: str
    type: Literal["quiz", "exam", "project", "portfolio", "presentation", "practical"]
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    duration_minutes: int = Field(gt=0)
    max_attempts: int = Field(default=1, ge=1)
    passing_score: float = Field(default=70.0, ge=0.0, le=100.0)
    rubric_id: Optional[str] = None


class MediaResource(BaseModel):
    """Media file, video link (e.g. YouTube), PDF, doc, or lab attached to curriculum."""
    id: Optional[str] = None
    name: str
    file_type: Optional[str] = "LINK"  # VIDEO, DOCS, LAB, PDF, LINK
    url: Optional[str] = None
    description: Optional[str] = None
    pedagogy_notes: Optional[str] = Field(
        default=None,
        description="Evaluative notes explaining why this resource is selected and what skill it reinforces"
    )
    difficulty_level: Optional[str] = "Intermediate"
    estimated_time: Optional[str] = "20 mins"
    is_primary: bool = False

    model_config = ConfigDict(extra="ignore")


class GeneratedLesson(BaseModel):
    """AI-generated lesson within a module."""
    id: str
    name: str
    description: str
    objective: str = Field(description="Bloom's-aligned learning objective")
    bloom_level: Optional[BloomLevel] = Field(
        default=None,
        description="Bloom's Taxonomy cognitive level of the objective verb"
    )
    # Duration stored as float matching DB double precision convention
    duration: float = Field(gt=0, description="Duration value (unit in duration_type)")
    duration_type: DurationType = "HOURS"
    instructional_methods: List[str] = Field(default_factory=list)
    technology_integrations: List[str] = Field(default_factory=list)
    assignments: List[GeneratedAssignment] = Field(default_factory=list)
    # IDs of ContentItem.id from TSP contents table
    content_references: List[str] = Field(
        default_factory=list,
        description="UUIDs of ACCEPTED content items referenced by this lesson"
    )
    media_resources: List[MediaResource] = Field(
        default_factory=list,
        description="Videos, YouTube links, PDFs, or files attached to this lesson"
    )


class GeneratedModule(BaseModel):
    """AI-generated curriculum module."""
    id: str
    name: str
    description: str
    key_concepts: str
    teaching_strategy: Optional[str] = None
    differentiation_strategies: Optional[str] = None
    inclusion_strategy: Optional[str] = None
    # Duration matching DB convention (double precision + type enum)
    duration: float = Field(gt=0)
    duration_type: DurationType = "HOURS"
    module_order: int = Field(ge=1)
    # UUIDs of objectives this module covers (from public.objectives.id)
    objective_ids: List[str] = Field(
        default_factory=list,
        description="IDs from public.objectives that this module addresses"
    )
    instructional_methods: List[str] = Field(default_factory=list)
    assessment_types: List[str] = Field(default_factory=list)
    primary_materials: Optional[str] = None
    secondary_materials: Optional[str] = None
    digital_tools: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    media_resources: List[MediaResource] = Field(
        default_factory=list,
        description="Videos, YouTube links, PDFs, or files attached to this module"
    )
    lessons: List[GeneratedLesson] = Field(min_length=2)
    assignments: List[GeneratedAssignment] = Field(min_length=1)
    assessments: List[GeneratedAssessment] = Field(min_length=1)
    rubrics: List[Rubric] = Field(min_length=1)

    @field_validator("lessons")
    @classmethod
    def at_least_two_lessons(cls, v: list) -> list:
        if len(v) < 2:
            raise ValueError("Each module must have at least 2 lessons")
        return v


class CurriculumValidationReport(BaseModel):
    """Records what validate_and_fix_curriculum() auto-corrected post-generation."""
    rubrics_weight_normalized: int = 0
    rubrics_criteria_padded: int = 0
    lessons_objective_filled: int = 0
    modules_assignment_added: int = 0
    modules_assessment_added: int = 0
    modules_rubric_added: int = 0
    objectives_mapping_inferred: bool = False


# ---------------------------------------------------------------------------
# Extended Curriculum Artifacts (Matching TSP database tables & manual)
# ---------------------------------------------------------------------------

class GeneratedAudienceProfile(BaseModel):
    """
    Generated audience profile matching public.audience_profiles and child tables.
    """
    learner_level: str = Field(default="Intermediate", description="Beginner, Intermediate, Advanced, or Expert")
    education_level: str = Field(default="Bachelor’s Degree", description="e.g. Bachelor’s Degree, TVET Diploma, etc.")
    language: str = Field(default="English", description="Primary language of delivery")
    work_experience: str = Field(default="Permanent Full-Time Job", description="e.g. Permanent Full-Time Job, Entry-Level")
    certifications: Optional[str] = Field(default=None, description="Required or recommended certifications")
    licenses: Optional[str] = Field(default=None, description="Required licenses or professional credentials")
    specific_courses: List[str] = Field(default_factory=list, description="Prerequisite courses (public.specific_courses)")
    specific_prerequisites: List[str] = Field(default_factory=list, description="Prerequisite skills/knowledge (public.specific_prerequisites)")


class GeneratedObjectiveOutcome(BaseModel):
    """Specific learning objective and associated outcomes (public.objectives & public.outcomes)."""
    objective: str = Field(description="Specific measurable learning objective (Bloom's-aligned)")
    outcomes: List[str] = Field(default_factory=list, description="Demonstrable learner outcomes upon completion")


class GeneratedTrainingProfile(BaseModel):
    """
    Generated training profile matching public.objectives, outcomes, and preferences.
    """
    general_objectives: List[str] = Field(default_factory=list, description="High-level overarching training objectives")
    specific_objectives: List[GeneratedObjectiveOutcome] = Field(default_factory=list, description="Targeted competency objectives and outcomes")
    learning_style_preferences: List[str] = Field(default_factory=list, description="e.g. Visual, Practical Hands-on, Collaborative")


class GeneratedSurveyChoice(BaseModel):
    """Choice item for a survey question (public.survey_entry_choices)."""
    choice_order: str = Field(description="A, B, C, D, etc.")
    choice_text: str


class GeneratedSurveyQuestion(BaseModel):
    """Question entry in a survey section (public.survey_entries)."""
    question_number: int
    question: str
    question_type: Literal["TEXT", "RADIO", "CHECKBOX", "GRID"] = "RADIO"
    is_required: bool = True
    is_follow_up: bool = False
    parent_choice: Optional[str] = None
    choices: List[GeneratedSurveyChoice] = Field(default_factory=list)


class GeneratedSurveySection(BaseModel):
    """Section within a survey (public.survey_sections)."""
    title: str
    description: str
    entries: List[GeneratedSurveyQuestion] = Field(default_factory=list)


class GeneratedSurvey(BaseModel):
    """
    Baseline or Endline evaluation survey (public.surveys).
    """
    name: str
    survey_type: Literal["BASELINE", "ENDLINE", "OTHER"]
    description: str
    sections: List[GeneratedSurveySection] = Field(default_factory=list)


class GeneratedFormalAssessmentChoice(BaseModel):
    """Choice item for an assessment question (public.assessment_entry_choices)."""
    choice_text: str
    is_correct: bool = False


class GeneratedFormalAssessmentQuestion(BaseModel):
    """Question entry in a formal assessment section (public.assessment_entries)."""
    question_number: int
    question: str
    question_type: Literal["RADIO", "CHECKBOX", "TEXT", "FILE_UPLOAD"] = "RADIO"
    weight: float = Field(default=10.0, description="Points/weight for this question")
    choices: List[GeneratedFormalAssessmentChoice] = Field(default_factory=list)


class GeneratedFormalAssessmentSection(BaseModel):
    """Section within a formal assessment (public.assessment_sections)."""
    section_number: int
    title: str
    description: str
    entries: List[GeneratedFormalAssessmentQuestion] = Field(default_factory=list)


class GeneratedFormalAssessment(BaseModel):
    """
    Pre-assessment, Continuous Assessment Test (CAT), or Post-assessment (public.assessments).
    """
    name: str
    assessment_type: Literal["PRE_POST", "CAT", "OTHER"]
    description: str
    is_timed: bool = True
    duration_minutes: int = Field(gt=0, description="Duration limit in minutes")
    max_attempts: int = Field(default=1, ge=1)
    passing_score: float = Field(default=70.0, ge=0.0, le=100.0)
    assessment_target: Literal["INDIVIDUAL", "GROUP"] = "INDIVIDUAL"
    sections: List[GeneratedFormalAssessmentSection] = Field(default_factory=list)


class GeneratedContentRequest(BaseModel):
    """
    Specification for materials to request from content developers (public.contents / manual 3.5).
    """
    content_name: str
    content_type: str = Field(description="e.g. SLIDES, DOCUMENT, VIDEO, LAB_MANUAL, CODE_NOTEBOOK")
    target_module: str
    target_lesson: Optional[str] = None
    description: str


class GeneratedCurriculum(BaseModel):
    """
    Top-level AI-generated curriculum response.
    Stored as JSONB in ai_generated_curricula.curriculum_json.
    """
    training_id: str = Field(description="UUID string of public.trainings.id")
    training_title: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    modules: List[GeneratedModule] = Field(min_length=3)
    audience_profile_summary: Dict[str, Any] = Field(default_factory=dict)
    # objective_id (str UUID) → list of module ids that cover it
    objectives_mapping: Dict[str, List[str]] = Field(default_factory=dict)
    validation_report: Optional[CurriculumValidationReport] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Extended artifacts matching manual (doc.md) & DB tables
    audience_profile: Optional[GeneratedAudienceProfile] = None
    training_profile: Optional[GeneratedTrainingProfile] = None
    surveys: List[GeneratedSurvey] = Field(default_factory=list)
    formal_assessments: List[GeneratedFormalAssessment] = Field(default_factory=list)
    content_requests: List[GeneratedContentRequest] = Field(default_factory=list)

    @field_validator("modules")
    @classmethod
    def at_least_three_modules(cls, v: list) -> list:
        if len(v) < 3:
            raise ValueError("Curriculum must have at least 3 modules")
        return v


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class CurriculumRequest(BaseModel):
    """POST /curriculum/generate request body."""
    training_id: str = Field(description="UUID of the training to generate a curriculum for")
    learner_id: Optional[str] = Field(
        default=None,
        description="Optional trainee UUID for personalisation hints"
    )
    force_regenerate: bool = Field(
        default=False,
        description="If False and a curriculum already exists for this training, return cached version"
    )
    options: Dict[str, Any] = Field(default_factory=dict)


class CustomCurriculumRequest(BaseModel):
    """POST /curriculum/generate-custom request body for creating a curriculum from scratch."""
    title: str = Field(description="Training title")
    rationale: str = Field(description="Business context, goals, and problem statement")
    scope: str = Field(description="Key topics, technical domains, and boundaries")
    company_name: str = Field(default="Enterprise Organization", description="Company or client name")
    industry_type: str = Field(default="Technology & Banking", description="Industry domain")
    duration_hours: float = Field(default=12.0, ge=1.0, le=200.0, description="Total training duration in hours")
    delivery_method: str = Field(default="BLENDED", description="OFFLINE, ONLINE, or BLENDED")
    learner_level: str = Field(default="Intermediate", description="Beginner, Intermediate, or Advanced")
    education_level: str = Field(default="Bachelor's Degree", description="Expected education level")
    language: str = Field(default="English", description="Instruction language")
    prerequisites: List[str] = Field(default_factory=list, description="Recommended prerequisites")
    specific_objectives: List[str] = Field(default_factory=list, description="Optional custom target objectives")
    resource_links: List[str] = Field(
        default_factory=list,
        description="Optional list of external video links, YouTube URLs, or document URLs to integrate"
    )


class DraftEnhanceRequest(BaseModel):
    """POST /curriculum/enhance-draft request body."""
    title: str = Field(description="Draft training title")
    rationale: Optional[str] = Field(default="", description="Draft rationale or problem statement")
    scope: Optional[str] = Field(default="", description="Draft topics or scope")
    learner_level: Optional[str] = Field(default="Intermediate", description="Beginner, Intermediate, or Advanced")
    company_name: Optional[str] = Field(default="Enterprise Organization", description="Client or company name")
    industry_type: Optional[str] = Field(default="Technology & Banking", description="Industry domain")
    duration_hours: Optional[float] = Field(default=None, description="Draft duration in hours")
    prerequisites: Optional[Union[str, List[str]]] = Field(default="", description="Draft prerequisites as string or list")


class DraftEnhanceResponse(BaseModel):
    """POST /curriculum/enhance-draft response body."""
    title: str
    rationale: str
    scope: str
    learner_level: str = "Intermediate"
    prerequisites: Union[str, List[str]] = ""
    suggested_duration_hours: float = 16.0
    enhancement_summary: str = ""



class SourceAttribution(BaseModel):
    """RAG source chunk citation included in copilot responses."""
    content_id: str
    module_id: Optional[str] = None
    lesson_id: Optional[str] = None
    module_name: Optional[str] = None
    lesson_name: Optional[str] = None
    excerpt: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class CopilotRequest(BaseModel):
    """POST /copilot/message request body."""
    training_id: str
    learner_id: Optional[str] = None
    question: str = Field(min_length=1, max_length=2000)
    # Server-side multi-turn context: pass the session_id returned by a previous
    # response to continue that conversation. Omit to start a new session.
    session_id: Optional[str] = Field(default=None, max_length=64)
    # Legacy client-supplied history — used only when no server-side session exists.
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    max_sources: int = Field(default=5, ge=1, le=20)


class NextActivityRecommendation(BaseModel):
    """Deterministic, evidence-grounded next-activity recommendation."""
    activity: str
    reason: str


class PersonalizationInfo(BaseModel):
    """How the copilot adapted this answer to the learner."""
    tier: str
    performance_level: str = "no_evidence"
    evidence_summary: Optional[str] = None


class CopilotResponse(BaseModel):
    """POST /copilot/message response."""
    answer: str
    sources: List[SourceAttribution] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    guardrail_triggered: bool = False
    guardrail_reason: Optional[str] = None
    embedder: str = "minilm"
    session_id: Optional[str] = None
    personalization: Optional[PersonalizationInfo] = None
    recommended_next_activity: Optional[NextActivityRecommendation] = None


class HealthResponse(BaseModel):
    """GET /health response."""
    status: Literal["healthy", "degraded"]
    database_connected: bool
    llm_connected: bool
    embedding_model_connected: bool = True
    embedding_model_status: str = "minilm"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CurriculumRegenerateRequest(BaseModel):
    """POST /curriculum/{training_id}/regenerate request body."""
    reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason for forcing regeneration (logged in metadata)"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional generation overrides (reserved for future use)"
    )


class CurriculumHistoryEntry(BaseModel):
    """One entry in GET /curriculum/{training_id}/history."""
    curriculum_db_id: str = Field(description="UUID of the ai_generated_curricula row")
    generated_at: str = Field(description="ISO timestamp when this version was generated")
    module_count: Optional[int] = Field(default=None, description="Number of modules in this version")
    training_title: Optional[str] = None
    validation_report: Dict[str, Any] = Field(default_factory=dict)

