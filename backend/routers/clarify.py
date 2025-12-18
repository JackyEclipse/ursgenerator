"""
Clarification Router - POST /clarify

Handles:
- Stage 2: Generate clarifying questions
- Submit answers to questions
- Re-run clarification after answers
"""

from fastapi import APIRouter, HTTPException
from typing import List
import uuid

from models.ingest import (
    ClarifyRequest,
    ClarifyResponse,
    ClarifyingQuestion,
    AnswersRequest,
    AnswerSubmission,
)

router = APIRouter()

# In-memory storage for MVP
clarifying_questions = {}  # session_id -> list of questions
answers = {}  # session_id -> list of answers


@router.post("/clarify", response_model=ClarifyResponse)
async def get_clarifying_questions(request: ClarifyRequest):
    """
    Generate clarifying questions based on ingested content.
    
    This endpoint runs Stage 2 of the LLM pipeline to:
    1. Analyze normalized chunks for gaps and ambiguities
    2. Generate targeted questions with context
    3. Prioritize questions by importance
    
    ## Question Categories
    - **missing_info**: Critical information not provided
    - **contradiction**: Conflicting statements found
    - **ambiguity**: Multiple interpretations possible
    - **scope_unclear**: Boundaries not well defined
    
    Call this after /ingest to see what clarifications are needed.
    """
    
    session_id = request.session_id
    
    # Check session exists
    from routers.ingest import sessions, chunks
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    # Get chunks for this session
    session_chunks = [chunks[cid] for cid in session.get("chunk_ids", []) if cid in chunks]
    
    if not session_chunks:
        raise HTTPException(status_code=400, detail="No chunks found for session")
    
    # TODO: Call Stage 2 LLM prompt to generate questions
    # For now, return example questions based on content analysis
    
    generated_questions = _generate_mock_questions(session_chunks, session)
    
    # Store questions
    clarifying_questions[session_id] = generated_questions
    
    # Calculate completeness score
    completeness = _calculate_completeness(session_chunks, generated_questions)
    
    return ClarifyResponse(
        session_id=session_id,
        questions=generated_questions,
        completeness_score=completeness,
    )


@router.post("/clarify/answer")
async def submit_answers(request: AnswersRequest):
    """
    Submit answers to clarifying questions.
    
    Answers are stored and incorporated into the URS generation.
    Each answer creates a new source chunk with the question as context.
    
    ## Answer Format
    - Provide the question_id and your answer
    - Optionally add additional_context for nuance
    - Answers can reference uploaded files by name
    """
    
    session_id = request.session_id
    
    from routers.ingest import sessions, chunks, generate_chunk_id
    from models.ingest import SourceChunk, SourceType
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    source_id = session.get("source_id", session_id)
    
    # Get existing questions
    questions = clarifying_questions.get(session_id, [])
    question_map = {q.question_id: q for q in questions}
    
    # Store answers
    if session_id not in answers:
        answers[session_id] = []
    
    # Create chunks from answers
    chunk_ids = session.get("chunk_ids", [])
    chunk_index = len(chunk_ids)
    
    for answer in request.answers:
        if answer.question_id not in question_map:
            continue  # Skip unknown questions
        
        question = question_map[answer.question_id]
        
        # Create answer chunk with question context
        content = f"Q: {question.question}\nA: {answer.answer}"
        if answer.additional_context:
            content += f"\nContext: {answer.additional_context}"
        
        chunk_id = generate_chunk_id(source_id, chunk_index)
        chunk = SourceChunk(
            chunk_id=chunk_id,
            source_id=source_id,
            source_type=SourceType.USER_INPUT,
            source_name=f"answer_to_{answer.question_id}",
            content=content,
            content_hash=f"ans-{answer.question_id[:8]}",
            data_classification=session.get("data_classification", "INTERNAL"),
        )
        chunks[chunk_id] = chunk
        chunk_ids.append(chunk_id)
        chunk_index += 1
        
        answers[session_id].append(answer)
        
        # Mark question as answered
        question_map[answer.question_id] = None
    
    # Update session
    session["chunk_ids"] = chunk_ids
    
    # Count remaining unanswered questions
    remaining = sum(1 for q in questions if q.question_id in 
                   [a.question_id for a in request.answers] == False)
    
    return {
        "status": "answers_recorded",
        "answers_submitted": len(request.answers),
        "remaining_questions": remaining,
        "ready_to_generate": remaining == 0,
    }


