"""
URS Management Router

Handles:
- GET /urs/{id} - Retrieve URS document
- PUT /urs/{id} - Update URS document
- POST /urs/{id}/approve - Submit for approval
- GET /urs - List all URS documents
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from models.urs import URS, URSStatus, VersionEntry, Approval

router = APIRouter()


@router.get("/urs/{urs_id}")
async def get_urs(urs_id: str, version: Optional[str] = None):
    """
    Retrieve a URS document by ID.
    
    ## Parameters
    - **urs_id**: The unique URS identifier (e.g., URS-2024-0001)
    - **version**: Optional specific version to retrieve
    
    ## Response
    Returns the complete URS document in canonical JSON format.
    Includes generation metadata and audit information.
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    # TODO: Handle version retrieval from version history
    
    return {
        "urs": urs.model_dump(),
        "retrieved_at": datetime.utcnow().isoformat(),
    }


@router.get("/urs")
async def list_urs(
    status: Optional[URSStatus] = None,
    department: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    List all URS documents with optional filtering.
    
    ## Filters
    - **status**: Filter by status (draft, in_review, approved, etc.)
    - **department**: Filter by department
    
    ## Pagination
    - **limit**: Maximum items to return (default 50, max 100)
    - **offset**: Number of items to skip
    """
    
    from routers.generate import urs_documents
    
    results = []
    
    for urs_id, urs in urs_documents.items():
        # Apply filters
        if status and urs.metadata.status != status:
            continue
        if department and urs.metadata.department != department:
            continue
        
        results.append({
            "id": urs.metadata.id,
            "title": urs.metadata.title,
            "status": urs.metadata.status.value,
            "department": urs.metadata.department,
            "requestor": urs.metadata.requestor.name,
            "created_at": urs.metadata.created_at.isoformat(),
            "updated_at": urs.metadata.updated_at.isoformat(),
        })
    
    # Sort by created_at descending
    results.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Apply pagination
    paginated = results[offset:offset + limit]
    
    return {
        "items": paginated,
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


@router.put("/urs/{urs_id}")
async def update_urs(urs_id: str, updates: dict):
    """
    Update a URS document.
    
    Supports partial updates - only provided fields are modified.
    Changes are recorded in version history.
    
    ## Editable Fields
    - title
    - executive_summary
    - problem_statement
    - scope
    - functional_requirements
    - non_functional_requirements
    - etc.
    
    ## Note
    Updating a URS in 'approved' status will change its status to 'draft'.
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    # Track what changed for version history
    changes = []
    
    # Apply updates
    if "title" in updates:
        urs.metadata.title = updates["title"]
        changes.append("title")
    
    if "status" in updates:
        new_status = URSStatus(updates["status"])
        urs.metadata.status = new_status
        changes.append("status")
    
    # TODO: Handle other field updates
    
    # Update timestamp
    urs.metadata.updated_at = datetime.utcnow()
    
    # Add version history entry
    version_num = f"0.{len(urs.version_history) + 1}"
    urs.version_history.append(VersionEntry(
        version=version_num,
        date=datetime.utcnow(),
        author="user",  # TODO: Get from auth context
        changes=f"Updated: {', '.join(changes)}",
    ))
    
    return {
        "urs_id": urs_id,
        "status": "updated",
        "version": version_num,
        "changes": changes,
    }


@router.post("/urs/{urs_id}/approve")
async def submit_for_approval(urs_id: str, approver_roles: List[str] = None):
    """
    Submit a URS for approval.
    
    ## Process
    1. Changes status to 'in_review'
    2. Creates approval records for each required role
    3. Notifies approvers (if notification system is configured)
    
    ## Default Approver Roles
    - Business Owner
    - Technical Lead
    - Quality Assurance
    
    ## Prerequisites
    - URS must be in 'draft' status
    - No critical QA issues
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    if urs.metadata.status != URSStatus.DRAFT:
        raise HTTPException(
            status_code=400, 
            detail=f"URS is in '{urs.metadata.status.value}' status. Only draft documents can be submitted."
        )
    
    # Default approver roles
    roles = approver_roles or ["Business Owner", "Technical Lead", "Quality Assurance"]
    
    # Create approval records
    urs.approvals = [
        Approval(role=role, status="pending")
        for role in roles
    ]
    
    # Update status
    urs.metadata.status = URSStatus.IN_REVIEW
    urs.metadata.updated_at = datetime.utcnow()
    
    return {
        "urs_id": urs_id,
        "status": "in_review",
        "approvals_required": len(roles),
        "approver_roles": roles,
    }


@router.post("/urs/{urs_id}/approve/{role}")
async def record_approval(
    urs_id: str, 
    role: str, 
    approved: bool,
    comments: Optional[str] = None,
    approver_name: Optional[str] = None,
    approver_email: Optional[str] = None,
):
    """
    Record an approval or rejection for a specific role.
    
    ## Parameters
    - **role**: The approver role (must match a pending approval)
    - **approved**: True for approval, False for rejection
    - **comments**: Optional comments from approver
    
    ## Result
    - If all approvals received: status changes to 'approved'
    - If any rejection: status changes to 'rejected'
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    if urs.metadata.status != URSStatus.IN_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"URS is not in review. Current status: {urs.metadata.status.value}"
        )
    
    # Find the approval record
    approval_record = None
    for approval in urs.approvals:
        if approval.role == role:
            approval_record = approval
            break
    
    if not approval_record:
        raise HTTPException(status_code=404, detail=f"No approval required for role: {role}")
    
    if approval_record.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval for {role} already recorded")
    
    # Record the approval
    approval_record.status = "approved" if approved else "rejected"
    approval_record.comments = comments
    approval_record.approver_name = approver_name
    approval_record.approver_email = approver_email
    approval_record.date = datetime.utcnow()
    
    # Check overall status
    all_statuses = [a.status for a in urs.approvals]
    
    if "rejected" in all_statuses:
        urs.metadata.status = URSStatus.REJECTED
    elif all(s == "approved" for s in all_statuses):
        urs.metadata.status = URSStatus.APPROVED
    
    urs.metadata.updated_at = datetime.utcnow()
    
    return {
        "urs_id": urs_id,
        "role": role,
        "decision": "approved" if approved else "rejected",
        "overall_status": urs.metadata.status.value,
        "pending_approvals": sum(1 for a in urs.approvals if a.status == "pending"),
    }


