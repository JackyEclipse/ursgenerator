"""
Stage 4: QA Pass on Generated URS

Purpose:
- Validate the generated URS for quality
- Flag vague or ambiguous language
- Check acceptance criteria testability
- Identify missing information
- Verify source traceability
- Score overall quality

Output:
- List of issues with severity and location
- Quality scores by category
- Recommendations for improvement
"""

STAGE4_SYSTEM_PROMPT = """You are a quality assurance AI assistant for requirements documents. Your task is to review a User Requirements Specification (URS) and identify issues that would make it unsuitable for engineering handoff.

## CRITICAL RULES

1. **BE THOROUGH**: Check every requirement, criterion, and section systematically.

2. **BE SPECIFIC**: Identify the exact location of each issue (JSON path).

3. **BE ACTIONABLE**: Provide concrete suggestions for fixing issues.

4. **PRIORITIZE CORRECTLY**: Critical issues block approval. Warnings should be addressed. Suggestions are nice-to-have.

5. **CHECK TRACEABILITY**: Verify every requirement has source references.

## ISSUE CATEGORIES

### vague_language
Terms that make requirements untestable:
- "fast", "quick", "slow" (without metrics)
- "user-friendly", "intuitive", "easy" (subjective)
- "appropriate", "reasonable", "adequate" (undefined)
- "etc.", "and so on", "as needed" (incomplete)
- "should", "may", "might" (weak commitment)

### missing_acceptance_criteria
- Requirements with no acceptance criteria
- Requirements with criteria that don't cover the full requirement
- Criteria that are really just restatements of the requirement

### untestable
Criteria that cannot be objectively verified:
- No measurable threshold
- Subjective assessment required
- Depends on undefined terms

### assumption
- Unvalidated assumptions that could affect delivery
- Inferences made without stakeholder confirmation
- Default values used without approval

### contradiction
- Conflicting requirements
- Inconsistent terminology
- Scope conflicts

### missing_source
- Requirements without source_references
- Broken or invalid chunk_id references
- Claims not supported by cited sources

### incomplete
- Sections with placeholder text
- Missing required fields
- Truncated content

## SEVERITY LEVELS

- **critical**: Blocks approval. Must be fixed before engineering handoff.
- **warning**: Should be addressed. May cause issues if ignored.
- **suggestion**: Optional improvement. Nice to have.

## QUALITY SCORING

Score each dimension 0-100:

1. **Completeness**: Are all sections filled? All requirements have criteria?
2. **Clarity**: Is language specific and unambiguous?
3. **Testability**: Can all requirements be verified?
4. **Traceability**: Are all requirements linked to sources?

## OUTPUT FORMAT

{
  "issues": [
    {
      "issue_id": "QA-001",
      "severity": "critical | warning | suggestion",
      "category": "vague_language | missing_acceptance_criteria | untestable | assumption | contradiction | missing_source | incomplete",
      "location": "JSON path, e.g., functional_requirements[0].description",
      "description": "What the issue is",
      "excerpt": "The problematic text",
      "suggestion": "How to fix it",
      "affected_requirement_id": "FR-XXX (if applicable)"
    }
  ],
  "scores": {
    "completeness": 0-100,
    "clarity": 0-100,
    "testability": 0-100,
    "traceability": 0-100,
    "overall": 0-100
  },
  "summary": {
    "total_issues": 0,
    "critical_count": 0,
    "warning_count": 0,
    "suggestion_count": 0,
    "ready_for_approval": true/false,
    "blocking_issues": ["list of critical issue IDs"]
  },
  "recommendations": [
    "Top recommendations for improving this URS"
  ]
}
"""

STAGE4_USER_TEMPLATE = """## URS DOCUMENT TO REVIEW

{urs_json}

## SOURCE CHUNKS AVAILABLE

The following source chunk IDs are valid references:
{valid_chunk_ids}

## REVIEW CHECKLIST

Please check:

### Metadata
- [ ] All required fields present
- [ ] Valid URS ID format
- [ ] Appropriate data classification

### Executive Summary
- [ ] Concise and informative
- [ ] Business value clearly stated
- [ ] No vague language

### Problem Statement
- [ ] Current state described
- [ ] Pain points specific and measurable
- [ ] Desired state clear

### Scope
- [ ] In-scope items listed
- [ ] Out-of-scope items listed
- [ ] Assumptions documented
- [ ] Dependencies identified

### Functional Requirements
For each requirement:
- [ ] Follows "The system shall..." format
- [ ] Has at least one acceptance criterion
- [ ] Criteria are testable
- [ ] Has source references
- [ ] Confidence level assigned
- [ ] No vague language

### Non-Functional Requirements
- [ ] Categories appropriate
- [ ] Metrics defined where applicable

### Risks and Open Questions
- [ ] Remaining uncertainties documented
- [ ] Risks have mitigation plans

## TASK

Perform a thorough QA review of this URS and output:
1. All issues found with severity and location
2. Quality scores for each dimension
3. Whether this URS is ready for approval
4. Recommendations for improvement

Be strict but fair. The goal is to ensure this URS can be handed to engineering with confidence.

Respond with valid JSON only."""


def build_stage4_prompt(urs_dict: dict, valid_chunk_ids: list) -> tuple:
    """
    Build the complete Stage 4 prompt.
    
    Args:
        urs_dict: The URS document as a dictionary
        valid_chunk_ids: List of valid source chunk IDs
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    
    user_prompt = STAGE4_USER_TEMPLATE.format(
        urs_json=json.dumps(urs_dict, indent=2, default=str),
        valid_chunk_ids=", ".join(valid_chunk_ids) if valid_chunk_ids else "No source chunks available",
    )
    return STAGE4_SYSTEM_PROMPT, user_prompt


# Expected output schema
STAGE4_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["issues", "scores", "summary"],
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["issue_id", "severity", "category", "location", "description"],
                "properties": {
                    "issue_id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "warning", "suggestion"]},
                    "category": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "excerpt": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "affected_requirement_id": {"type": "string"}
                }
            }
        },
        "scores": {
            "type": "object",
            "properties": {
                "completeness": {"type": "number"},
                "clarity": {"type": "number"},
                "testability": {"type": "number"},
                "traceability": {"type": "number"},
                "overall": {"type": "number"}
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "total_issues": {"type": "integer"},
                "critical_count": {"type": "integer"},
                "warning_count": {"type": "integer"},
                "suggestion_count": {"type": "integer"},
                "ready_for_approval": {"type": "boolean"},
                "blocking_issues": {"type": "array", "items": {"type": "string"}}
            }
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}


# Common vague terms to flag
VAGUE_TERMS = [
    "fast", "quick", "slow", "rapid",
    "easy", "simple", "intuitive", "user-friendly", "seamless",
    "efficient", "effective", "optimal", "best",
    "appropriate", "reasonable", "adequate", "sufficient",
    "flexible", "scalable", "robust", "reliable",
    "modern", "state-of-the-art", "cutting-edge",
    "etc", "and so on", "and more", "as needed",
    "should", "may", "might", "could possibly",
    "good", "better", "improved",
    "various", "multiple", "several", "some",
]

