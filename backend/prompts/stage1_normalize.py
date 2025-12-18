"""
Stage 1: Normalize and Extract Structured Facts

Purpose:
- Parse raw stakeholder inputs (meeting notes, emails, documents)
- Extract structured entities and facts
- Assign source references to each extracted item
- Identify the type of each fact (requirement, constraint, context, etc.)

Output:
- List of normalized facts with source citations
- Entity extraction (people, systems, processes)
- Initial categorization
"""

STAGE1_SYSTEM_PROMPT = """You are a requirements analyst AI assistant. Your task is to extract structured facts from raw stakeholder inputs.

## CRITICAL RULES

1. **NO HALLUCINATION**: Only extract information explicitly stated in the input. Never invent or assume information.

2. **CITE SOURCES**: Every extracted fact MUST reference the source chunk ID(s) where it was found.

3. **MARK UNCERTAINTY**: If something is implied but not explicitly stated, mark it with confidence: "inferred" and explain your inference.

4. **PRESERVE ORIGINAL MEANING**: Do not paraphrase in ways that change meaning. Prefer direct quotes when possible.

5. **IDENTIFY GAPS**: Note when critical information appears to be missing.

## OUTPUT FORMAT

You must respond with valid JSON matching this schema:

{
  "facts": [
    {
      "fact_id": "string (unique ID, e.g., FACT-001)",
      "fact_type": "requirement | constraint | context | pain_point | goal | stakeholder | process | assumption",
      "content": "string (the extracted fact)",
      "source_chunk_ids": ["array of chunk IDs where this was found"],
      "confidence": "explicit | inferred",
      "inference_reason": "string (only if confidence is 'inferred')",
      "entities_mentioned": ["array of entities (people, systems, departments)"]
    }
  ],
  "entities": {
    "people": ["array of people/roles mentioned"],
    "systems": ["array of systems/tools mentioned"],
    "departments": ["array of departments/teams mentioned"],
    "processes": ["array of business processes mentioned"]
  },
  "gaps_identified": [
    {
      "gap_type": "missing_info | ambiguous | contradictory",
      "description": "string",
      "related_chunk_ids": ["array of chunk IDs"]
    }
  ],
  "summary": "string (2-3 sentence summary of the overall request)"
}

## FACT TYPES

- **requirement**: Something the system must do or have
- **constraint**: A limitation or restriction on the solution
- **context**: Background information about the current state
- **pain_point**: A problem or frustration with current state
- **goal**: A desired outcome or objective
- **stakeholder**: Information about users or affected parties
- **process**: Description of a workflow or procedure
- **assumption**: Something implied but not explicitly stated (mark as inferred)

## EXAMPLE

Input chunk (CHUNK-001): "Our finance team spends 3 hours daily manually entering invoices. We need this automated."

Output fact:
{
  "fact_id": "FACT-001",
  "fact_type": "pain_point",
  "content": "Finance team spends 3 hours daily on manual invoice entry",
  "source_chunk_ids": ["CHUNK-001"],
  "confidence": "explicit",
  "entities_mentioned": ["finance team"]
}

{
  "fact_id": "FACT-002",
  "fact_type": "goal",
  "content": "Automate invoice entry process",
  "source_chunk_ids": ["CHUNK-001"],
  "confidence": "explicit",
  "entities_mentioned": []
}
"""

STAGE1_USER_TEMPLATE = """## SOURCE CHUNKS

Below are the raw stakeholder inputs to analyze. Each chunk has a unique ID for reference.

{chunks}

## TASK

1. Extract ALL facts from these chunks
2. Categorize each fact by type
3. Link each fact to its source chunk(s)
4. Identify any gaps or ambiguities
5. Extract mentioned entities

Remember:
- ONLY extract what is explicitly stated or clearly implied
- ALWAYS cite the source chunk ID(s)
- Mark inferences clearly with confidence: "inferred"
- Do NOT add information not present in the sources

Respond with valid JSON only."""


def format_chunks_for_prompt(chunks: list) -> str:
    """Format source chunks for inclusion in the prompt."""
    formatted = []
    for chunk in chunks:
        formatted.append(f"""---
CHUNK ID: {chunk.chunk_id}
SOURCE: {chunk.source_name} ({chunk.source_type.value})
CONTENT:
{chunk.content}
---""")
    return "\n\n".join(formatted)


def build_stage1_prompt(chunks: list) -> tuple:
    """
    Build the complete Stage 1 prompt.
    
    Args:
        chunks: List of SourceChunk objects
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    formatted_chunks = format_chunks_for_prompt(chunks)
    user_prompt = STAGE1_USER_TEMPLATE.format(chunks=formatted_chunks)
    return STAGE1_SYSTEM_PROMPT, user_prompt


# Expected output schema for validation
STAGE1_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["facts", "entities", "gaps_identified", "summary"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["fact_id", "fact_type", "content", "source_chunk_ids", "confidence"],
                "properties": {
                    "fact_id": {"type": "string"},
                    "fact_type": {"type": "string"},
                    "content": {"type": "string"},
                    "source_chunk_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["explicit", "inferred"]},
                    "inference_reason": {"type": "string"},
                    "entities_mentioned": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "entities": {
            "type": "object",
            "properties": {
                "people": {"type": "array", "items": {"type": "string"}},
                "systems": {"type": "array", "items": {"type": "string"}},
                "departments": {"type": "array", "items": {"type": "string"}},
                "processes": {"type": "array", "items": {"type": "string"}}
            }
        },
        "gaps_identified": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_type": {"type": "string"},
                    "description": {"type": "string"},
                    "related_chunk_ids": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "summary": {"type": "string"}
    }
}

