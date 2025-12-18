# URS Generator - System Architecture

## 1. High-Level Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 PRESENTATION LAYER                               │
│                                                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Intake    │  │  Clarify    │  │    URS      │  │  Approval   │            │
│   │    Form     │  │    View     │  │   Editor    │  │   Workflow  │            │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│          │                │                │                │                    │
│          └────────────────┴────────────────┴────────────────┘                    │
│                                    │                                             │
└────────────────────────────────────┼─────────────────────────────────────────────┘
                                     │ REST API
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  API LAYER                                       │
│                                                                                  │
│   FastAPI Application                                                            │
│   ├── POST /ingest          → Accept raw inputs, chunk, store                   │
│   ├── POST /clarify         → Generate clarifying questions                     │
│   ├── POST /generate-urs    → Create URS draft from inputs                      │
│   ├── POST /review          → QA pass on URS draft                              │
│   ├── GET  /urs/{id}        → Retrieve URS by ID                                │
│   ├── PUT  /urs/{id}        → Update URS (manual edits)                         │
│   └── POST /urs/{id}/approve → Submit for approval                              │
│                                                                                  │
│   Middleware:                                                                    │
│   ├── Request logging                                                            │
│   ├── Data classification enforcement                                            │
│   └── Audit trail injection                                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               PROCESSING LAYER                                   │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         LLM PROMPT PIPELINE                              │   │
│   │                                                                          │   │
│   │   STAGE 1: NORMALIZE                                                     │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ Input: Raw text, PDFs, meeting notes                             │  │   │
│   │   │ Process: Extract entities, facts, requirements, constraints      │  │   │
│   │   │ Output: Structured chunks with source_id references              │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                              │                                           │   │
│   │                              ▼                                           │   │
│   │   STAGE 2: CLARIFY                                                       │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ Input: Normalized chunks                                          │  │   │
│   │   │ Process: Identify gaps, contradictions, ambiguities              │  │   │
│   │   │ Output: List of clarifying questions with context                │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                              │                                           │   │
│   │                              ▼                                           │   │
│   │   STAGE 3: GENERATE                                                      │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ Input: Chunks + clarification answers                             │  │   │
│   │   │ Process: Synthesize into canonical URS schema                    │  │   │
│   │   │ Output: Complete URS JSON with source citations                  │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                              │                                           │   │
│   │                              ▼                                           │   │
│   │   STAGE 4: QA                                                            │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ Input: URS draft                                                  │  │   │
│   │   │ Process: Validate completeness, clarity, testability             │  │   │
│   │   │ Output: QA report with issues and recommendations                │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│   ┌──────────────────────┐  ┌──────────────────────┐                            │
│   │   Document Chunker   │  │   Source Tracker     │                            │
│   │   - PDF extraction   │  │   - Chunk ID mgmt    │                            │
│   │   - Text splitting   │  │   - Citation links   │                            │
│   │   - Image OCR        │  │   - Version refs     │                            │
│   └──────────────────────┘  └──────────────────────┘                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INTEGRATION LAYER                                   │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │                           LLM SERVICE                                     │  │
│   │                                                                           │  │
│   │   Supported Providers:                                                    │  │
│   │   ├── OpenAI GPT-4                                                       │  │
│   │   ├── Azure OpenAI                                                       │  │
│   │   └── (Pluggable for other providers)                                    │  │
│   │                                                                           │  │
│   │   Features:                                                               │  │
│   │   ├── Rate limiting                                                      │  │
│   │   ├── Token counting & tracking                                         │  │
│   │   ├── Retry with exponential backoff                                    │  │
│   │   └── Response validation                                                │  │
│   │                                                                           │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                DATA LAYER                                        │
│                                                                                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│   │  SOURCE STORE   │  │   URS STORE     │  │  AUDIT STORE    │                 │
│   │                 │  │                 │  │                 │                 │
│   │  - Raw inputs   │  │  - URS docs     │  │  - User actions │                 │
│   │  - Chunks       │  │  - Versions     │  │  - LLM calls    │                 │
│   │  - Metadata     │  │  - Status       │  │  - Data access  │                 │
│   │                 │  │                 │  │  - Timestamps   │                 │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│                                                                                  │
│   DATA CLASSIFICATION:                                                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  [INTERNAL]      - Standard handling, logged access                      │   │
│   │  [CONFIDENTIAL]  - Encrypted at rest, restricted access, enhanced audit │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Data Flow

### Ingestion Flow
```
User uploads files/text
        │
        ▼
┌───────────────────┐
│   File Handler    │──────┐
│   - Validate type │      │
│   - Extract text  │      │
│   - OCR if needed │      │
└───────────────────┘      │
        │                  │
        ▼                  ▼
┌───────────────────┐  ┌───────────────────┐
│    Chunker        │  │  Audit Logger     │
│   - Split text    │  │  - Log upload     │
│   - Assign IDs    │  │  - Log user       │
│   - Store refs    │  │  - Log timestamp  │
└───────────────────┘  └───────────────────┘
        │
        ▼
┌───────────────────┐
│  Stage 1: LLM     │
│  - Normalize      │
│  - Extract facts  │
│  - Tag sources    │
└───────────────────┘
        │
        ▼
    Structured chunks stored
```

### Generation Flow
```
Chunks + User Answers
        │
        ▼
┌───────────────────┐
│  Stage 3: LLM     │
│  - Generate URS   │
│  - Cite sources   │
│  - Mark assumptions│
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Stage 4: LLM     │
│  - QA review      │
│  - Flag issues    │
│  - Score quality  │
└───────────────────┘
        │
        ▼
    URS Draft + QA Report
```

## 3. Security & Compliance

### Data Classification
- **INTERNAL**: Default classification, standard logging
- **CONFIDENTIAL**: Enhanced encryption, access controls, full audit trail

### Audit Logging
Every action is logged with:
- Timestamp (UTC)
- User ID
- Action type
- Resource affected
- Data classification level
- LLM tokens consumed (if applicable)
- Request/response hashes

### Source Traceability
- Every requirement MUST link to source chunks
- Assumptions MUST be explicitly labeled with `[ASSUMPTION]`
- LLM-inferred content marked with confidence levels

## 4. Technology Stack (Recommended)

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | Vanilla JS / React | Simple, no build for MVP |
| API | FastAPI | Async, auto-docs, Pydantic |
| LLM | OpenAI / Azure OpenAI | Enterprise support |
| Storage | SQLite → PostgreSQL | Start simple, scale later |
| File Processing | PyMuPDF, python-docx | Reliable extraction |
| OCR | pytesseract | Open source, good enough |

## 5. Deployment Considerations

### MVP (Phase 1)
- Single server deployment
- SQLite for storage
- File-based audit logs
- Manual backup

### Production (Phase 2)
- Container deployment (Docker)
- PostgreSQL for storage
- Centralized logging (ELK/Splunk)
- Automated backup
- Load balancer for scaling

