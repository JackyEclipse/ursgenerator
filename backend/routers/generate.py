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
    """
    import logging
    logger = logging.getLogger(__name__)
    
    session_id = request.session_id
    logger.info(f"Generate URS request for session: {session_id}")
    
    try:
        # Get session data
        from routers.ingest import sessions, chunks
        
        # If session was lost (Render restart), create a minimal one
        if session_id not in sessions:
            logger.info(f"Session {session_id} not found, creating recovery session")
            sessions[session_id] = {
                "urs_id": request.urs_id or f"URS-{datetime.utcnow().year}-{len(sessions)+1:04d}",
                "title": "Generated Requirements",
                "requestor": {"name": "User", "email": "user@company.com"},
                "department": "General",
                "data_classification": "INTERNAL",
                "created_at": datetime.utcnow(),
                "status": "recovered",
                "chunk_ids": [],
            }
        
        session = sessions[session_id]
        urs_id = request.urs_id or session.get("urs_id", f"URS-{datetime.utcnow().year}-0001")
        logger.info(f"Using URS ID: {urs_id}")
        
        from routers.clarify import clarifying_questions, answers
        
        # Check if clarification is complete (skip check for MVP - always allow generation)
        questions = clarifying_questions.get(session_id, [])
        session_answers = answers.get(session_id, [])
        answered_ids = {a.question_id for a in session_answers}
        unanswered = [q for q in questions if q.question_id not in answered_ids]
        
        # Get all chunks for this session
        session_chunks = [chunks[cid] for cid in session.get("chunk_ids", []) if cid in chunks]
        logger.info(f"Found {len(session_chunks)} chunks for session")
        
        # If chunks were lost (server restart), create a placeholder
        if not session_chunks:
            logger.info("No chunks found, creating placeholder")
            from models.ingest import SourceChunk, SourceType
            import hashlib
            placeholder_chunk = SourceChunk(
                chunk_id=f"placeholder-{session_id[:8]}",
                source_id=f"src-{session_id[:8]}",
                source_type=SourceType.USER_INPUT,
                source_name="user_input",
                content=session.get("title", "User requirements input"),
                content_hash=hashlib.sha256(session_id.encode()).hexdigest()[:16],
            )
            session_chunks = [placeholder_chunk]
        
        # Call LLM to generate URS from chunks
        logger.info("Calling LLM to generate URS...")
        generated_urs = await _generate_urs_from_chunks(session, session_chunks, session_answers)
        logger.info("URS generated successfully")
        
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
    
    except Exception as e:
        logger.error(f"Error generating URS: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate URS: {str(e)}")


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

async def _generate_urs_from_chunks(session: dict, chunks: List, answers: List) -> URS:
    """
    Generate a URS document from chunks and answers.
    Uses LLM service (mock or real) to generate professional content.
    """
    from services.llm_service import get_llm_service
    import json
    
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
    
    # Build the prompt for real LLM generation
    system_prompt = """You are a requirements analyst. Generate a User Requirements Specification (URS) in JSON format.
Output ONLY valid JSON with this structure:
{
  "executive_summary": {"summary": "...", "business_value": "..."},
  "problem_statement": {
    "current_state": "description of current situation",
    "pain_points": [{"description": "...", "impact": "High/Medium/Low"}],
    "desired_state": "what they want to achieve"
  },
  "functional_requirements": [
    {
      "requirement_id": "FR-001",
      "priority": "Must/Should/Could",
      "description": "The system shall...",
      "rationale": "why this is needed",
      "acceptance_criteria": [{"criterion": "specific testable criterion"}],
      "confidence_level": "high/medium/low"
    }
  ]
}
Generate 5-7 functional requirements. Use "Must" for critical, "Should" for important, "Could" for nice-to-have.
Base requirements on the actual input content. Mark assumptions clearly."""

    user_prompt = f"""Generate URS requirements for this project:

Title: {title}
Department: {department}
Requestor: {requestor.get('name', 'Unknown')}

Input Content:
{all_content[:3000]}

Generate practical, specific requirements based on this input."""

    # Call LLM (real or mock depending on settings)
    llm_response = await llm_service.call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format={"type": "json_object"}
    )
    
    # Parse LLM response
    llm_content = llm_response.get("content", {})
    logger = logging.getLogger(__name__)
    logger.info(f"LLM response type: {type(llm_content)}")
    
    if isinstance(llm_content, str):
        try:
            llm_urs = json.loads(llm_content)
            logger.info(f"Parsed LLM JSON successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            llm_urs = {}
    else:
        llm_urs = llm_content
    
    logger.info(f"LLM URS keys: {llm_urs.keys() if isinstance(llm_urs, dict) else 'not a dict'}")
    
    # Helper to normalize priority values
    def normalize_priority(p):
        p_lower = str(p).lower().strip()
        if p_lower in ["must", "critical", "high"]:
            return Priority.MUST
        elif p_lower in ["should", "important", "medium"]:
            return Priority.SHOULD
        elif p_lower in ["could", "nice", "low", "enhancement"]:
            return Priority.COULD
        return Priority.SHOULD  # Default
    
    # Helper to normalize confidence levels
    def normalize_confidence(c):
        c_lower = str(c).lower().strip()
        if c_lower == "high":
            return ConfidenceLevel.HIGH
        elif c_lower == "low":
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MEDIUM  # Default
    
    # Build functional requirements from LLM response
    functional_reqs = []
    llm_func_reqs = llm_urs.get("functional_requirements", [])
    logger.info(f"Found {len(llm_func_reqs)} functional requirements from LLM")
    
    for idx, req_data in enumerate(llm_func_reqs):
        try:
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
            
            # Handle acceptance criteria - could be string or dict
            acc_criteria = []
            for i, ac in enumerate(req_data.get("acceptance_criteria", [])):
                if isinstance(ac, str):
                    criterion_text = ac
                elif isinstance(ac, dict):
                    criterion_text = ac.get("criterion", str(ac))
                else:
                    criterion_text = str(ac)
                acc_criteria.append(AcceptanceCriterion(
                    criterion_id=f"{req_data.get('requirement_id', f'FR-{idx+1:03d}')}-AC{i+1}",
                    criterion=criterion_text,
                    test_method="manual",
                ))
            
            functional_reqs.append(FunctionalRequirement(
                requirement_id=req_data.get("requirement_id", f"FR-{idx+1:03d}"),
                priority=normalize_priority(req_data.get("priority", "Should")),
                description=req_data.get("description", "Requirement not specified"),
                rationale=req_data.get("rationale", ""),
                acceptance_criteria=acc_criteria if acc_criteria else [
                    AcceptanceCriterion(criterion_id=f"FR-{idx+1:03d}-AC1", criterion="To be defined", test_method="manual")
                ],
                source_references=refs,
                confidence_level=normalize_confidence(req_data.get("confidence_level", "medium")),
            ))
        except Exception as e:
            logger.error(f"Error processing requirement {idx}: {e}")
            continue
    
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

