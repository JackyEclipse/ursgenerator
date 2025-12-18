"""
URS Generator - FastAPI Application Entry Point

This is the main application that coordinates:
- Ingestion of raw stakeholder inputs
- LLM-powered analysis and generation
- URS document management
- Audit logging
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from config import get_settings
from routers import ingest, clarify, generate, review, urs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Default data classification: {settings.default_classification}")
    
    # TODO: Initialize database connection
    # TODO: Validate LLM credentials
    
    yield
    
    # Shutdown
    logger.info("Shutting down URS Generator")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## URS Generator API
    
    Transform messy stakeholder inputs into structured, 
    approval-ready User Requirements Specifications.
    
    ### Pipeline Stages
    1. **Ingest** - Upload and chunk raw inputs
    2. **Clarify** - Get/answer clarifying questions
    3. **Generate** - Create structured URS
    4. **Review** - QA and validation
    
    ### Key Features
    - Source traceability for all requirements
    - Explicit assumption labeling
    - Full audit logging
    - Data classification support
    """,
    lifespan=lifespan,
)

# CORS middleware (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Middleware for Audit Logging
# ============================================================================

@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """
    Middleware to log all requests for audit purposes.
    In production, this would write to a proper audit store.
    """
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.info(f"Response: {response.status_code} ({duration_ms:.0f}ms)")
    
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred"}
    )


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(clarify.router, prefix="/api", tags=["Clarification"])
app.include_router(generate.router, prefix="/api", tags=["Generation"])
app.include_router(review.router, prefix="/api", tags=["Review"])
app.include_router(urs.router, prefix="/api", tags=["URS Management"])


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "llm_provider": settings.llm_provider,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.post("/api/export-doc", tags=["Export"])
async def export_doc(request: Request):
    """
    Export URS document as Word (.doc) file.
    Accepts form data or JSON with doc_content and filename.
    """
    content_type = request.headers.get("content-type", "")
    
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        doc_content = form.get("doc_content", "")
        filename = form.get("filename", "document.doc")
    else:
        body = await request.json()
        doc_content = body.get("doc_content", "")
        filename = body.get("filename", "document.doc")
    
    return Response(
        content=doc_content,
        media_type="application/msword",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/msword; charset=utf-8",
            "X-Content-Type-Options": "nosniff"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )



