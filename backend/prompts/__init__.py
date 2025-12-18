"""
LLM Prompt Templates for URS Generator Pipeline.

Each stage has specific prompts designed for:
- Deterministic, structured outputs
- Explicit prohibition of hallucination
- Required citation of sources
- Clear assumption labeling
"""

from .stage1_normalize import STAGE1_SYSTEM_PROMPT, STAGE1_USER_TEMPLATE
from .stage2_clarify import STAGE2_SYSTEM_PROMPT, STAGE2_USER_TEMPLATE
from .stage3_generate import STAGE3_SYSTEM_PROMPT, STAGE3_USER_TEMPLATE
from .stage4_qa import STAGE4_SYSTEM_PROMPT, STAGE4_USER_TEMPLATE

__all__ = [
    "STAGE1_SYSTEM_PROMPT",
    "STAGE1_USER_TEMPLATE",
    "STAGE2_SYSTEM_PROMPT",
    "STAGE2_USER_TEMPLATE",
    "STAGE3_SYSTEM_PROMPT",
    "STAGE3_USER_TEMPLATE",
    "STAGE4_SYSTEM_PROMPT",
    "STAGE4_USER_TEMPLATE",
]

