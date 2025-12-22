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

After reading, respond with ONE sentence only that summarizes:
- the current project phase
- what is completed
- what is the immediate priority

Do NOT implement anything.
Do NOT suggest new features.
Wait for explicit confirmation before taking any action.

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