# Plans Vision API

Vision API for understanding construction plan conventions using GPT-5.2.

## Overview

This API **learns how a project is drawn** rather than recognizing objects. It analyzes multiple pages of construction plans to discover and validate visual conventions, producing a stable, reusable visual guide.

### Core Principles

1. **Nothing is hardcoded** - No assumed meanings for symbols
2. **Nothing is guessed** - Only observable patterns are reported
3. **Rules must be observed** - Conventions require visual evidence
4. **Unstable rules are rejected** - Only validated patterns in final guide

---

## Quick Demo

Upload a PDF master, query a room, get an annotated PDF:

```bash
API_KEY="pv_your-api-key"
PROJECT_ID="..."  # from project creation

# 1. Upload PDF master
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/pdf \
  -H "X-API-Key: $API_KEY" \
  -F "file=@plans.pdf"
# Returns: pdf_id, fingerprint, page_count

# 2. Build mapping (PNG ↔ PDF coordinates)
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/pdf/$PDF_ID/build-mapping \
  -H "X-API-Key: $API_KEY"
# Returns: mapping_job_id, status: processing

# 3. Query room 203 (with PDF geometry)
curl "http://localhost:8000/v3/projects/$PROJECT_ID/query?room_number=203" \
  -H "X-API-Key: $API_KEY"
# Returns: matches with geometry_png AND geometry_pdf

# 4. Render annotated PDF
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/render/pdf \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_id": "'$PDF_ID'",
    "mapping_version_id": "'$MAPPING_ID'",
    "objects": ["room_203"],
    "style": {"mode": "highlight", "include_labels": true}
  }'
# Returns: render_job_id → output_pdf_url
```

---

## API Versions

| Version | Phase | Description |
|---------|-------|-------------|
| v1 | Visual Guide Generation | Learn project conventions from PNG pages |
| v2 | Extraction and Query | Extract rooms, doors, schedules; query by room number |
| v3 | Render | Anchor to PDF master, annotated PDF output |

---

## Authentication

All endpoints require authentication via `X-API-Key` header:

```bash
curl -H "X-API-Key: pv_your-api-key" http://localhost:8000/projects
```

Legacy `X-Owner-Id` (UUID) is supported for backwards compatibility.

---

## V1 — Visual Guide Generation

Build a project-specific visual guide from PNG pages.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create a new project |
| GET | `/projects` | List all projects |
| GET | `/projects/{id}` | Get project details |
| POST | `/projects/{id}/pages` | Upload a PNG page |
| GET | `/projects/{id}/pages` | List project pages |
| POST | `/projects/{id}/analyze` | Start analysis pipeline |
| GET | `/projects/{id}/status` | Get pipeline status |
| GET | `/projects/{id}/guide` | Get visual guide |

### Example

```bash
API_KEY="pv_your-api-key"

# Create project
curl -X POST http://localhost:8000/projects \
  -H "X-API-Key: $API_KEY"

# Upload pages
curl -X POST http://localhost:8000/projects/$PROJECT_ID/pages \
  -H "X-API-Key: $API_KEY" \
  -F "file=@page1.png"

curl -X POST http://localhost:8000/projects/$PROJECT_ID/pages \
  -H "X-API-Key: $API_KEY" \
  -F "file=@page2.png"

# Start analysis
curl -X POST http://localhost:8000/projects/$PROJECT_ID/analyze \
  -H "X-API-Key: $API_KEY"

# Check status
curl http://localhost:8000/projects/$PROJECT_ID/status \
  -H "X-API-Key: $API_KEY"

# Get guide
curl http://localhost:8000/projects/$PROJECT_ID/guide \
  -H "X-API-Key: $API_KEY"
```

### Pipeline Flow

1. **Guide Builder** analyzes page 1 → provisional guide
2. **Guide Applier** tests guide against pages 2-N
3. **Self-Validator** evaluates rule stability
4. **Guide Consolidator** produces final stable guide (or rejects)

Single-page projects return provisional guide only (`stable = null`).

---

## V2 — Extraction and Query

Extract objects (rooms, doors, schedules) and query by attributes.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v2/projects/{id}/extract` | Start extraction pipeline |
| GET | `/v2/projects/{id}/extract/status` | Get extraction status |
| GET | `/v2/projects/{id}/query` | Query objects |
| GET | `/v2/projects/{id}/pages/{page_id}/overlay` | Get page overlay data |

### Example: Extract Objects

```bash
API_KEY="pv_your-api-key"

