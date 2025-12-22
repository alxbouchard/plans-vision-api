# RUNBOOK — plans-vision-api

## Quick Reference

| Action | Command |
|--------|---------|
| Run server | `make run` |
| Run tests | `make test` |
| Check health | `curl http://localhost:8000/health` |

---

## Quick Start (Local)

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with OPENAI_API_KEY

# Test
make test

# Run
make run
```

---

## Common Operations

### Run Tests

```bash
make test
# or
pytest tests/ -v
```

### Run API Locally

```bash
make run
# or
uvicorn src.main:app --reload --port 8000
```

### Generate Test Fixtures

```bash
python testdata/generate_fixtures.py
```

---

## API Usage Examples

### Create Project

```bash
curl -X POST http://localhost:8000/projects \
  -H "X-Owner-Id: $(uuidgen)"
```

### Upload Page

```bash
curl -X POST http://localhost:8000/projects/{project_id}/pages \
  -H "X-Owner-Id: {owner_id}" \
  -F "file=@page1.png"
```

### Start Analysis

```bash
curl -X POST http://localhost:8000/projects/{project_id}/analyze \
  -H "X-Owner-Id: {owner_id}"
```

### Check Status

```bash
curl http://localhost:8000/projects/{project_id}/status \
  -H "X-Owner-Id: {owner_id}"
```

### Get Guide

```bash
curl http://localhost:8000/projects/{project_id}/guide \
  -H "X-Owner-Id: {owner_id}"
```

---

## Triage Guide

### Pipeline Stuck in "processing"

1. Check `/status` endpoint for current_step
2. Inspect logs for step timeouts or errors
3. Verify model call retries (max 3 attempts with exponential backoff)
4. Check OPENAI_API_KEY is valid

### Model Output Invalid JSON

- Expected behavior (Gate 4 test)
- Inspect logs for MODEL_INVALID_OUTPUT error
- Check error.step field for which agent failed
- Schema validation errors return 500 with error_code

### Guide Rejected (No Stable Rules)

1. Check `confidence_report.rejection_reason` in response
2. Look at `confidence_report.rules` for unstable items
3. Contradicted rules → UNSTABLE (any contradiction fails the rule)
4. Solution: Upload additional pages with consistent conventions

### 401 Unauthorized

- Missing `X-Owner-Id` or `X-API-Key` header
- Invalid API key (check for typos)
- Solution: Include valid authentication header

### 429 Too Many Requests

- Rate limit exceeded (60 req/min default)
- Check `Retry-After` response header
- Wait and retry after indicated seconds

### 415 Unsupported Media Type

- Non-PNG file uploaded
- Check actual file format (not just extension)
- Solution: Convert to PNG format

---

## Incident Checklist

When investigating production issues:

1. **Capture identifiers**:
   - `X-Request-ID` from response headers
   - `tenant_id` from auth
   - `project_id` from request

2. **Check logs**:
   - Filter by request_id
   - Look for error_code fields
   - Check duration_ms for slow requests

3. **Verify infrastructure**:
   - Health check: `curl /health`
   - Database connectivity
   - Disk space for uploads

4. **Check external services**:
   - OpenAI API status
   - Rate limiting on model calls

---

## Maintenance

### Database Backup

```bash
cp plans_vision.db plans_vision.db.backup
```

### Clean Old Files

```python
from src.storage import FileStorage
storage = FileStorage()
await storage.cleanup_old_files(max_age_days=30)
```

### Check Storage Stats

```python
from src.storage import FileStorage
storage = FileStorage()
print(storage.get_storage_stats())
# {"total_files": 42, "total_size_mb": 123.5, "tenant_count": 5}
```