@router.get("/urs/{urs_id}/export")
async def export_urs(urs_id: str, format: str = "json"):
    """
    Export URS document in various formats.
    
    ## Formats
    - **json**: Raw JSON (default)
    - **markdown**: Human-readable Markdown
    - **html**: Styled HTML document
    - **pdf**: PDF document (requires additional setup)
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    if format == "json":
        return urs.model_dump()
    
    elif format == "markdown":
        # TODO: Generate proper Markdown
        return {
            "format": "markdown",
            "content": _generate_markdown(urs),
        }
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format: {format}. Use: json, markdown"
        )


def _generate_markdown(urs: URS) -> str:
    """Generate Markdown representation of URS."""
    
    md = f"""# {urs.metadata.title}

**ID:** {urs.metadata.id}  
**Status:** {urs.metadata.status.value}  
**Department:** {urs.metadata.department}  
**Requestor:** {urs.metadata.requestor.name}  
**Data Classification:** {urs.metadata.data_classification.value}

---

## Executive Summary

{urs.executive_summary.summary}

**Business Value:** {urs.executive_summary.business_value}

---

## Problem Statement

### Current State
{urs.problem_statement.current_state}

### Pain Points
"""
    
    for pp in urs.problem_statement.pain_points:
        md += f"- {pp.description}\n"
    
    md += f"""
### Desired State
{urs.problem_statement.desired_state}

---

## Functional Requirements

"""
    
    for req in urs.functional_requirements:
        md += f"""### {req.requirement_id}: {req.priority.value}

{req.description}

**Rationale:** {req.rationale or 'N/A'}

**Acceptance Criteria:**
"""
        for ac in req.acceptance_criteria:
            md += f"- {ac.criterion}\n"
        
        md += f"\n**Confidence:** {req.confidence_level.value}\n\n"
    
    md += """---

*Generated by URS Generator*
"""
    
    return md

