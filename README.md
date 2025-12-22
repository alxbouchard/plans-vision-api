# Plans Vision API

Vision API for understanding construction plan conventions using GPT-5.2.

## Overview

This API **learns how a project is drawn** rather than recognizing objects. It analyzes multiple pages of construction plans to discover and validate visual conventions, producing a stable, reusable visual guide.

### Core Principles

1. **Nothing is hardcoded** - No assumed meanings for symbols
2. **Nothing is guessed** - Only observable patterns are reported
3. **Rules must be observed** - Conventions require visual evidence
4. **Unstable rules are rejected** - Only validated patterns in final guide

## Architecture

```
Client
 └─ API (FastAPI)
     ├─ Storage (SQLite + File System)
     ├─ Pipeline (Multi-Agent Orchestrator)
     │   ├─ Guide Builder (gpt-5.2-pro) - Analyzes page 1
     │   ├─ Guide Applier (gpt-5.2) - Validates on pages 2-N
     │   ├─ Self-Validator (gpt-5.2-pro) - Assesses stability
     │   └─ Guide Consolidator (gpt-5.2) - Produces final guide
     └─ Storage (Visual Guides)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create a new project |
| GET | `/projects` | List all projects (tenant-scoped) |
| GET | `/projects/{id}` | Get project details |
| POST | `/projects/{id}/pages` | Upload a PNG page |
| GET | `/projects/{id}/pages` | List project pages |
| POST | `/projects/{id}/analyze` | Start analysis pipeline |
| GET | `/projects/{id}/status` | Get pipeline status |
| GET | `/projects/{id}/guide` | Get visual guide |
| GET | `/health` | Health check |

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
```

## Usage Example

```bash
# Set owner ID for tenant isolation
OWNER_ID="your-uuid-here"

# 1. Create a project
curl -X POST http://localhost:8000/projects \
  -H "X-Owner-Id: $OWNER_ID"

# 2. Upload pages (PNG only)
curl -X POST http://localhost:8000/projects/{project_id}/pages \
  -H "X-Owner-Id: $OWNER_ID" \
  -F "file=@page1.png"

curl -X POST http://localhost:8000/projects/{project_id}/pages \
  -H "X-Owner-Id: $OWNER_ID" \
  -F "file=@page2.png"

# 3. Start analysis (1+ pages)
# Single page: provisional guide only
# Multiple pages: full validation pipeline
curl -X POST http://localhost:8000/projects/{project_id}/analyze \
  -H "X-Owner-Id: $OWNER_ID"

# 4. Check status
curl http://localhost:8000/projects/{project_id}/status \
  -H "X-Owner-Id: $OWNER_ID"

# 5. Get the visual guide
curl http://localhost:8000/projects/{project_id}/guide \
  -H "X-Owner-Id: $OWNER_ID"
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src

# Verbose output
pytest -v
```

## Project Structure

```
plans-vision-api/
├── src/
│   ├── agents/           # GPT-5.2 vision agents
│   ├── api/              # FastAPI application
│   ├── models/           # Pydantic models
│   ├── pipeline/         # Multi-agent orchestrator
│   ├── storage/          # Database & file storage
│   ├── config.py         # Configuration
│   ├── logging.py        # Structured logging
│   └── main.py           # Entry point
├── tests/                # Test suite
├── pyproject.toml        # Project configuration
└── .env.example          # Environment template
```

## Pipeline Flow

### Multi-Page Projects (2+ pages)

1. **Guide Builder** analyzes page 1 to create a provisional visual guide
2. **Guide Applier** tests the provisional guide against pages 2-N
3. **Self-Validator** evaluates rule stability across all pages
4. **Guide Consolidator** produces the final stable guide (or rejects if unstable)

### Single-Page Projects (Option B)

With only 1 page, cross-validation is impossible. The pipeline:
- Generates a **provisional guide only**
- Sets `stable = null`
- Returns explicit rejection reason explaining the limitation

```json
{
  "has_provisional": true,
  "has_stable": false,
  "rejection_message": "Cannot generate stable guide: Only 1 page provided..."
}
```

## Rule Stability

All agents produce **structured JSON outputs** with explicit classification:

- **Stable**: Confirmed on 80%+ of testable pages, **zero contradictions**
- **Partial**: Confirmed on 50-79%, or minor variations exist
- **Unstable**: **Any contradiction on any page**, or <50% confirmation

### Contradiction Handling

A single contradiction immediately marks a rule as **UNSTABLE**:
- The rule is excluded from the final guide
- If too many rules are unstable (<60% stable), no guide is generated
- Rejection reason explicitly explains which rules failed and why

Only **stable** rules appear in the final guide.

## Structured Outputs

All agent responses use Pydantic-validated JSON schemas:

```python
# Guide Builder Output
{
  "observations": [...],
  "candidate_rules": [...],
  "uncertainties": [...],
  "assumptions": []  # MUST be empty
}

# Self-Validator Output
{
  "rule_assessments": [
    {
      "rule_id": "RULE_001",
      "classification": "stable | partial | unstable",
      "pages_confirmed": 3,
      "pages_contradicted": 0
    }
  ],
  "can_generate_guide": true,
  "rejection_reason": null
}
```

## License

MIT
