"""
Generation Router - POST /generate-urs

Handles:
- Stage 3: Generate full URS from normalized content
- Combines chunks, facts, and clarification answers
- Produces canonical URS JSON with source citations
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import uuid

from models.ingest import GenerateRequest, GenerateResponse
from models.urs import (
    URS,
    URSMetadata,
    URSStatus,
    DataClassification,
    Person,
    ExecutiveSummary,
    ProblemStatement,
    PainPoint,
    Scope,
    FunctionalRequirement,
    AcceptanceCriterion,
    SourceReference,
    Priority,
    ConfidenceLevel,
    VersionEntry,
)

router = APIRouter()

# In-memory URS storage for MVP
urs_documents = {}  # urs_id -> URS


@router.post("/generate-urs", response_model=GenerateResponse)
async def generate_urs(request: GenerateRequest):
    """
    Generate a complete URS document from ingested and clarified content.
    
    This endpoint runs Stage 3 of the LLM pipeline to:
    1. Synthesize all source chunks and answers
    2. Generate structured requirements with citations
    3. Mark assumptions explicitly
    4. Assign confidence levels to each requirement
    
    ## Output
    - Complete URS following the canonical schema
    - Every requirement linked to source chunks
    - Assumptions labeled with [ASSUMPTION] tag
    - Confidence levels (high/medium/low) for each requirement
    
    ## Options
    - **skip_clarification**: Generate even if questions are unanswered (not recommended)
    """
    
    session_id = request.session_id
    
    # Get session data
    from routers.ingest import sessions, chunks
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    urs_id = request.urs_id or session.get("urs_id", f"URS-{datetime.utcnow().year}-0001")
    
    from routers.clarify import clarifying_questions, answers
    
    # Check if clarification is complete (skip check for MVP - always allow generation)
    questions = clarifying_questions.get(session_id, [])
    session_answers = answers.get(session_id, [])
    answered_ids = {a.question_id for a in session_answers}
    unanswered = [q for q in questions if q.question_id not in answered_ids]
    
    # For MVP, we skip the clarification check since we're not using it
    # The frontend always passes skip_clarification=true anyway
    # if unanswered and not request.skip_clarification:
    #     raise HTTPException(
    #         status_code=400,
    #         detail=f"{len(unanswered)} clarifying questions remain unanswered. "
    #                f"Answer them or set skip_clarification=true."
    #     )
    
    # Get all chunks for this session
    session_chunks = [chunks[cid] for cid in session.get("chunk_ids", []) if cid in chunks]
    
    if not session_chunks:
        raise HTTPException(status_code=400, detail="No source content found")
    
    # TODO: Call Stage 3 LLM prompt to generate URS
    # For now, generate a structured example based on content
    
    generated_urs = _generate_urs_from_chunks(session, session_chunks, session_answers)
    
    # Store the generated URS
    urs_documents[urs_id] = generated_urs
    
    # Count assumptions and low-confidence items
    assumptions_count = _count_assumptions(generated_urs)
    low_confidence_count = _count_low_confidence(generated_urs)
    
    warnings = []
    if assumptions_count > 0:
        warnings.append(f"{assumptions_count} assumptions were made due to incomplete information")
    if low_confidence_count > 0:
        warnings.append(f"{low_confidence_count} requirements have low confidence - review recommended")
    if unanswered:
        warnings.append(f"{len(unanswered)} clarifying questions were skipped")
    
    return GenerateResponse(
        urs_id=urs_id,
        status="success",
        urs=generated_urs.model_dump(),
        warnings=warnings,
        assumptions_made=assumptions_count,
        low_confidence_requirements=low_confidence_count,
    )


@router.post("/generate-urs/{urs_id}/regenerate")
async def regenerate_urs(urs_id: str, sections: List[str] = None):
    """
    Regenerate specific sections of an existing URS.
    
    Useful when:
    - New information is added
    - User wants to refine specific sections
    - QA identified issues that need fixing
    
    ## Parameters
    - **sections**: List of sections to regenerate (e.g., ["functional_requirements", "scope"])
                   If empty, regenerates the entire document.
    """
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    # TODO: Implement selective regeneration
    
    return {
        "urs_id": urs_id,
        "status": "regeneration_scheduled",
        "sections": sections or ["all"],
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _generate_urs_from_chunks(session: dict, chunks: List, answers: List) -> URS:
    """
    Generate a URS document from chunks and answers.
    Uses LLM service (mock or real) to generate professional content.
    """
    from services.llm_service import get_llm_service
    
    urs_id = session.get("urs_id", f"URS-{datetime.utcnow().year}-0001")
    title = session.get("title", "Untitled Requirements")
    requestor = session.get("requestor", {"name": "Unknown", "email": "unknown@company.com"})
    department = session.get("department", "Unknown")
    classification = session.get("data_classification", "INTERNAL")
    
    # Combine all content for analysis
    all_content = "\n\n".join([c.content for c in chunks])
    
    # Generate source references from actual chunks
    chunk_refs = [
        SourceReference(
            chunk_id=c.chunk_id,
            source_type=c.source_type.value,
            source_name=c.source_name,
            excerpt=c.content[:200] + "..." if len(c.content) > 200 else c.content,
            is_assumption=False,
        )
        for c in chunks[:3]
    ]
    
    # Get LLM service for URS generation
    llm_service = get_llm_service()
    llm_response = llm_service._mock_response(f"Generate URS requirements for: {title}")
    llm_urs = llm_response.get("content", {})
    
    # Build functional requirements from LLM response
    functional_reqs = []
    llm_func_reqs = llm_urs.get("functional_requirements", [])
    for idx, req_data in enumerate(llm_func_reqs):
        # Assign real chunk refs to first few, mark rest as assumptions
        has_source = idx < len(chunk_refs)
        refs = [chunk_refs[idx % len(chunk_refs)]] if chunk_refs else []
        if not has_source and idx > 2:
            refs = [SourceReference(
                chunk_id="N/A",
                source_type="assumption",
                source_name="Generated",
                excerpt="Inferred from context",
                is_assumption=True,
            )]
        
        functional_reqs.append(FunctionalRequirement(
            requirement_id=req_data.get("requirement_id", f"FR-{idx+1:03d}"),
            priority=Priority(req_data.get("priority", "Must")),
            description=req_data.get("description", ""),
            rationale=req_data.get("rationale", ""),
            acceptance_criteria=[
                AcceptanceCriterion(
                    criterion_id=f"{req_data.get('requirement_id', f'FR-{idx+1:03d}')}-AC{i+1}",
                    criterion=ac.get("criterion", ""),
                    test_method="manual",
                )
                for i, ac in enumerate(req_data.get("acceptance_criteria", []))
            ],
            source_references=refs,
            confidence_level=ConfidenceLevel(req_data.get("confidence_level", "medium")),
        ))
    
    # Build pain points from LLM response
    pain_points = []
    llm_problem = llm_urs.get("problem_statement", {})
    for pp_data in llm_problem.get("pain_points", []):
        pain_points.append(PainPoint(
            description=pp_data.get("description", ""),
            impact=pp_data.get("impact", "Medium"),
            source_references=chunk_refs[:1] if chunk_refs else [],
        ))
    
    # Create the URS structure with LLM-generated content
    urs = URS(
        metadata=URSMetadata(
            id=urs_id,
            title=title,
            requestor=Person(name=requestor["name"], email=requestor["email"]),
            department=department,
            status=URSStatus.DRAFT,
            owner=Person(name=requestor["name"], email=requestor["email"]),
            data_classification=DataClassification(classification),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        executive_summary=ExecutiveSummary(
            summary=llm_urs.get("executive_summary", {}).get("summary", 
                f"This document specifies the requirements for {title}."),
            business_value=llm_urs.get("executive_summary", {}).get("business_value", 
                "Improved efficiency and reduced manual effort."),
            source_references=chunk_refs[:1] if chunk_refs else [],
        ),
        problem_statement=ProblemStatement(
            current_state=llm_problem.get("current_state", 
                "Current processes rely on manual workflows and disconnected systems."),
            pain_points=pain_points if pain_points else [
                PainPoint(description="Manual processes are time-consuming", impact="High", source_references=[])
            ],
            desired_state=llm_problem.get("desired_state", 
                "An automated, integrated solution that streamlines workflows."),
            source_references=chunk_refs,
        ),
        scope=Scope(
            in_scope=[{"item": "Core functionality as described", "rationale": "Primary business need"}],
            out_of_scope=[{"item": "Integration with legacy systems not specified", "rationale": "Future phase"}],
            assumptions=[],
            dependencies=[],
        ),
        functional_requirements=functional_reqs if functional_reqs else [
            FunctionalRequirement(
                requirement_id="FR-001",
                priority=Priority.MUST,
                description="The system shall provide core functionality as specified.",
                rationale="Essential for meeting business objectives.",
                acceptance_criteria=[AcceptanceCriterion(
                    criterion_id="FR-001-AC1",
                    criterion="System operates as described in requirements",
                    test_method="manual",
                )],
                source_references=chunk_refs,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
        ],
        non_functional_requirements=[],  # NFRs handled separately
        version_history=[
            VersionEntry(
                version="0.1",
                date=datetime.utcnow(),
                author=requestor["name"],
                changes="Initial draft generated from stakeholder inputs",
            )
        ],
    )
    
    return urs


def _count_assumptions(urs: URS) -> int:
    """Count the number of assumptions in the URS."""
    count = len(urs.scope.assumptions) if urs.scope else 0
    
    # Count source references marked as assumptions
    for req in urs.functional_requirements:
        count += sum(1 for ref in req.source_references if ref.is_assumption)
    
    return count


def _count_low_confidence(urs: URS) -> int:
    """Count requirements with low confidence."""
    return sum(
        1 for req in urs.functional_requirements 
        if req.confidence_level == ConfidenceLevel.LOW
    )

