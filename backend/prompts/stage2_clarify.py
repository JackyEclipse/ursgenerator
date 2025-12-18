"""
Stage 2: Generate Clarifying Questions

Purpose:
- Analyze normalized facts for gaps and ambiguities
- Identify contradictions between sources
- Generate targeted questions to resolve issues
- Prioritize questions by importance

Output:
- List of clarifying questions with context
- Each question linked to relevant source chunks
- Priority ranking (high/medium/low)
"""

STAGE2_SYSTEM_PROMPT = """You are a requirements analyst AI assistant. Your task is to identify gaps, ambiguities, and contradictions in stakeholder inputs, then generate clarifying questions.

## CRITICAL RULES

1. **TARGETED QUESTIONS**: Each question must address a specific gap or ambiguity. No generic questions.

2. **CITE SOURCES**: Reference the chunk IDs that prompted each question.

3. **PROVIDE CONTEXT**: Explain WHY the question is being asked.

4. **PRIORITIZE**: High-priority questions are blocking; without answers, requirements cannot be properly defined.

5. **NO ASSUMPTIONS IN QUESTIONS**: Don't embed assumptions in your questions. Keep them neutral.

6. **ACTIONABLE**: Questions should be answerable by stakeholders (not technical implementation questions).

## QUESTION CATEGORIES

- **missing_info**: Critical information not provided
- **contradiction**: Conflicting statements found in sources
- **ambiguity**: Multiple valid interpretations possible
- **scope_unclear**: Boundaries of the requirement not defined
- **priority_unclear**: Relative importance not stated
- **acceptance_unclear**: Success criteria not defined

## PRIORITY LEVELS

- **high**: Blocks requirement definition. Cannot proceed without answer.
- **medium**: Important for complete requirements but can make assumptions if needed.
- **low**: Nice to have clarity, but can proceed with reasonable defaults.

## OUTPUT FORMAT

Respond with valid JSON:

{
  "questions": [
    {
      "question_id": "string (e.g., Q-001)",
      "question": "string (the question to ask)",
      "context": "string (why this question is being asked)",
      "related_chunk_ids": ["array of source chunk IDs"],
      "related_fact_ids": ["array of fact IDs from Stage 1"],
      "category": "missing_info | contradiction | ambiguity | scope_unclear | priority_unclear | acceptance_unclear",
      "priority": "high | medium | low",
      "suggested_options": ["optional array of multiple-choice options if applicable"],
      "what_happens_if_unanswered": "string (consequence of not getting an answer)"
    }
  ],
  "contradictions_found": [
    {
      "description": "string",
      "chunk_ids": ["array of conflicting chunk IDs"],
      "resolution_question_id": "string (ID of question that addresses this)"
    }
  ],
  "information_completeness": {
    "score": 0.0-1.0,
    "missing_critical": ["array of critical missing items"],
    "missing_optional": ["array of optional missing items"]
  }
}

## GOOD QUESTION EXAMPLES

✓ "Who are the primary users of this system? Please describe their roles and typical daily activities." (specific, actionable)

✓ "You mentioned needing 'fast response times' - what specific threshold is acceptable? (e.g., <2 seconds, <500ms)" (clarifying vague term)

✓ "The meeting notes say the deadline is Q2, but the email mentions 'by March'. Which is correct?" (resolving contradiction)

## BAD QUESTION EXAMPLES

✗ "Can you tell me more about the requirements?" (too vague)

✗ "What technology stack should we use?" (implementation detail, not stakeholder question)

✗ "Shouldn't you also want feature X?" (leading question with embedded assumption)
"""

STAGE2_USER_TEMPLATE = """## EXTRACTED FACTS FROM STAGE 1

{facts}

## ORIGINAL SOURCE CHUNKS

{chunks}

## ENTITIES IDENTIFIED

{entities}

## GAPS ALREADY IDENTIFIED

{gaps}

## TASK

1. Analyze the facts and sources for gaps, ambiguities, and contradictions
2. Generate clarifying questions for each issue found
3. Prioritize questions (high/medium/low)
4. Provide context for why each question is needed
5. Suggest answer options where applicable

Focus on questions that:
- Block requirement definition (high priority)
- Resolve conflicting information
- Clarify vague terms
- Define scope boundaries
- Establish success criteria

Respond with valid JSON only."""


def format_facts_for_prompt(facts: list) -> str:
    """Format extracted facts for the prompt."""
    formatted = []
    for fact in facts:
        formatted.append(f"""- [{fact.get('fact_id')}] ({fact.get('fact_type')}) {fact.get('content')}
  Sources: {', '.join(fact.get('source_chunk_ids', []))}
  Confidence: {fact.get('confidence')}""")
    return "\n".join(formatted)


def format_entities_for_prompt(entities: dict) -> str:
    """Format entities for the prompt."""
    lines = []
    for category, items in entities.items():
        if items:
            lines.append(f"- {category.title()}: {', '.join(items)}")
    return "\n".join(lines) if lines else "No entities identified"


def format_gaps_for_prompt(gaps: list) -> str:
    """Format already-identified gaps for the prompt."""
    if not gaps:
        return "No gaps pre-identified"
    
    formatted = []
    for gap in gaps:
        formatted.append(f"- [{gap.get('gap_type')}] {gap.get('description')}")
    return "\n".join(formatted)


def build_stage2_prompt(facts: list, chunks: list, entities: dict, gaps: list) -> tuple:
    """
    Build the complete Stage 2 prompt.
    
    Args:
        facts: List of facts from Stage 1
        chunks: Original source chunks
        entities: Entities dict from Stage 1
        gaps: Gaps identified in Stage 1
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from .stage1_normalize import format_chunks_for_prompt
    
    user_prompt = STAGE2_USER_TEMPLATE.format(
        facts=format_facts_for_prompt(facts),
        chunks=format_chunks_for_prompt(chunks),
        entities=format_entities_for_prompt(entities),
        gaps=format_gaps_for_prompt(gaps),
    )
    return STAGE2_SYSTEM_PROMPT, user_prompt


# Expected output schema
STAGE2_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["questions", "information_completeness"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["question_id", "question", "context", "category", "priority"],
                "properties": {
                    "question_id": {"type": "string"},
                    "question": {"type": "string"},
                    "context": {"type": "string"},
                    "related_chunk_ids": {"type": "array"},
                    "related_fact_ids": {"type": "array"},
                    "category": {"type": "string"},
                    "priority": {"type": "string"},
                    "suggested_options": {"type": "array"},
                    "what_happens_if_unanswered": {"type": "string"}
                }
            }
        },
        "contradictions_found": {"type": "array"},
        "information_completeness": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "missing_critical": {"type": "array"},
                "missing_optional": {"type": "array"}
            }
        }
    }
}

