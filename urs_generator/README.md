# URS Generator MVP

A local MVP for generating User Requirements Specifications (URS) with the workflow:
**Intake → Clarify → Generate URS → QA**

Features:
- Text-only ingestion with automatic chunking
- Clarifying questions generation with chunk traceability
- URS generation with source references and assumption labeling
- QA review with scoring and issue detection
- Data classification gate (blocks CONFIDENTIAL data from external LLMs)
- Full audit logging via database persistence
- Works in MOCK mode (no LLM key required) or REAL mode (OpenAI-compatible)

## Tech Stack

- **Backend**: Python 3.11 + FastAPI + SQLModel + SQLite
- **Frontend**: React + Vite + TypeScript
- **No auth** (MVP)

## Project Structure

```
urs_generator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app entry
│   │   ├── models.py        # SQLModel/Pydantic models
│   │   ├── database.py      # SQLite setup
│   │   ├── routes.py        # API endpoints
│   │   ├── llm.py           # LLM wrapper (mock/real)
│   │   ├── chunker.py       # Text chunking logic
│   │   └── prompts.py       # LLM prompts
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts    # API client
│   │   ├── pages/
│   │   │   ├── IntakePage.tsx
│   │   │   └── RequestPage.tsx
│   │   ├── components/
│   │   │   ├── ClarifyPanel.tsx
│   │   │   ├── URSPanel.tsx
│   │   │   └── QAPanel.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
└── README.md
```

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure env
copy .env.example .env
# (Mac/Linux: cp .env.example .env)

# Run backend
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 2. Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Copy env
copy .env.example .env
# (Mac/Linux: cp .env.example .env)

# Run frontend
npm run dev
```

Frontend runs at: http://localhost:5173

## Environment Variables

### Backend (.env)

```bash
# LLM Mode: "mock" or "real"
LLM_MODE=mock

# OpenAI settings (only needed for real mode)
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### Frontend (.env)

```bash
VITE_API_URL=http://localhost:8000
```

## Usage Flow

1. **Intake**: Enter request details and raw text → Click "Ingest" → See chunks
2. **Clarify**: Click "Generate Clarifying Questions" → Answer questions
3. **Generate URS**: Click "Generate URS" → Review requirements with source references
4. **QA Review**: Click "Run QA" → See quality score and issues

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest` | Ingest raw text, returns chunks |
| POST | `/api/clarify` | Generate clarifying questions |
| POST | `/api/generate-urs` | Generate URS from answers |
| POST | `/api/review` | Run QA review on URS |
| GET | `/api/requests/{id}` | Get full request with URS/QA |

## Data Classification Policy

- **INTERNAL**: Can use real LLM (if configured)
- **CONFIDENTIAL**: Blocked from external LLM calls (returns error)

This is an MVP safeguard. In production, integrate with approved internal LLM services.

## Mock Mode

When `LLM_MODE=mock` (default), the system returns realistic mock responses:
- Clarifying questions based on chunk content
- URS with functional/non-functional requirements
- QA reports with typical issues

This allows full demo without any API keys.

## Design Decisions

1. **Chunking**: Split by blank lines, then by ~800 char limit. Chunk IDs are stable (C-001, C-002...).
2. **Traceability**: Every requirement has `source_references` linking to chunk_ids.
3. **Assumptions**: Requirements not backed by chunks are labeled `[ASSUMPTION]` with `confidence: low`.
4. **Persistence**: All data stored in SQLite (`urs_generator.db`).
5. **Versioning**: URS has version field; QA reports timestamped.

## Future Enhancements (Not in MVP)

- PDF/OCR ingestion
- Authentication
- Collaborative editing
- Export to Word/PDF
- Integration with Azure OpenAI
- Approval workflows