@router.get("/clarify/{session_id}/status")
async def get_clarify_status(session_id: str):
    """
    Get current clarification status for a session.
    
    Returns:
    - Total questions generated
    - Questions answered
    - Remaining questions
    - Completeness score
    """
    
    questions = clarifying_questions.get(session_id, [])
    session_answers = answers.get(session_id, [])
    answered_ids = {a.question_id for a in session_answers}
    
    return {
        "session_id": session_id,
        "total_questions": len(questions),
        "answered": len(session_answers),
        "remaining": len(questions) - len(answered_ids),
        "questions": [
            {
                "question_id": q.question_id,
                "question": q.question,
                "answered": q.question_id in answered_ids,
            }
            for q in questions
        ],
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _generate_mock_questions(chunks: List, session: dict) -> List[ClarifyingQuestion]:
    """
    Generate mock clarifying questions.
    In production, this calls the Stage 2 LLM prompt.
    """
    
    # Analyze content to generate relevant questions
    all_content = " ".join([c.content for c in chunks]).lower()
    
    questions = []
    
    # Check for common missing information
    if "user" not in all_content and "persona" not in all_content:
        questions.append(ClarifyingQuestion(
            question_id=f"q-{uuid.uuid4().hex[:8]}",
            question="Who are the primary users of this system? Please describe their roles and how often they would use it.",
            context="No specific users or personas were mentioned in the provided inputs.",
            related_chunk_ids=[chunks[0].chunk_id] if chunks else [],
            category="missing_info",
            priority="high",
            suggested_options=[
                "Internal employees only",
                "External customers",
                "Both internal and external users",
            ],
        ))
    
    if "deadline" not in all_content and "timeline" not in all_content and "date" not in all_content:
        questions.append(ClarifyingQuestion(
            question_id=f"q-{uuid.uuid4().hex[:8]}",
            question="What is the expected timeline or deadline for this project?",
            context="No timeline information was provided in the inputs.",
            related_chunk_ids=[chunks[0].chunk_id] if chunks else [],
            category="missing_info",
            priority="medium",
        ))
    
    if "budget" not in all_content and "cost" not in all_content:
        questions.append(ClarifyingQuestion(
            question_id=f"q-{uuid.uuid4().hex[:8]}",
            question="Are there any budget constraints or cost considerations for this project?",
            context="No budget information was mentioned.",
            related_chunk_ids=[],
            category="missing_info",
            priority="low",
        ))
    
    # Check for potential scope issues
    if "not" in all_content or "except" in all_content or "exclude" in all_content:
        questions.append(ClarifyingQuestion(
            question_id=f"q-{uuid.uuid4().hex[:8]}",
            question="Can you confirm what is explicitly OUT of scope for this project?",
            context="Some exclusions were mentioned but the full out-of-scope list may not be complete.",
            related_chunk_ids=[c.chunk_id for c in chunks[:2]],
            category="scope_unclear",
            priority="high",
        ))
    
    return questions


def _calculate_completeness(chunks: List, questions: List[ClarifyingQuestion]) -> float:
    """
    Calculate how complete the provided information is.
    1.0 = fully complete, 0.0 = missing critical information
    """
    if not questions:
        return 1.0
    
    # Weight by priority
    weights = {"high": 0.4, "medium": 0.1, "low": 0.05}
    total_weight = sum(weights.get(q.priority, 0.1) for q in questions)
    
    # More content = more complete
    content_length = sum(len(c.content) for c in chunks)
    content_bonus = min(0.2, content_length / 10000)
    
    base_score = max(0.3, 1.0 - total_weight)
    return min(1.0, base_score + content_bonus)

