# START_PROMPT — Claude Code (plans-vision-api)

This file contains the exact startup prompt to use when beginning a new
Claude Code session on this repository.

Use this prompt verbatim. Do not paraphrase.

---

## Startup Prompt (COPY / PASTE)

Read AGENTS.md at the root of the repository and apply all rules strictly.

Then read the following documents:
- docs/PROJECT_STATUS.md
- docs/SESSION_PLAYBOOK.md
- docs/FEATURE_BuildGuide.md
- docs/TEST_GATES.md
- docs/ERRORS.md
- docs/RELEASE_CRITERIA.md

## MCAF — Mandatory Cognitive Architecture Framework (Non-Negotiable)

This repository follows a strict MCAF rule.

Core principles:

1. NO business logic is ever hardcoded.
   - No keyword lists
   - No exclusion lists
   - No semantic assumptions
   - No pattern rules in code

2. The Visual Guide is the SINGLE source of intelligence.
   - All semantic understanding comes from the guide
   - The guide may contain machine-readable payloads
   - Code executes payloads, never interprets meaning

3. Engines are pure executors.
   - SpatialRoomLabeler
   - Detectors
   - Pairing logic
   These components must be data-driven only.

4. If a rule is missing, the system must fail silently and observably.
   - rooms_emitted = 0 is valid
   - logs must explain why
   - tests must cover this case

5. Tests define truth.
   - Tests must not be modified to match new logic unless the architecture changes
   - If tests break, investigate architectural violation first

6. Guide evolution is allowed.
   - Guide schema MAY evolve
   - Guide payloads MAY expand
   - Engines MUST NOT change behavior without guide changes

If at any point you feel compelled to hardcode logic,
STOP and reassess the guide.

After reading, respond with ONE sentence only that summarizes:
- the current project phase
- what is completed
- what is the immediate priority

Do NOT implement anything.
Do NOT suggest new features.
Wait for explicit confirmation before taking any action.

If your work changes the project state, you must update docs/PROJECT_STATUS.md before committing.

---

## Expected Correct Summary (example)

"The project is in Phase 1 with the visual guide pipeline implemented; the
current priority is to ensure all test gates exist and pass before moving
to extraction or viewer-related work."

If the response does not mention Phase 1, test gates, or explicit rejection
behavior, STOP and correct understanding before proceeding.

---

## Rule

This prompt must be used:
- after a crash
- after starting a new session
- after switching machines
- after any loss of context