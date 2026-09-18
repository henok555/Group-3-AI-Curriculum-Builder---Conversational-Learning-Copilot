"""
Pydantic schemas for the AI Service API.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# ==================== Learner Profile ====================

class LearnerProfile(BaseModel):
    """Learner/trainee profile for personalization."""
    id: str
    user_id: Optional[str] = None
    training_id: Optional[str] = None
    first_name: str
    last_name: str
    email: str
    role_name: Optional[str] = None
    academic_level: Optional[str] = None
    language: Optional[str] = None
    language_code: Optional[str] = None
    city: Optional[str] = None
    zone: Optional[str] = None
    employment_status: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    field_of_study: Optional[str] = None
    has_smart_phone: Optional[bool] = None
    has_training_experience: Optional[bool] = None
    cohort_id: Optional[str] = None


# ==================== Curriculum Generation ====================

class RubricCriterion(BaseModel):
    """Single rubric criterion."""
    criterion: str
    description: str
    weight: float = Field(ge=0, le=1)
    levels: Dict[str, str] = Field(default_factory=dict)  # e.g., {"4": "Excellent", "3": "Good", ...}


class Rubric(BaseModel):
    """Assessment rubric."""
    id: str
    title: str
    description: Optional[str] = None
    criteria: List[RubricCriterion]
    total_weight: float = 1.0


class Assignment(BaseModel):
    """Module/lesson assignment."""
    id: str
    title: str
    description: str
    type: Literal["individual", "group", "practical", "written", "presentation"]
    estimated_hours: float
    rubric_id: Optional[str] = None
    due_date: Optional[str] = None


class Assessment(BaseModel):
    """Module assessment."""
    id: str
    title: str
    description: str
    type: Literal["quiz", "exam", "project", "portfolio", "presentation", "practical"]
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    duration_minutes: int
    max_attempts: int = 1
    passing_score: float = 70.0
    rubric_id: Optional[str] = None


class Lesson(BaseModel):
    """Lesson within a module."""
    id: str
    name: str
    description: str
    objective: str
    duration_hours: float
    duration_type: str = "HOURS"
    instructional_methods: List[str] = Field(default_factory=list)
    technology_integrations: List[str] = Field(default_factory=list)
    assignments: List[Assignment] = Field(default_factory=list)
    content_references: List[str] = Field(default_factory=list)  # content IDs


class Module(BaseModel):
    """Training module."""
    id: str
    name: str
    description: str
    key_concepts: str
    teaching_strategy: Optional[str] = None
    differentiation_strategies: Optional[str] = None
    inclusion_strategy: Optional[str] = None
    duration_hours: float
    duration_type: str = "HOURS"
    module_order: int
    instructional_methods: List[str] = Field(default_factory=list)
    assessment_types: List[str] = Field(default_factory=list)
    primary_materials: Optional[str] = None
    secondary_materials: Optional[str] = None
    digital_tools: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    lessons: List[Lesson] = Field(default_factory=list)
    assignments: List[Assignment] = Field(default_factory=list)
    assessments: List[Assessment] = Field(default_factory=list)
    rubrics: List[Rubric] = Field(default_factory=list)


class CurriculumRequest(BaseModel):
    """Request to generate curriculum."""
    training_id: str
    learner_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Curriculum(BaseModel):
    """Generated curriculum response."""
    training_id: str
    training_title: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    modules: List[Module]
    audience_profile_summary: Dict[str, Any]
    objectives_mapping: Dict[str, List[str]] = Field(default_factory=dict)  # objective_id -> module_ids
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Copilot ====================

class SourceAttribution(BaseModel):
    """Source citation for copilot answers."""
    content_id: str
    module_id: Optional[str] = None
    lesson_id: Optional[str] = None
    module_name: Optional[str] = None
    lesson_name: Optional[str] = None
    excerpt: str
    similarity_score: float


class CopilotRequest(BaseModel):
    """Request to copilot."""
    training_id: str
    learner_id: Optional[str] = None
    question: str
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    max_sources: int = 5


class CopilotResponse(BaseModel):
    """Copilot response with sources."""
    answer: str
    sources: List[SourceAttribution] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    guardrail_triggered: bool = False
    guardrail_reason: Optional[str] = None
    embedder: str = "minilm"


# ==================== Health ====================

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    llm_connected: bool
    embedding_model_connected: bool = True
    embedding_model_status: str = "minilm"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
