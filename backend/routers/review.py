"""
Review Router - POST /review

Handles:
- Stage 4: QA pass on generated URS
- Validate completeness, clarity, testability
- Flag issues and generate recommendations
"""

from fastapi import APIRouter, HTTPException
from typing import List
import uuid
import re

from models.ingest import ReviewRequest, ReviewResponse, QAIssue

router = APIRouter()


@router.post("/review", response_model=ReviewResponse)
async def review_urs(request: ReviewRequest):
    """
    Perform QA review on a generated URS document.
    
    This endpoint runs Stage 4 of the LLM pipeline to:
    1. Check for vague or ambiguous language
    2. Verify acceptance criteria are testable
    3. Identify missing information
    4. Flag assumptions that need validation
    5. Check for contradictions
    
    ## Issue Severities
    - **critical**: Blocks approval, must be fixed
    - **warning**: Should be addressed before approval
    - **suggestion**: Nice to have improvements
    
    ## Issue Categories
    - **vague_language**: Terms like "fast", "easy", "user-friendly" without metrics
    - **missing_acceptance_criteria**: Requirements without testable criteria
    - **untestable**: Criteria that cannot be objectively verified
    - **assumption**: Unvalidated assumptions that may affect delivery
    - **contradiction**: Conflicting statements in the document
    """
    
    urs_id = request.urs_id
    
    # Get the URS document
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    urs = urs_documents[urs_id]
    
    # TODO: Call Stage 4 LLM prompt for comprehensive QA
    # For now, run rule-based checks
    
    issues = []
    
    # Check functional requirements
    issues.extend(_check_functional_requirements(urs))
    
    # Check for vague language throughout
    issues.extend(_check_vague_language(urs))
    
    # Check acceptance criteria
    issues.extend(_check_acceptance_criteria(urs))
    
    # Check for assumptions
    issues.extend(_check_assumptions(urs))
    
    # Calculate scores
    scores = _calculate_qa_scores(urs, issues)
    
    # Determine if ready for approval
    blocking_issues = [i for i in issues if i.severity == "critical"]
    ready = len(blocking_issues) == 0
    
    return ReviewResponse(
        urs_id=urs_id,
        overall_score=scores["overall"],
        scores=scores,
        issues=issues,
        ready_for_approval=ready,
        blocking_issues_count=len(blocking_issues),
    )


@router.post("/review/{urs_id}/fix")
async def auto_fix_issues(urs_id: str, issue_ids: List[str] = None):
    """
    Attempt to auto-fix identified issues.
    
    The LLM will try to:
    - Clarify vague language with specific metrics
    - Generate missing acceptance criteria
    - Resolve simple contradictions
    
    Not all issues can be auto-fixed. Some require human input.
    """
    
    from routers.generate import urs_documents
    
    if urs_id not in urs_documents:
        raise HTTPException(status_code=404, detail="URS not found")
    
    # TODO: Implement auto-fix with LLM
    
    return {
        "urs_id": urs_id,
        "status": "auto_fix_scheduled",
        "issues_to_fix": issue_ids or "all",
        "note": "Auto-fix will regenerate affected sections with LLM"
    }


# ============================================================================
# QA Check Functions
# ============================================================================

VAGUE_TERMS = [
    "fast", "quick", "slow", "easy", "simple", "user-friendly",
    "intuitive", "seamless", "efficient", "effective", "modern",
    "appropriate", "reasonable", "adequate", "sufficient", "good",
    "best", "optimal", "flexible", "scalable", "robust", "etc",
    "and so on", "as needed", "if necessary", "when appropriate",
]


def _check_functional_requirements(urs) -> List[QAIssue]:
    """Check functional requirements for issues."""
    issues = []
    
    for i, req in enumerate(urs.functional_requirements):
        location = f"functional_requirements[{i}]"
        
        # Check description format
        if not req.description.startswith("The system shall"):
            issues.append(QAIssue(
                issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                severity="warning",
                category="vague_language",
                location=f"{location}.description",
                description="Requirement description should start with 'The system shall'",
                suggestion=f"Rewrite as: 'The system shall {req.description}'",
                affected_requirement_id=req.requirement_id,
            ))
        
        # Check for source references
        if not req.source_references:
            issues.append(QAIssue(
                issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                severity="warning",
                category="assumption",
                location=f"{location}.source_references",
                description="Requirement has no source references. This may be an assumption.",
                suggestion="Link this requirement to source chunks or mark as [ASSUMPTION]",
                affected_requirement_id=req.requirement_id,
            ))
        
        # Check for low confidence
        if req.confidence_level.value == "low":
            issues.append(QAIssue(
                issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                severity="warning",
                category="assumption",
                location=f"{location}",
                description="Requirement has low confidence level - review with stakeholders",
                affected_requirement_id=req.requirement_id,
            ))
    
    return issues


