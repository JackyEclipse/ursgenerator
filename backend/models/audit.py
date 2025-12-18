"""
Audit logging models.
All actions in the system are logged for traceability and compliance.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib
import json


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # Document actions
    URS_CREATED = "urs_created"
    URS_UPDATED = "urs_updated"
    URS_VIEWED = "urs_viewed"
    URS_DELETED = "urs_deleted"
    URS_APPROVED = "urs_approved"
    URS_REJECTED = "urs_rejected"
    
    # Ingestion actions
    SOURCE_UPLOADED = "source_uploaded"
    SOURCE_CHUNKED = "source_chunked"
    
    # LLM actions
    LLM_NORMALIZE_CALLED = "llm_normalize_called"
    LLM_CLARIFY_CALLED = "llm_clarify_called"
    LLM_GENERATE_CALLED = "llm_generate_called"
    LLM_QA_CALLED = "llm_qa_called"
    
    # User actions
    USER_ANSWERED_QUESTION = "user_answered_question"
    USER_EDITED_REQUIREMENT = "user_edited_requirement"
    
    # Data access
    DATA_EXPORTED = "data_exported"
    DATA_ACCESSED = "data_accessed"


class AuditLogEntry(BaseModel):
    """
    A single audit log entry.
    These are immutable and append-only.
    """
    id: str = Field(..., description="Unique log entry ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Actor
    user_id: Optional[str] = Field(None, description="User who performed action")
    user_email: Optional[str] = None
    ip_address: Optional[str] = None
    
    # Action
    action: AuditAction
    resource_type: str = Field(..., description="e.g., 'urs', 'source_chunk'")
    resource_id: str = Field(..., description="ID of affected resource")
    
    # Context
    data_classification: str = Field(default="INTERNAL")
    session_id: Optional[str] = None
    
    # LLM-specific fields
    llm_model: Optional[str] = None
    llm_tokens_input: Optional[int] = None
    llm_tokens_output: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    
    # Content hashes (for verification without storing sensitive data)
    request_hash: Optional[str] = Field(
        None, 
        description="SHA-256 hash of request payload"
    )
    response_hash: Optional[str] = Field(
        None, 
        description="SHA-256 hash of response payload"
    )
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @staticmethod
    def compute_hash(data: Any) -> str:
        """Compute SHA-256 hash of data for audit purposes."""
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditLogQuery(BaseModel):
    """Query parameters for searching audit logs."""
    user_id: Optional[str] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    data_classification: Optional[str] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

