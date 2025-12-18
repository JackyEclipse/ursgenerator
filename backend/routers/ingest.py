"""
Ingestion Router - POST /ingest

Handles:
- File uploads (PDF, DOCX, images, text)
- Raw text input
- Chunking and source ID assignment
- Stage 1: Normalization via LLM
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import List, Optional
import uuid
from datetime import datetime

from models.ingest import (
    IngestRequest,
    IngestResponse,
    SourceChunk,
    SourceType,
)
from models.audit import AuditLogEntry, AuditAction

router = APIRouter()


# ============================================================================
# In-memory storage for MVP (replace with database in production)
# ============================================================================
sessions = {}  # session_id -> session data
chunks = {}    # chunk_id -> SourceChunk


def generate_urs_id() -> str:
    """Generate a unique URS ID."""
    year = datetime.utcnow().year
    seq = len([s for s in sessions.values() if s.get("year") == year]) + 1
    return f"URS-{year}-{seq:04d}"


def generate_chunk_id(source_id: str, index: int) -> str:
    """Generate a unique chunk ID."""
    return f"{source_id}-chunk-{index:04d}"


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/ingest", response_model=IngestResponse)
async def ingest_sources(
    background_tasks: BackgroundTasks,
    title: str = Form("Untitled Request"),
    description: Optional[str] = Form(None),
    requestor_name: str = Form("Anonymous"),
    requestor_email: str = Form("anonymous@example.com"),
    department: str = Form("General"),
    raw_text: Optional[str] = Form(None),
    meeting_notes: Optional[str] = Form(None),
    email_thread: Optional[str] = Form(None),
    data_classification: str = Form("INTERNAL"),
    files: List[UploadFile] = File(default=[]),
):
    """
    Ingest raw stakeholder inputs and create source chunks.
    
    This endpoint:
    1. Accepts multiple input types (text, files)
    2. Creates source chunks with unique IDs
    3. Triggers Stage 1 normalization (async)
    4. Returns session ID for subsequent operations
    
    ## Input Types Supported
    - **raw_text**: Free-form text descriptions
    - **meeting_notes**: Meeting transcript or notes
    - **email_thread**: Email conversation
    - **files**: PDF, DOCX, PNG, JPG, TXT files
    
    ## Data Classification
    - **INTERNAL**: Standard handling
    - **CONFIDENTIAL**: Enhanced security, full audit trail
    """
    
    # Generate IDs
    session_id = str(uuid.uuid4())
    urs_id = generate_urs_id()
    source_id = f"src-{session_id[:8]}"
    
    # Sanitize title - truncate if too long
    safe_title = (title or "Untitled Request")[:200].strip()
    if not safe_title:
        safe_title = "Untitled Request"
    
    # Create session
    sessions[session_id] = {
        "urs_id": urs_id,
        "source_id": source_id,
        "title": safe_title,
        "requestor": {"name": requestor_name, "email": requestor_email},
        "department": department,
        "data_classification": data_classification,
        "created_at": datetime.utcnow(),
        "status": "ingesting",
        "year": datetime.utcnow().year,
    }
    
    created_chunks = []
    chunk_index = 0
    
    # Process raw text inputs
    for text_input, source_type in [
        (raw_text, SourceType.USER_INPUT),
        (meeting_notes, SourceType.MEETING_NOTES),
        (email_thread, SourceType.EMAIL),
    ]:
        if text_input and text_input.strip():
            # Split into chunks (simplified - use proper chunking in production)
            text_chunks = _split_text(text_input)
            for chunk_text in text_chunks:
                chunk_id = generate_chunk_id(source_id, chunk_index)
                chunk = SourceChunk(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    source_type=source_type,
                    source_name=f"{source_type.value}_input",
                    content=chunk_text,
                    content_hash=_hash_content(chunk_text),
                    data_classification=data_classification,
                )
                chunks[chunk_id] = chunk
                created_chunks.append(chunk)
                chunk_index += 1
    
    # Process uploaded files
    for file in files:
        if file.filename:
            content = await file.read()
            
            # Determine source type from file extension
            ext = file.filename.lower().split(".")[-1]
            source_type = _get_source_type(ext)
            
            # Extract text from file (simplified - use proper extraction in production)
            text_content = await _extract_text_from_file(content, ext)
            
            if text_content:
                text_chunks = _split_text(text_content)
                for chunk_text in text_chunks:
                    chunk_id = generate_chunk_id(source_id, chunk_index)
                    chunk = SourceChunk(
                        chunk_id=chunk_id,
                        source_id=source_id,
                        source_type=source_type,
                        source_name=file.filename,
                        content=chunk_text,
                        content_hash=_hash_content(chunk_text),
                        data_classification=data_classification,
                    )
                    chunks[chunk_id] = chunk
                    created_chunks.append(chunk)
                    chunk_index += 1
    
    if not created_chunks:
        raise HTTPException(
            status_code=400,
            detail="No content provided. Please provide text or upload files."
        )
    
    # Store chunks in session
    sessions[session_id]["chunk_ids"] = [c.chunk_id for c in created_chunks]
    sessions[session_id]["status"] = "ingested"
    
    # TODO: Trigger Stage 1 normalization in background
    # background_tasks.add_task(normalize_chunks, session_id, created_chunks)
    
    # Log audit entry
    # TODO: Write to actual audit store
    
    return IngestResponse(
        session_id=session_id,
        urs_id=urs_id,
        chunks_created=len(created_chunks),
        normalized_facts=0,  # Will be updated after Stage 1
        extracted_summary=f"Ingested {len(created_chunks)} chunks from {len(files)} files and text inputs",
        needs_clarification=True,  # Will be determined after Stage 2
        clarifying_questions_count=0,
    )


@router.post("/ingest/files")
async def upload_files(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Upload additional files to an existing session.
    Useful for adding more context after initial ingestion.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # TODO: Process and add files to existing session
    
    return {"status": "files_added", "count": len(files)}


# ============================================================================
# Helper Functions
# ============================================================================

def _split_text(text: str, max_chars: int = 2000) -> List[str]:
    """
    Split text into chunks.
    In production, use proper sentence/paragraph-aware chunking.
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current = ""
    
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current += "\n\n" + paragraph if current else paragraph
    
    if current:
        chunks.append(current.strip())
    
    return chunks if chunks else [text]


