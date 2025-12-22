# RUNBOOK — plans-vision-api

## Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
uvicorn src.main:app --reload
```

## Common Operations

### Run tests
```bash
pytest -v
```

### Run API locally
```bash
uvicorn src.main:app --reload
```

## Triage Guide

### Pipeline stuck in running
- Check /status
- Inspect logs for step timeouts
- Verify model call retries

### Model output invalid JSON
- Expect failure (Gate 4)
- Inspect stored raw output in logs or debug artifacts
- Confirm schema validation error is returned

### Guide rejected
- Look at confidence_report.rejection_reason
- Confirm contradiction evidence exists
- Ask for more pages

## Incident Checklist
- Capture request_id
- Capture tenant_id
- Capture project_id
- Export logs for the time window
