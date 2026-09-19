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
from typing import Any, Dict, List, Literal, Optional
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

# Bloom's Taxonomy cognitive levels (AI-generated — not in DB schema)
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
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    max_sources: int = Field(default=5, ge=1, le=20)


class CopilotResponse(BaseModel):
    """POST /copilot/message response."""
    answer: str
    sources: List[SourceAttribution] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    guardrail_triggered: bool = False
    guardrail_reason: Optional[str] = None
    embedder: str = "minilm"


class HealthResponse(BaseModel):
    """GET /health response."""
    status: Literal["healthy", "degraded"]
    database_connected: bool
    llm_connected: bool
    embedding_model_connected: bool = True
    embedding_model_status: str = "minilm"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