def _hash_content(content: str) -> str:
    """Generate content hash for deduplication."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_source_type(ext: str) -> SourceType:
    """Map file extension to source type."""
    mapping = {
        "pdf": SourceType.DOCUMENT,
        "docx": SourceType.DOCUMENT,
        "doc": SourceType.DOCUMENT,
        "txt": SourceType.DOCUMENT,
        "png": SourceType.SCREENSHOT,
        "jpg": SourceType.SCREENSHOT,
        "jpeg": SourceType.SCREENSHOT,
        "eml": SourceType.EMAIL,
    }
    return mapping.get(ext, SourceType.DOCUMENT)


async def _extract_text_from_file(content: bytes, ext: str) -> str:
    """
    Extract text from file content.
    In production, use PyMuPDF for PDF, python-docx for DOCX, pytesseract for images.
    """
    if ext == "txt":
        return content.decode("utf-8", errors="ignore")
    
    if ext == "pdf":
        # TODO: Use PyMuPDF (fitz)
        # import fitz
        # doc = fitz.open(stream=content, filetype="pdf")
        # return "\n".join([page.get_text() for page in doc])
        return "[PDF content extraction - implement with PyMuPDF]"
    
    if ext in ("docx", "doc"):
        # TODO: Use python-docx
        # from docx import Document
        # doc = Document(io.BytesIO(content))
        # return "\n".join([p.text for p in doc.paragraphs])
        return "[DOCX content extraction - implement with python-docx]"
    
    if ext in ("png", "jpg", "jpeg"):
        # TODO: Use pytesseract for OCR
        # import pytesseract
        # from PIL import Image
        # img = Image.open(io.BytesIO(content))
        # return pytesseract.image_to_string(img)
        return "[Image OCR - implement with pytesseract]"
    
    return ""

