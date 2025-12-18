"""
Audit Logger Service - Immutable audit trail for compliance.

All significant actions are logged:
- User actions (create, update, view, approve)
- LLM calls (inputs, outputs, tokens, latency)
- Data access (especially for CONFIDENTIAL data)
"""

from typing import Optional, Dict, Any
from datetime import datetime
import json
import os
import uuid
from pathlib import Path
import logging

from models.audit import AuditLogEntry, AuditAction
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuditLogger:
    """
    Immutable audit logging service.
    
    MVP: Writes to JSON files.
    Production: Should integrate with enterprise logging (ELK, Splunk, etc.)
    """
    
    def __init__(self, log_path: str = None):
        self.log_path = Path(log_path or settings.audit_log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory buffer for batch writes
        self._buffer: list = []
        self._buffer_size = 10
    
    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        data_classification: str = "INTERNAL",
        metadata: Optional[Dict[str, Any]] = None,
        # LLM-specific fields
        llm_model: Optional[str] = None,
        llm_tokens_input: Optional[int] = None,
        llm_tokens_output: Optional[int] = None,
        llm_latency_ms: Optional[int] = None,
        request_data: Optional[Any] = None,
        response_data: Optional[Any] = None,
    ) -> str:
        """
        Log an auditable action.
        
        Args:
            action: The type of action (from AuditAction enum)
            resource_type: Type of resource affected (urs, source_chunk, etc.)
            resource_id: ID of the affected resource
            user_id: ID of the user performing the action
            user_email: Email of the user
            data_classification: INTERNAL or CONFIDENTIAL
            metadata: Additional context
            llm_model: Model used for LLM actions
            llm_tokens_input: Input tokens for LLM actions
            llm_tokens_output: Output tokens for LLM actions
            llm_latency_ms: Latency in ms for LLM actions
            request_data: Request payload (will be hashed, not stored)
            response_data: Response payload (will be hashed, not stored)
        
        Returns:
            The unique log entry ID
        """
        
        entry_id = f"audit-{uuid.uuid4().hex}"
        
        # Compute hashes for request/response (don't store sensitive data)
        request_hash = None
        response_hash = None
        
        if request_data is not None:
            request_hash = AuditLogEntry.compute_hash(request_data)
        
        if response_data is not None:
            response_hash = AuditLogEntry.compute_hash(response_data)
        
        entry = AuditLogEntry(
            id=entry_id,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            data_classification=data_classification,
            llm_model=llm_model,
            llm_tokens_input=llm_tokens_input,
            llm_tokens_output=llm_tokens_output,
            llm_latency_ms=llm_latency_ms,
            request_hash=request_hash,
            response_hash=response_hash,
            metadata=metadata or {},
        )
        
        # Add to buffer
        self._buffer.append(entry)
        
        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            await self._flush()
        
        # Log to standard logger as well
        log_msg = f"AUDIT: {action.value} on {resource_type}/{resource_id}"
        if data_classification == "CONFIDENTIAL":
            logger.info(f"[CONFIDENTIAL] {log_msg}")
        else:
            logger.info(log_msg)
        
        return entry_id
    
    async def _flush(self):
        """Flush the buffer to disk."""
        if not self._buffer:
            return
        
        # Group by date for file organization
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.log_path / f"audit_{date_str}.jsonl"
        
        try:
            with open(log_file, "a") as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry.model_dump(), default=str) + "\n")
            
            self._buffer.clear()
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    async def log_llm_call(
        self,
        action: AuditAction,
        urs_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        prompt: str,
        response: Any,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Convenience method for logging LLM calls.
        """
        return await self.log(
            action=action,
            resource_type="urs",
            resource_id=urs_id,
            user_id=user_id,
            llm_model=model,
            llm_tokens_input=input_tokens,
            llm_tokens_output=output_tokens,
            llm_latency_ms=latency_ms,
            request_data=prompt,
            response_data=response,
            metadata={
                "pipeline_stage": action.value.split("_")[1] if "_" in action.value else action.value,
            },
        )
    
    async def log_data_access(
        self,
        resource_type: str,
        resource_id: str,
        access_type: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        data_classification: str = "INTERNAL",
    ) -> str:
        """
        Log data access events (especially for CONFIDENTIAL data).
        """
        return await self.log(
            action=AuditAction.DATA_ACCESSED,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            data_classification=data_classification,
            metadata={"access_type": access_type},
        )
    
    async def query(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        Query audit logs.
        
        MVP: Reads from files.
        Production: Should query from database/Elasticsearch.
        """
        
        results = []
        
        # Determine which files to read
        log_files = sorted(self.log_path.glob("audit_*.jsonl"), reverse=True)
        
        for log_file in log_files:
            try:
                with open(log_file, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        entry = json.loads(line)
                        
                        # Apply filters
                        if action and entry.get("action") != action.value:
                            continue
                        if resource_id and entry.get("resource_id") != resource_id:
                            continue
                        if user_id and entry.get("user_id") != user_id:
                            continue
                        
                        entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                        if start_date and entry_time < start_date:
                            continue
                        if end_date and entry_time > end_date:
                            continue
                        
                        results.append(entry)
                        
                        if len(results) >= limit:
                            return results
                            
            except Exception as e:
                logger.error(f"Failed to read audit log {log_file}: {e}")
        
        return results
    
    async def close(self):
        """Flush any remaining entries and close."""
        await self._flush()


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the singleton audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