# Start extraction (requires completed guide)
curl -X POST http://localhost:8000/v2/projects/$PROJECT_ID/extract \
  -H "X-API-Key: $API_KEY"
# Returns: job_id, status: processing

# Check extraction status
curl http://localhost:8000/v2/projects/$PROJECT_ID/extract/status \
  -H "X-API-Key: $API_KEY"
# Returns: status, current_step, extracted objects count
```

### Example: Query Objects

```bash
# Query by room number
curl "http://localhost:8000/v2/projects/$PROJECT_ID/query?room_number=203" \
  -H "X-API-Key: $API_KEY"

# Query by room name
curl "http://localhost:8000/v2/projects/$PROJECT_ID/query?room_name=CLASSE" \
  -H "X-API-Key: $API_KEY"

# Query by object type
curl "http://localhost:8000/v2/projects/$PROJECT_ID/query?type=door" \
  -H "X-API-Key: $API_KEY"
```

### Query Response

```json
{
  "schema_version": "2.0",
  "project_id": "...",
  "query": {"room_number": "203"},
  "ambiguous": false,
  "matches": [
    {
      "object_id": "room_203",
      "type": "room",
      "page_number": 12,
      "label": "CLASSE 203",
      "confidence": 0.92,
      "confidence_level": "high",
      "geometry": {"type": "bbox", "bbox": [100, 200, 300, 250]}
    }
  ]
}
```

If multiple matches exist, `ambiguous: true` is returned (no arbitrary picking).

---

## V3 — Render (PDF Master Anchoring)

Anchor extracted objects to the PDF master and produce annotated output.

**Key principle**: Renderer performs **zero model calls**. All geometry is derived from mapping.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v3/projects/{id}/pdf` | Upload PDF master |
| POST | `/v3/projects/{id}/pdf/{pdf_id}/build-mapping` | Build PNG↔PDF mapping |
| GET | `/v3/projects/{id}/pdf/{pdf_id}/mapping/status` | Mapping job status |
| GET | `/v3/projects/{id}/pdf/{pdf_id}/mapping` | Get mapping metadata |
| GET | `/v3/projects/{id}/query` | Query with PDF geometry |
| POST | `/v3/projects/{id}/render/pdf` | Render annotated PDF |
| GET | `/v3/projects/{id}/render/pdf/{job_id}` | Get render status |
| POST | `/v3/projects/{id}/render/annotations` | Export annotations JSON |

### Example: Upload PDF and Build Mapping

```bash
API_KEY="pv_your-api-key"

# Upload PDF master
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/pdf \
  -H "X-API-Key: $API_KEY" \
  -F "file=@architectural_plans.pdf"

# Response:
# {
#   "schema_version": "3.1",
#   "pdf_id": "abc-123",
#   "page_count": 42,
#   "fingerprint": "sha256...",
#   "stored_at": "2025-12-23T..."
# }

# Build mapping
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/pdf/$PDF_ID/build-mapping \
  -H "X-API-Key: $API_KEY"

# Check mapping status
curl http://localhost:8000/v3/projects/$PROJECT_ID/pdf/$PDF_ID/mapping/status \
  -H "X-API-Key: $API_KEY"

# Get mapping metadata
curl http://localhost:8000/v3/projects/$PROJECT_ID/pdf/$PDF_ID/mapping \
  -H "X-API-Key: $API_KEY"
```

### Example: Query with PDF Geometry

```bash
# Query returns both PNG and PDF coordinates
curl "http://localhost:8000/v3/projects/$PROJECT_ID/query?room_number=203" \
  -H "X-API-Key: $API_KEY"

# Response includes:
# {
#   "matches": [{
#     "geometry_png": {"type": "bbox", "bbox": [100, 200, 300, 250]},
#     "geometry_pdf": {"type": "rect", "rect": [72.0, 144.0, 216.0, 288.0]},
#     "trace": {
#       "pdf_id": "...",
#       "pdf_fingerprint": "sha256...",
#       "mapping_version_id": "..."
#     }
#   }]
# }
```

### Example: Render Annotated PDF

