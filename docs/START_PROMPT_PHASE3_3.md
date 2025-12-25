# START_PROMPT_PHASE3_3.md

Read AGENTS.md and apply rules strictly.

Then read:
- docs/PROJECT_STATUS.md
- docs/WORK_QUEUE_PHASE3_3.md
- docs/FEATURE_Phase3_3_SpatialRoomLabeling.md
- docs/TEST_GATES_PHASE3_3.md
- docs/DECISIONS_Phase3_3.md

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

After reading, respond with one sentence:
- current phase
- what is completed
- immediate priority

Then wait.

When approved to implement:
- Work ticket by ticket in WORK_QUEUE_PHASE3_3.md order
- After each ticket: run targeted tests, then commit
- Do not change public API schemas unless explicitly asked


