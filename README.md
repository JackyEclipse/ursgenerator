# URS Generator

An internal web application that ingests messy stakeholder inputs and uses LLM to produce structured, approval-ready User Requirements Specifications (URS).

## Features

- **4-Stage Pipeline**: Intake → Clarify → Generate URS → QA Review
- **Source Traceability**: Every requirement links back to source chunks
- **Assumption Labeling**: LLM-inferred content is explicitly marked `[ASSUMPTION]`
- **Data Classification**: INTERNAL or CONFIDENTIAL handling
- **Mock Mode**: Works without LLM API key for demos
- **Audit Logging**: All operations are logged

## Quick Start

### Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
# Windows:
copy env.example.txt .env
# Mac/Linux:
cp env.example.txt .env

# Run the backend server
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Frontend Setup

Open a new terminal:

```bash
cd frontend

# Serve the frontend (any static file server works)
python -m http.server 3000
```

Frontend runs at: http://localhost:3000

**Or simply open `frontend/index.html` directly in your browser.**

## Environment Variables

Edit `backend/.env`:

```bash
# LLM Mode: "mock" (default) or "real"
LLM_MODE=mock

# Only needed for LLM_MODE=real
OPENAI_API_KEY=sk-your-key-here

# Optional settings
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
DEBUG=false
```

## Usage Flow

1. **Intake**: Fill in project details and requirements text → Click "Analyze & Extract"
2. **Clarify**: Answer the generated clarifying questions
3. **Generate URS**: Review the generated URS document with requirements
4. **QA Review**: See quality scores and issues to address
5. **Approval**: Submit for stakeholder approval

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest` | Ingest raw text/files, returns chunks |
| POST | `/api/clarify` | Generate clarifying questions |
| POST | `/api/clarify/answer` | Submit answers to questions |
| POST | `/api/generate-urs` | Generate URS from chunks + answers |
| POST | `/api/review` | Run QA review on URS |
| GET | `/api/urs/{id}` | Get URS document |
| GET | `/api/urs` | List all URS documents |
| POST | `/api/urs/{id}/approve` | Submit for approval |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           FRONTEND                               │
│  Intake Form  │  Clarify View  │  URS Editor  │  Approval View  │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                       │
│  /ingest  →  /clarify  →  /generate-urs  →  /review  →  /approve │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING PIPELINE                          │
│   Stage 1      Stage 2       Stage 3         Stage 4            │
│  Normalize  →  Clarify   →   Generate   →     QA                │
│  (chunk)      (questions)    (URS)          (validate)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────┐    ┌────────────────────┐
│    LLM SERVICE    │    │    AUDIT LOGGER    │
│  (Mock or Real)   │    │  (all operations)  │
└───────────────────┘    └────────────────────┘
```

## Data Classification Policy

- **INTERNAL**: Standard handling, can use external LLM
- **CONFIDENTIAL**: Enhanced security (in production: blocks external LLM calls)

## Project Structure

```
urs_generator/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Environment configuration
│   ├── models/              # Pydantic data models
│   │   ├── ingest.py        # Ingestion models
│   │   ├── urs.py           # URS document schema
│   │   └── audit.py         # Audit log models
│   ├── routers/             # API endpoint handlers
│   │   ├── ingest.py        # POST /ingest
│   │   ├── clarify.py       # POST /clarify
│   │   ├── generate.py      # POST /generate-urs
│   │   ├── review.py        # POST /review
│   │   └── urs.py           # URS management
│   ├── services/            # Business logic
│   │   ├── llm_service.py   # LLM wrapper (mock/real)
│   │   ├── chunking.py      # Text chunking
│   │   └── audit_logger.py  # Audit logging
│   └── prompts/             # LLM prompt templates
├── frontend/
│   ├── index.html           # Main SPA
│   ├── styles.css           # CSS styling
│   └── app.js               # Frontend JavaScript
├── docs/
│   └── architecture.md      # Detailed architecture
└── README.md
```

## Development

### Running Tests

```bash
cd backend
pytest
```

### Adding New Features

1. Define models in `backend/models/`
2. Add prompts in `backend/prompts/`
3. Implement router in `backend/routers/`
4. Update frontend in `frontend/`

## Tech Stack

- **Backend**: Python 3.11 + FastAPI + Pydantic
- **Storage**: In-memory (MVP), SQLite planned
- **LLM**: OpenAI-compatible API (mock mode available)
- **Frontend**: Vanilla HTML/CSS/JS (no build required)

## MVP Limitations

- No authentication (add in production)
- No PDF/OCR ingestion yet (text-only)
- In-memory storage (add database for persistence)
- Single-user (add sessions for multi-user)

## License

Internal use only.
