# CHECKLIST — Before Coding Anything

Before implementing or modifying code, confirm ALL items below.

## Context
- [ ] AGENTS.md has been read and understood
- [ ] docs/PROJECT_STATUS.md has been read
- [ ] docs/SESSION_PLAYBOOK.md has been read
- [ ] I can state the current project phase correctly (Phase 1)

## Scope
- [ ] Task is explicitly allowed in current phase
- [ ] Task does NOT include extraction, bbox, viewer, or PDF annotation
- [ ] No scope expansion without approval

## Tests
- [ ] Relevant test gates exist in tests/
- [ ] If missing, tests are written BEFORE implementation
- [ ] pytest passes locally

## Outputs
- [ ] All agent outputs are strict JSON
- [ ] Outputs validate against schemas
- [ ] No heuristic text parsing exists

## Errors
- [ ] Errors are explicit and documented
- [ ] Refusal cases are handled clearly

## Final Check
- [ ] I can explain in one sentence why this change is safe
- [ ] I can explain which test gate validates it