"""
Pydantic models for the canonical URS schema.
These models mirror the JSON schema and provide validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class URSStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"
    SUPERSEDED = "superseded"


class DataClassification(str, Enum):
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class Priority(str, Enum):
    MUST = "Must"
    SHOULD = "Should"
    COULD = "Could"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NFRCategory(str, Enum):
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    AVAILABILITY = "availability"
    SECURITY = "security"
    USABILITY = "usability"
    ACCESSIBILITY = "accessibility"
    MAINTAINABILITY = "maintainability"
    COMPLIANCE = "compliance"
    INTEROPERABILITY = "interoperability"


# ============================================================================
# Sub-models
# ============================================================================

class Person(BaseModel):
    """Person reference (requestor, owner, etc.)"""
    name: str
    email: str
    department: Optional[str] = None
    role: Optional[str] = None


class SourceReference(BaseModel):
    """
    Reference to a source chunk.
    CRITICAL: Every requirement must link back to sources.
    """
    chunk_id: str = Field(..., description="Unique ID of the source chunk")
    source_type: Optional[str] = Field(
        None, 
        description="document, email, meeting_notes, interview, screenshot, link, user_input"
    )
    source_name: Optional[str] = None
    excerpt: Optional[str] = Field(None, description="Relevant excerpt from source")
    is_assumption: bool = Field(
        False, 
        description="True if this was inferred by LLM without explicit source"
    )


class AcceptanceCriterion(BaseModel):
    """Single testable acceptance criterion."""
    criterion_id: Optional[str] = None
    criterion: str = Field(..., description="Testable acceptance criterion")
    test_method: Optional[str] = Field(None, description="manual, automated, review, demo")


class FunctionalRequirement(BaseModel):
    """
    A single functional requirement with full traceability.
    """
    requirement_id: str = Field(..., pattern=r"^FR-[0-9]{3}$", description="e.g., FR-001")
    priority: Priority
    description: str = Field(..., description="The system shall... format")
    rationale: Optional[str] = None
    acceptance_criteria: List[AcceptanceCriterion] = Field(
        ..., 
        min_length=1,
        description="At least one testable criterion required"
    )
    source_references: List[SourceReference] = Field(
        default_factory=list,
        description="Links to source chunks"
    )
    confidence_level: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="LLM confidence in this requirement"
    )
    related_requirements: List[str] = Field(default_factory=list)
    user_stories: List[str] = Field(default_factory=list)
    
    @field_validator("description")
    @classmethod
    def validate_description_format(cls, v: str) -> str:
        """Ensure description follows 'The system shall...' format."""
        if not v.startswith("The system shall"):
            # Auto-fix common patterns
            if v.lower().startswith("the system should"):
                v = "The system shall" + v[17:]
            elif not v.startswith("The system"):
                v = f"The system shall {v}"
        return v


class NonFunctionalRequirement(BaseModel):
    """Non-functional requirement (performance, security, etc.)"""
    requirement_id: str = Field(..., pattern=r"^NFR-[0-9]{3}$")
    category: NFRCategory
    description: str
    target_metric: Optional[str] = None
    measurement_method: Optional[str] = None
    priority: Priority = Priority.SHOULD
    source_references: List[SourceReference] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM


class PainPoint(BaseModel):
    """A specific pain point in the problem statement."""
    description: str
    impact: Optional[str] = None
    frequency: Optional[str] = None
    source_references: List[SourceReference] = Field(default_factory=list)


class Assumption(BaseModel):
    """An assumption that needs validation."""
    assumption_id: Optional[str] = None
    assumption: str
    is_validated: bool = False
    validated_by: Optional[str] = None
    validation_date: Optional[date] = None
    risk_if_wrong: Optional[str] = None


class Dependency(BaseModel):
    """A project dependency."""
    dependency_id: Optional[str] = None
    dependency: str
    type: Optional[str] = Field(None, description="system, team, external, regulatory, data")
    owner: Optional[str] = None
    status: str = "identified"


class Risk(BaseModel):
    """A project risk."""
    risk_id: str
    description: str
    likelihood: str = Field(..., description="low, medium, high")
    impact: str = Field(..., description="low, medium, high")
    mitigation: Optional[str] = None
    owner: Optional[str] = None


class OpenQuestion(BaseModel):
    """An open question that needs answering."""
    question_id: str
    question: str
    context: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    status: str = "open"
    answer: Optional[str] = None


class SuccessMetric(BaseModel):
    """A measurable success metric."""
    metric_id: str
    name: str
    description: Optional[str] = None
    baseline: Optional[str] = None
    target: str
    measurement_method: Optional[str] = None
    measurement_frequency: Optional[str] = None


class VersionEntry(BaseModel):
    """Version history entry."""
    version: str
    date: datetime
    author: str
    changes: str
    approved_by: Optional[str] = None


class Approval(BaseModel):
    """Approval record."""
    role: str
    approver_name: Optional[str] = None
    approver_email: Optional[str] = None
    status: str = "pending"
    comments: Optional[str] = None
    date: Optional[datetime] = None


class WorkflowStep(BaseModel):
    """A step in the workflow description."""
    step_number: int
    description: str
    actor: Optional[str] = None
    system: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    decision_points: List[str] = Field(default_factory=list)


class DataInput(BaseModel):
    """Data input specification."""
    name: str
    description: str
    source_system: Optional[str] = None
    format: Optional[str] = None
    frequency: Optional[str] = None
    volume: Optional[str] = None
    data_classification: Optional[str] = None


class DataOutput(BaseModel):
    """Data output specification."""
    name: str
    description: str
    destination_system: Optional[str] = None
    format: Optional[str] = None
    frequency: Optional[str] = None


class Persona(BaseModel):
    """User persona definition."""
    persona_id: str
    name: str
    role: str
    responsibilities: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    frequency_of_use: Optional[str] = None
    technical_proficiency: Optional[str] = None


# ============================================================================
# Composite Models
# ============================================================================

class URSMetadata(BaseModel):
    """URS document metadata."""
    id: str = Field(..., pattern=r"^URS-[0-9]{4}-[0-9]{4}$", description="e.g., URS-2024-0001")
    title: str = Field(..., min_length=10, max_length=200)
    requestor: Person
    department: str
    status: URSStatus = URSStatus.DRAFT
    owner: Person
    data_classification: DataClassification = DataClassification.INTERNAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    target_completion_date: Optional[date] = None
    tags: List[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    """Executive summary section."""
    summary: str = Field(..., min_length=50, max_length=1000)
    business_value: str
    source_references: List[SourceReference] = Field(default_factory=list)


class ProblemStatement(BaseModel):
    """Problem statement section."""
    current_state: str
    pain_points: List[PainPoint]
    desired_state: str
    source_references: List[SourceReference] = Field(default_factory=list)


class Scope(BaseModel):
    """Scope definition section."""
    in_scope: List[dict]  # Simplified for MVP
    out_of_scope: List[dict]
    assumptions: List[Assumption] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    constraints: List[dict] = Field(default_factory=list)


class DataRequirements(BaseModel):
    """Data requirements section."""
    inputs: List[DataInput] = Field(default_factory=list)
    outputs: List[DataOutput] = Field(default_factory=list)
    quality_rules: List[dict] = Field(default_factory=list)
    retention_requirements: Optional[dict] = None


class WorkflowDescription(BaseModel):
    """Workflow description section."""
    overview: Optional[str] = None
    steps: List[WorkflowStep] = Field(default_factory=list)
    exceptions: List[dict] = Field(default_factory=list)


class RisksAndQuestions(BaseModel):
    """Risks and open questions section."""
    risks: List[Risk] = Field(default_factory=list)
    open_questions: List[OpenQuestion] = Field(default_factory=list)


class GenerationMetadata(BaseModel):
    """Metadata about LLM generation."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model: str
    source_chunk_count: int
    qa_score: Optional[dict] = None
    assumptions_count: int = 0
    low_confidence_count: int = 0


