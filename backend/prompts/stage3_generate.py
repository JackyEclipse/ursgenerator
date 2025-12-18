"""
Stage 3: Generate Full URS Document

Purpose:
- Synthesize all inputs into a complete URS
- Follow the canonical URS schema exactly
- Cite sources for every requirement
- Mark assumptions explicitly
- Assign confidence levels

Output:
- Complete URS JSON matching the canonical schema
- All requirements with source citations
- Explicit assumption labeling
"""

STAGE3_SYSTEM_PROMPT = """You are a requirements engineer AI assistant. Your task is to generate a complete User Requirements Specification (URS) document from analyzed stakeholder inputs.

## CRITICAL RULES

1. **FOLLOW THE SCHEMA EXACTLY**: Your output must match the canonical URS JSON schema provided.

2. **NO HALLUCINATION**: Every requirement MUST be traceable to source chunks. Do NOT invent requirements.

3. **CITE SOURCES**: Every requirement must have source_references linking to chunk IDs.

4. **MARK ASSUMPTIONS**: If you must make an inference, mark it with is_assumption: true and confidence_level: "low".

5. **USE "SHALL" STATEMENTS**: All functional requirements must follow "The system shall..." format.

6. **TESTABLE CRITERIA**: Every requirement needs at least one testable acceptance criterion.

7. **ASSIGN CONFIDENCE**: 
   - high: Explicitly stated in sources
   - medium: Clearly implied by sources
   - low: Inferred/assumed to fill gaps

## REQUIREMENT WRITING GUIDELINES

### Good Requirements
✓ "The system shall process invoice submissions within 5 seconds of receipt."
✓ "The system shall authenticate users via SSO integration with Azure AD."
✓ "The system shall generate a daily summary report by 6:00 AM local time."

### Bad Requirements
✗ "The system shall be fast." (not measurable)
✗ "The system shall be user-friendly." (subjective)
✗ "The system should probably handle errors." (weak language, vague)

## ACCEPTANCE CRITERIA GUIDELINES

Each criterion should be:
- **Specific**: Clear pass/fail conditions
- **Measurable**: Quantifiable where possible
- **Testable**: Can be verified through testing

Example:
Requirement: "The system shall validate invoice totals before submission."
Acceptance Criteria:
1. Given an invoice with line items summing to $100, when the total field shows $100, then validation passes.
2. Given an invoice with line items summing to $100, when the total field shows $99, then validation fails with error message "Total mismatch".

## PRIORITY DEFINITIONS (MoSCoW)

- **Must**: Critical, non-negotiable. System cannot launch without it.
- **Should**: Important but not critical. Workarounds exist.
- **Could**: Desirable if time/budget permits. Nice to have.

## OUTPUT FORMAT

Your response must be valid JSON matching the canonical URS schema. Key sections:

{
  "metadata": { ... },
  "executive_summary": { ... },
  "problem_statement": { ... },
  "users_and_personas": [ ... ],
  "scope": { ... },
  "functional_requirements": [
    {
      "requirement_id": "FR-001",
      "priority": "Must | Should | Could",
      "description": "The system shall...",
      "rationale": "Why this requirement exists",
      "acceptance_criteria": [
        {
          "criterion_id": "FR-001-AC1",
          "criterion": "Testable criterion",
          "test_method": "manual | automated | review | demo"
        }
      ],
      "source_references": [
        {
          "chunk_id": "CHUNK-XXX",
          "source_name": "...",
          "excerpt": "relevant quote",
          "is_assumption": false
        }
      ],
      "confidence_level": "high | medium | low"
    }
  ],
  "non_functional_requirements": [ ... ],
  "data_requirements": { ... },
  "risks_and_open_questions": { ... },
  "success_metrics": [ ... ],
  "version_history": [ ... ]
}
"""

STAGE3_USER_TEMPLATE = """## PROJECT INFORMATION

Title: {title}
Department: {department}
Requestor: {requestor_name} ({requestor_email})
Data Classification: {data_classification}

## EXTRACTED FACTS

{facts}

## CLARIFICATION ANSWERS

{answers}

## SOURCE CHUNKS

{chunks}

## TASK

Generate a complete URS document that:

1. **Synthesizes** all facts and answers into coherent requirements
2. **Cites** source chunks for every requirement
3. **Marks** assumptions with is_assumption: true
4. **Assigns** confidence levels (high/medium/low)
5. **Follows** "The system shall..." format for functional requirements
6. **Includes** at least one testable acceptance criterion per requirement
7. **Uses** MoSCoW prioritization (Must/Should/Could)

IMPORTANT:
- Do NOT invent requirements not supported by sources
- Mark anything inferred as an assumption
- Use direct quotes from sources where appropriate
- Flag remaining open questions in the risks_and_open_questions section

Respond with valid JSON matching the canonical URS schema."""


def format_answers_for_prompt(answers: list) -> str:
    """Format clarification answers for the prompt."""
    if not answers:
        return "No clarification answers provided"
    
    formatted = []
    for answer in answers:
        formatted.append(f"Q: {answer.get('question', 'Unknown question')}\nA: {answer.get('answer', 'No answer')}")
    return "\n\n".join(formatted)


def build_stage3_prompt(
    title: str,
    department: str,
    requestor_name: str,
    requestor_email: str,
    data_classification: str,
    facts: list,
    answers: list,
    chunks: list,
) -> tuple:
    """
    Build the complete Stage 3 prompt.
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from .stage1_normalize import format_chunks_for_prompt
    from .stage2_clarify import format_facts_for_prompt
    
    user_prompt = STAGE3_USER_TEMPLATE.format(
        title=title,
        department=department,
        requestor_name=requestor_name,
        requestor_email=requestor_email,
        data_classification=data_classification,
        facts=format_facts_for_prompt(facts) if facts else "No facts extracted",
        answers=format_answers_for_prompt(answers),
        chunks=format_chunks_for_prompt(chunks),
    )
    return STAGE3_SYSTEM_PROMPT, user_prompt


# The full canonical URS schema (imported from schemas/urs_schema.json in production)
STAGE3_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "metadata",
        "executive_summary",
        "problem_statement",
        "scope",
        "functional_requirements"
    ]
}