```bash
# Render specific objects
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/render/pdf \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_id": "'$PDF_ID'",
    "mapping_version_id": "'$MAPPING_ID'",
    "objects": ["room_203", "door_203a"],
    "style": {
      "mode": "highlight",
      "include_labels": true,
      "min_confidence_level": "medium"
    }
  }'

# Response:
# {
#   "render_job_id": "xyz-789",
#   "status": "processing"
# }

# Get rendered PDF
curl http://localhost:8000/v3/projects/$PROJECT_ID/render/pdf/$RENDER_JOB_ID \
  -H "X-API-Key: $API_KEY"

# Response:
# {
#   "status": "completed",
#   "output_pdf_url": "https://..."
# }
```

### Example: Export Annotations Only

```bash
curl -X POST http://localhost:8000/v3/projects/$PROJECT_ID/render/annotations \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_id": "'$PDF_ID'",
    "mapping_version_id": "'$MAPPING_ID'",
    "objects": ["room_203"],
    "format": "json"
  }'

# Response:
# {
#   "annotations": [
#     {
#       "page_number": 12,
#       "type": "rect",
#       "rect": [72.0, 144.0, 216.0, 288.0],
#       "label": "CLASSE 203",
#       "object_id": "room_203"
#     }
#   ]
# }
```

### Safety Checks

- **PDF_MISMATCH**: Fingerprint mismatch between PDF and mapping → refused
- **MAPPING_REQUIRED**: No mapping exists for this PDF → refused
- Low confidence objects excluded unless explicitly requested

---

## Installation

```bash
# Clone the repository
git clone https://github.com/alxbouchard/plans-vision-api.git
cd plans-vision-api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install .

# For development
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required:
- `OPENAI_API_KEY` - Your OpenAI API key

Optional:
- `DATABASE_URL` - Database connection (default: SQLite)
- `UPLOAD_DIR` - Image storage directory
- `API_HOST` / `API_PORT` - Server settings
- `LOG_LEVEL` - Logging verbosity

## Running

```bash
# Start the server
python -m src.main

# API available at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
# Test UI at file:///.../test-ui.html (open in browser)
```

## Testing

```bash
# Run all tests
pytest -v

# Test summary (collected/passed/skipped)
./scripts/test_summary.sh

# With coverage
pytest --cov=src

# Generate test fixtures
make fixtures
```

---

## Architecture

```
Client
 └─ API (FastAPI)
     ├─ V1 Routes (Guide Generation)
     ├─ V2 Routes (Extraction & Query)
     ├─ V3 Routes (Render)
     ├─ Storage (SQLite + File System)
     ├─ Pipeline (Multi-Agent Orchestrator)
     │   ├─ Guide Builder (gpt-5.2-pro)
     │   ├─ Guide Applier (gpt-5.2)
     │   ├─ Self-Validator (gpt-5.2-pro)
     │   └─ Guide Consolidator (gpt-5.2)
     └─ Extraction (Classifier, Room/Door/Schedule Extractors)
```

## Project Structure

```
plans-vision-api/
├── src/
│   ├── agents/           # GPT-5.2 vision agents
│   ├── api/
│   │   ├── routes/       # V1 API endpoints
│   │   ├── routes_v2/    # V2 extraction & query
│   │   └── app.py        # FastAPI application
│   ├── extraction/       # Object extractors
│   ├── models/
│   │   ├── entities.py   # Domain models
│   │   ├── schemas_v2.py # V2 API schemas
│   │   └── schemas_v3.py # V3 API schemas
│   ├── pipeline/         # Multi-agent orchestrator
│   ├── storage/          # Database & file storage
│   └── main.py           # Entry point
├── tests/                # Test suite
├── docs/                 # Documentation
│   ├── API_CONTRACT_v1.md
│   ├── API_CONTRACT_v2.md
│   ├── API_CONTRACT_Render_v3.md
│   ├── ERRORS.md
│   └── PROJECT_STATUS.md
└── test-ui.html          # Visual test interface
```

---

## Rule Stability (V1)

All agents produce **structured JSON outputs** with explicit classification:

- **Stable**: Confirmed on 80%+ of testable pages, **zero contradictions**
- **Partial**: Confirmed on 50-79%, or minor variations exist
- **Unstable**: **Any contradiction on any page**, or <50% confirmation

A single contradiction immediately marks a rule as **UNSTABLE** and excludes it from the final guide.

---

## Error Codes

All errors follow a consistent JSON format:

```json
{
  "schema_version": "3.1",
  "error_code": "PDF_MISMATCH",
  "message": "PDF fingerprint does not match mapping",
  "recoverable": false
}
```

See `docs/ERRORS.md` for the complete error taxonomy.

---

## License

MIT