# ============================================================================
# Main URS Model
# ============================================================================

class URS(BaseModel):
    """
    Complete User Requirements Specification document.
    This is the canonical format for all URS documents.
    """
    metadata: URSMetadata
    executive_summary: ExecutiveSummary
    problem_statement: ProblemStatement
    users_and_personas: List[Persona] = Field(default_factory=list)
    scope: Scope
    functional_requirements: List[FunctionalRequirement] = Field(..., min_length=1)
    non_functional_requirements: List[NonFunctionalRequirement] = Field(default_factory=list)
    data_requirements: Optional[DataRequirements] = None
    workflow_description: Optional[WorkflowDescription] = None
    risks_and_open_questions: Optional[RisksAndQuestions] = None
    success_metrics: List[SuccessMetric] = Field(default_factory=list)
    version_history: List[VersionEntry] = Field(default_factory=list)
    approvals: List[Approval] = Field(default_factory=list)
    _generation_metadata: Optional[GenerationMetadata] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "id": "URS-2024-0001",
                    "title": "Automated Invoice Processing System",
                    "requestor": {"name": "Jane Smith", "email": "jane@company.com"},
                    "department": "Finance",
                    "status": "draft",
                    "owner": {"name": "John Doe", "email": "john@company.com"},
                    "data_classification": "INTERNAL"
                }
            }
        }


class URSCreate(BaseModel):
    """Request model for creating a new URS."""
    title: str = Field(..., min_length=10, max_length=200)
    requestor_name: str
    requestor_email: str
    department: str
    data_classification: DataClassification = DataClassification.INTERNAL


class URSUpdate(BaseModel):
    """Request model for updating an existing URS."""
    title: Optional[str] = None
    status: Optional[URSStatus] = None
    functional_requirements: Optional[List[FunctionalRequirement]] = None
    # Add other fields as needed for manual editing

