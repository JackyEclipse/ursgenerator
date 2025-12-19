"""
LLM Service - Handles all interactions with language models.

Supports:
- OpenAI (GPT-4, GPT-4 Turbo)
- Azure OpenAI
- Groq (Llama 3.3, Mixtral - FREE!)

Features:
- Rate limiting
- Token tracking
- Retry with exponential backoff
- Response validation
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import logging
import asyncio

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """
    Centralized LLM interaction service.
    All LLM calls go through this service for consistency and auditability.
    """
    
    def __init__(self):
        self.mode = settings.llm_mode.lower()  # "mock" or "real"
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        
        # Initialize client based on provider (only if real mode)
        self._client = None
        if self.mode == "real":
            self._init_client()
        else:
            logger.info("LLM Service running in MOCK mode")
        
        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def _init_client(self):
        """Initialize the LLM client based on provider configuration."""
        try:
            if self.provider == "groq":
                from openai import AsyncOpenAI
                # Groq uses OpenAI-compatible API
                self._client = AsyncOpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info(f"Initialized Groq client with model: {self.model}")
            elif self.provider == "openai":
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            elif self.provider == "azure":
                from openai import AsyncAzureOpenAI
                self._client = AsyncAzureOpenAI(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_key,
                    api_version="2024-02-01",
                )
            else:
                logger.warning(f"Unknown LLM provider: {self.provider}. Using mock mode.")
                self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            self._client = None
    
    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Make an LLM call with retry logic.
        
        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user message/content
            response_format: Optional JSON schema for structured output
            max_retries: Number of retries on failure
        
        Returns:
            Dict with 'content', 'input_tokens', 'output_tokens', 'model', 'latency_ms'
        """
        
        start_time = datetime.utcnow()
        
        if self.mode == "mock" or self._client is None:
            # Mock mode for development
            logger.info("Using mock LLM response")
            return self._mock_response(user_prompt)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        for attempt in range(max_retries):
            try:
                # For Groq and OpenAI, use self.model directly
                # For Azure, use the deployment name
                model_name = self.model
                if self.provider == "azure":
                    model_name = settings.azure_openai_deployment
                
                kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                
                # Add response format if specified (for JSON mode)
                if response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = await self._client.chat.completions.create(**kwargs)
                
                # Extract response
                content = response.choices[0].message.content
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                
                # Track tokens
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                
                latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                # Parse JSON if expected
                if response_format and content:
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse JSON response")
                
                return {
                    "content": content,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": self.model,
                    "latency_ms": latency_ms,
                }
                
            except Exception as e:
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
        
        raise Exception("LLM call failed after all retries")
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate a mock response for development/testing."""
        # Detect what type of response is needed based on prompt content
        prompt_lower = prompt.lower()
        
        if "clarifying questions" in prompt_lower or "question" in prompt_lower:
            content = self._mock_clarifying_questions_response()
        elif "urs" in prompt_lower or "requirement" in prompt_lower:
            content = self._mock_urs_response()
        elif "qa" in prompt_lower or "review" in prompt_lower:
            content = self._mock_qa_response()
        else:
            content = f"[MOCK RESPONSE] This is a placeholder for: {prompt[:200]}..."
        
        return {
            "content": content,
            "input_tokens": len(prompt.split()),
            "output_tokens": 500,
            "model": f"{self.model} (mock)",
            "latency_ms": 100,
        }
    
    def _mock_clarifying_questions_response(self) -> Dict[str, Any]:
        """Generate mock clarifying questions."""
        return {
            "questions": [
                {
                    "question_id": "q-001",
                    "question": "Who are the primary users of this system?",
                    "context": "Understanding user roles is essential for access control.",
                    "related_chunk_ids": [],
                    "category": "missing_info",
                    "priority": "high",
                    "suggested_options": ["Internal employees", "External customers", "Both"]
                },
                {
                    "question_id": "q-002",
                    "question": "What is the expected timeline for this project?",
                    "context": "Timeline affects scope prioritization.",
                    "related_chunk_ids": [],
                    "category": "missing_info",
                    "priority": "medium"
                },
                {
                    "question_id": "q-003",
                    "question": "Are there any existing systems this needs to integrate with?",
                    "context": "Integration requirements affect architecture.",
                    "related_chunk_ids": [],
                    "category": "missing_info",
                    "priority": "high"
                },
                {
                    "question_id": "q-004",
                    "question": "What are the performance requirements?",
                    "context": "Performance impacts technical decisions.",
                    "related_chunk_ids": [],
                    "category": "missing_info",
                    "priority": "medium"
                },
                {
                    "question_id": "q-005",
                    "question": "Are there compliance or regulatory requirements?",
                    "context": "Compliance affects design significantly.",
                    "related_chunk_ids": [],
                    "category": "missing_info",
                    "priority": "medium"
                }
            ]
        }
    
    def _mock_urs_response(self) -> Dict[str, Any]:
        """Generate mock URS document - professional quality for Eclipse Automation."""
        from datetime import datetime
        return {
            "metadata": {
                "id": f"URS-{datetime.utcnow().year}-0001",
                "title": "Process Automation System Requirements",
                "status": "draft",
                "version": "1.0",
                "department": "Digital Transformation",
                "requestor": "Submitted via URS Generator",
                "data_classification": "INTERNAL",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            "executive_summary": {
                "summary": "Teams currently track work using spreadsheets and email. This leads to lost information and wasted time on manual reporting. A unified system would automate status updates and provide real-time visibility.",
                "business_value": "Automate the manual tracking and reporting process. Reduce time spent compiling reports by 40%.",
                "scope": "Core tracking workflow, user interface, integrations, and reporting."
            },
            "problem_statement": {
                "current_state": "Teams currently track work using spreadsheets, whiteboards, and email. This leads to lost information, duplicated effort, and difficulty seeing the full picture. Staff waste time on manual updates instead of productive work.",
                "pain_points": [
                    {"description": "Manual data entry between systems is time-consuming and error-prone", "impact": "High", "frequency": "Daily"},
                    {"description": "No single source of truth - data exists in multiple spreadsheets and systems", "impact": "High", "frequency": "Ongoing"},
                    {"description": "Lack of real-time visibility into process status and bottlenecks", "impact": "Medium", "frequency": "Daily"},
                    {"description": "Difficult to generate reports and track KPIs without manual compilation", "impact": "Medium", "frequency": "Weekly"},
                    {"description": "Knowledge transfer is difficult when key personnel are unavailable", "impact": "Medium", "frequency": "As needed"}
                ],
                "desired_state": "A single system where users can see status at a glance, get automatic alerts, and pull reports without manual work."
            },
            "functional_requirements": [
                {
                    "requirement_id": "FR-001",
                    "priority": "Must",
                    "description": "The system shall provide a web-based interface accessible from standard browsers (Chrome, Edge, Firefox) without requiring additional software installation.",
                    "rationale": "Ensures broad accessibility across the organization without IT deployment overhead.",
                    "acceptance_criteria": [
                        {"criterion": "Application loads successfully in Chrome 120+, Edge 120+, and Firefox 120+"},
                        {"criterion": "All core functionality is accessible via mouse and keyboard navigation"},
                        {"criterion": "Interface renders correctly on screens 1280px wide and larger"}
                    ],
                    "source_references": [{"chunk_id": "C-001", "is_assumption": False}],
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "FR-002",
                    "priority": "Must",
                    "description": "The system shall integrate with the existing ERP system via API to automatically retrieve and update relevant records.",
                    "rationale": "Eliminates duplicate data entry and ensures single source of truth.",
                    "acceptance_criteria": [
                        {"criterion": "System successfully connects to ERP API using provided credentials"},
                        {"criterion": "Data synchronization occurs within 5 minutes of source update"},
                        {"criterion": "Failed API calls are logged and retry automatically up to 3 times"}
                    ],
                    "source_references": [{"chunk_id": "C-002", "is_assumption": False}],
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "FR-003",
                    "priority": "Must",
                    "description": "The system shall provide role-based access control with at least three permission levels: Admin, Editor, and Viewer.",
                    "rationale": "Ensures appropriate access controls and data security.",
                    "acceptance_criteria": [
                        {"criterion": "Admins can manage users, configure system settings, and access all data"},
                        {"criterion": "Editors can create, modify, and submit records within their assigned scope"},
                        {"criterion": "Viewers can only view records and generate reports, not modify data"}
                    ],
                    "source_references": [{"chunk_id": "C-001", "is_assumption": True}],
                    "confidence_level": "medium"
                },
                {
                    "requirement_id": "FR-004",
                    "priority": "Must",
                    "description": "The system shall automatically generate notifications when tasks require user action or when defined thresholds are exceeded.",
                    "rationale": "Proactive notifications prevent delays and ensure timely processing.",
                    "acceptance_criteria": [
                        {"criterion": "Email notifications are sent within 1 minute of trigger event"},
                        {"criterion": "Users can configure their notification preferences"},
                        {"criterion": "System provides in-app notification center showing recent alerts"}
                    ],
                    "source_references": [{"chunk_id": "C-003", "is_assumption": False}],
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "FR-005",
                    "priority": "Should",
                    "description": "The system shall provide a dashboard displaying key performance indicators (KPIs) including processing time, volume, and error rates.",
                    "rationale": "Real-time visibility enables proactive management and continuous improvement.",
                    "acceptance_criteria": [
                        {"criterion": "Dashboard displays at least 5 configurable KPI widgets"},
                        {"criterion": "Data refreshes automatically every 5 minutes or on-demand"},
                        {"criterion": "Users can filter dashboard by date range and category"}
                    ],
                    "source_references": [{"chunk_id": "C-004", "is_assumption": False}],
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "FR-006",
                    "priority": "Should",
                    "description": "The system shall maintain a complete audit trail of all data changes including timestamp, user, and before/after values.",
                    "rationale": "Audit trails support compliance requirements and troubleshooting.",
                    "acceptance_criteria": [
                        {"criterion": "All create, update, and delete operations are logged"},
                        {"criterion": "Audit logs cannot be modified or deleted by regular users"},
                        {"criterion": "Audit logs can be exported to CSV for review"}
                    ],
                    "source_references": [{"chunk_id": "C-002", "is_assumption": False}],
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "FR-007",
                    "priority": "Could",
                    "description": "The system shall support bulk import of historical data via CSV file upload.",
                    "rationale": "Enables migration of existing data and periodic batch updates.",
                    "acceptance_criteria": [
                        {"criterion": "System accepts CSV files up to 10MB in size"},
                        {"criterion": "Import validates data before committing changes"},
                        {"criterion": "Import results summary shows success/failure counts"}
                    ],
                    "source_references": [{"chunk_id": "N/A", "is_assumption": True}],
                    "confidence_level": "low"
                }
            ],
            "non_functional_requirements": [
                {
                    "requirement_id": "NFR-001",
                    "category": "Performance",
                    "description": "The system shall load any page within 3 seconds under normal operating conditions (up to 50 concurrent users).",
                    "priority": "Must",
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "NFR-002",
                    "category": "Availability",
                    "description": "The system shall be available 99.5% of the time during business hours (6 AM - 8 PM EST, Monday-Friday).",
                    "priority": "Must",
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "NFR-003",
                    "category": "Security",
                    "description": "The system shall encrypt all data in transit using TLS 1.2 or higher and at rest using AES-256.",
                    "priority": "Must",
                    "confidence_level": "high"
                },
                {
                    "requirement_id": "NFR-004",
                    "category": "Usability",
                    "description": "New users shall be able to complete core tasks without training after reviewing built-in help documentation.",
                    "priority": "Should",
                    "confidence_level": "medium"
                },
                {
                    "requirement_id": "NFR-005",
                    "category": "Scalability",
                    "description": "[ASSUMPTION] The system shall support up to 200 registered users and 10,000 records without performance degradation.",
                    "priority": "Should",
                    "confidence_level": "low"
                }
            ],
            "risks_and_open_questions": {
                "risks": [
                    {"risk_id": "R-001", "description": "ERP API availability or rate limits may impact real-time sync", "likelihood": "Medium", "impact": "High", "mitigation": "Implement queuing and retry logic; establish SLA with ERP team"},
                    {"risk_id": "R-002", "description": "User adoption may be slow without adequate change management", "likelihood": "Medium", "impact": "Medium", "mitigation": "Plan for training sessions and designate super-users"}
                ],
                "open_questions": [
                    {"question_id": "OQ-001", "question": "What is the data retention policy for audit logs?", "owner": "Compliance Team"},
                    {"question_id": "OQ-002", "question": "Are there specific regulatory requirements that apply to this data?", "owner": "Legal/Compliance"}
                ],
                "assumptions": [
                    {"assumption_id": "A-001", "description": "ERP system has a documented and stable API available for integration"},
                    {"assumption_id": "A-002", "description": "Users have access to modern web browsers on their workstations"},
                    {"assumption_id": "A-003", "description": "IT will provide necessary infrastructure for hosting the application"}
                ]
            }
        }
    
    def _mock_qa_response(self) -> Dict[str, Any]:
        """Generate mock QA review response."""
        return {
            "overall_score": 75.0,
            "scores": {
                "completeness": 80.0,
                "clarity": 75.0,
                "testability": 70.0,
                "traceability": 75.0,
                "overall": 75.0
            },
            "issues": [
                {
                    "issue_id": "qa-001",
                    "severity": "warning",
                    "category": "vague_language",
                    "location": "functional_requirements[2].description",
                    "description": "Requirement uses vague term 'efficiently'",
                    "suggestion": "Define specific performance metrics"
                },
                {
                    "issue_id": "qa-002",
                    "severity": "suggestion",
                    "category": "untestable",
                    "location": "non_functional_requirements[0].description",
                    "description": "Consider specifying load conditions for response time",
                    "suggestion": "Add context like 'under normal load (100 concurrent users)'"
                }
            ],
            "ready_for_approval": True,
            "blocking_issues_count": 0
        }
    
    async def call_with_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Make an LLM call expecting structured JSON output.
        
        The system prompt should instruct the LLM to output valid JSON
        matching the provided schema.
        """
        
        enhanced_system = f"""{system_prompt}

IMPORTANT: Your response MUST be valid JSON matching this schema:
{json.dumps(output_schema, indent=2)}

Do not include any text before or after the JSON object."""
        
        return await self.call(
            system_prompt=enhanced_system,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )
    
    def get_token_stats(self) -> Dict[str, int]:
        """Get cumulative token usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

