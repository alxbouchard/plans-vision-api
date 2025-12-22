# SESSION_PLAYBOOK — Claude Code (plans-vision-api)

This document defines how to start, run, pause, and resume a Claude Code
development session on this repository.

It exists to prevent context drift, rework, and accidental scope creep.

---

## 1) How to Start a New Session (MANDATORY)

When starting a new Claude Code session, the FIRST message MUST be:

"Read AGENTS.md, docs/PROJECT_STATUS.md, docs/FEATURE_BuildGuide.md,
docs/TEST_GATES.md, and docs/ERRORS.md.
Then summarize in one sentence where the project currently is.
Do NOT implement anything until I confirm."

If the agent does not explicitly mention:
- Phase 1
- test gates
- provisional-only behavior
- contradiction rejection

Stop and correct the understanding before proceeding.

---

## 2) Allowed Work in Current Phase

Allowed:
- Adding or fixing test gates
- Improving validation of JSON outputs
- Adding real PNG fixtures for testing
- Making rejection behavior clearer or more explicit
- Improving logs or error clarity related to Phase 1

Forbidden (without explicit approval):
- Object extraction
- Bounding boxes or polygons
- Viewer-related code
- PDF annotation output
- Pricing, billing, or SaaS logic

If unsure, the agent MUST ask before implementing.

---

## 3) Workflow Rules

All work MUST follow this order:

1. Read the relevant FEATURE doc in docs/
2. Write or update tests according to docs/TEST_GATES.md
3. Run `pytest`
4. Implement until tests pass
5. Commit with a clear message

No commit is allowed if tests are failing.

---

## 4) Command Reference

Activate environment:
```bash
source .venv/bin/activate