def _check_vague_language(urs) -> List[QAIssue]:
    """Check for vague language throughout the document."""
    issues = []
    
    # Check executive summary
    for term in VAGUE_TERMS:
        if term in urs.executive_summary.summary.lower():
            issues.append(QAIssue(
                issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                severity="suggestion",
                category="vague_language",
                location="executive_summary.summary",
                description=f"Vague term '{term}' found. Consider using specific, measurable language.",
                suggestion=f"Replace '{term}' with a specific metric or definition.",
            ))
            break  # Only report first vague term per section
    
    # Check each requirement
    for i, req in enumerate(urs.functional_requirements):
        for term in VAGUE_TERMS:
            if term in req.description.lower():
                issues.append(QAIssue(
                    issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                    severity="warning",
                    category="vague_language",
                    location=f"functional_requirements[{i}].description",
                    description=f"Vague term '{term}' makes this requirement untestable.",
                    suggestion=f"Define what '{term}' means with specific metrics.",
                    affected_requirement_id=req.requirement_id,
                ))
                break
    
    return issues


def _check_acceptance_criteria(urs) -> List[QAIssue]:
    """Check that acceptance criteria are testable."""
    issues = []
    
    for i, req in enumerate(urs.functional_requirements):
        location = f"functional_requirements[{i}]"
        
        # Check minimum criteria count
        if len(req.acceptance_criteria) < 1:
            issues.append(QAIssue(
                issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                severity="critical",
                category="missing_acceptance_criteria",
                location=f"{location}.acceptance_criteria",
                description="Requirement has no acceptance criteria. Cannot be tested.",
                suggestion="Add at least one testable acceptance criterion.",
                affected_requirement_id=req.requirement_id,
            ))
            continue
        
        # Check each criterion for testability
        for j, criterion in enumerate(req.acceptance_criteria):
            # Check for vague terms in criteria
            for term in VAGUE_TERMS:
                if term in criterion.criterion.lower():
                    issues.append(QAIssue(
                        issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                        severity="warning",
                        category="untestable",
                        location=f"{location}.acceptance_criteria[{j}]",
                        description=f"Criterion contains vague term '{term}' - not objectively testable.",
                        suggestion="Rewrite with specific, measurable conditions.",
                        affected_requirement_id=req.requirement_id,
                    ))
                    break
            
            # Check for measurable terms (numbers, comparisons)
            has_metric = bool(re.search(r'\d+|less than|more than|within|between|at least', 
                                        criterion.criterion.lower()))
            if not has_metric:
                issues.append(QAIssue(
                    issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                    severity="suggestion",
                    category="untestable",
                    location=f"{location}.acceptance_criteria[{j}]",
                    description="Criterion may benefit from specific metrics or thresholds.",
                    affected_requirement_id=req.requirement_id,
                ))
    
    return issues


def _check_assumptions(urs) -> List[QAIssue]:
    """Check for unvalidated assumptions."""
    issues = []
    
    if urs.scope and urs.scope.assumptions:
        for i, assumption in enumerate(urs.scope.assumptions):
            if not assumption.is_validated:
                issues.append(QAIssue(
                    issue_id=f"qa-{uuid.uuid4().hex[:8]}",
                    severity="warning",
                    category="assumption",
                    location=f"scope.assumptions[{i}]",
                    description=f"Unvalidated assumption: {assumption.assumption}",
                    suggestion="Validate this assumption with stakeholders before proceeding.",
                ))
    
    return issues


def _calculate_qa_scores(urs, issues: List[QAIssue]) -> dict:
    """Calculate quality scores for different aspects."""
    
    # Start with perfect scores
    completeness = 100.0
    clarity = 100.0
    testability = 100.0
    traceability = 100.0
    
    # Deduct points for issues
    for issue in issues:
        penalty = {
            "critical": 15.0,
            "warning": 5.0,
            "suggestion": 1.0,
        }.get(issue.severity, 2.0)
        
        if issue.category == "missing_acceptance_criteria":
            completeness -= penalty
            testability -= penalty
        elif issue.category == "vague_language":
            clarity -= penalty
        elif issue.category == "untestable":
            testability -= penalty
        elif issue.category == "assumption":
            traceability -= penalty
        elif issue.category == "contradiction":
            clarity -= penalty
            completeness -= penalty
    
    # Ensure scores are in valid range
    scores = {
        "completeness": max(0, min(100, completeness)),
        "clarity": max(0, min(100, clarity)),
        "testability": max(0, min(100, testability)),
        "traceability": max(0, min(100, traceability)),
    }
    
    # Overall is weighted average
    scores["overall"] = (
        scores["completeness"] * 0.25 +
        scores["clarity"] * 0.25 +
        scores["testability"] * 0.30 +
        scores["traceability"] * 0.20
    )
    
    return scores

