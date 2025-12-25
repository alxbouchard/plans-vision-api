# START_PROMPT — Claude Code (plans-vision-api)

This file contains the **authoritative startup prompt** to use when beginning  
**any new Claude Code session** on this repository.

**Use this prompt verbatim.  
Do not paraphrase.  
Do not skip steps.**

---

## Startup Prompt (COPY / PASTE)

You are working on the repository **plans-vision-api**.

---

## STEP 0 — ABSOLUTE RULE

Before doing **anything else**, you MUST:

1. Read `AGENTS.md` at the root of the repository  
2. Apply **all rules strictly and without interpretation**

If you disagree with any rule, STOP and ask for clarification.  
Do NOT implement work under disagreement.

---

## STEP 1 — Mandatory Reading Order (DO NOT SKIP)

You MUST read the following documents **in this exact order**.

### Core project state
- `docs/PROJECT_STATUS.md`
- `docs/SESSION_PLAYBOOK.md`
- `docs/RELEASE_CRITERIA.md`

### Architecture & framework
- `docs/SPEC.md`
- `docs/FEATURE_BuildGuide.md`
- `docs/FEATURE_ExtractObjects.md`

### MCAF & Decisions
- `docs/DECISIONS_Phase3_2_ProvisionalMode.md`
- `docs/DECISIONS_Phase3_3.md`
- `docs/DECISIONS_Render.md`

### Test & failure definitions
- `docs/TEST_GATES.md`
- `docs/TEST_GATES_PHASE3_3.md`
- `docs/ERRORS.md`
- `docs/ERRORS_PHASE3_3.md`

### Work planning
- `docs/WORK_QUEUE.md`
- `docs/WORK_QUEUE_PHASE3_3.md`
- `docs/WORK_QUEUE_PHASE3_RENDER.md`

---

## STEP 2 — MCAF (Mandatory Cognitive Architecture Framework)

This repository follows a **strict MCAF rule**.  
This is **non-negotiable**.

### Core principles

1. **NO business logic is ever hardcoded**
   - No keyword lists
   - No exclusion lists
   - No semantic assumptions
   - No pattern rules in code

2. **The Visual Guide is the SINGLE source of intelligence**
   - All semantic understanding comes from the guide
   - The guide may contain machine-readable payloads
   - Code executes payloads, never interprets meaning

3. **Engines are pure executors**
   - SpatialRoomLabeler
   - Detectors
   - Pairing logic  
   These components are **data-driven only**

4. **Missing rules MUST fail silently and observably**
   - `rooms_emitted = 0` is valid behavior
   - Logs MUST explain why
   - Tests MUST cover this case

5. **Tests define truth**
   - Tests must NOT be modified to “fit” new logic
   - If tests break, assume an architectural violation first

6. **Guide evolution is allowed**
   - Guide schema MAY evolve
   - Guide payloads MAY expand
   - Engines MUST NOT change behavior without guide changes

⚠️ If at any point you feel compelled to hardcode logic:  
**STOP. Reassess the guide.**

---

## STEP 3 — Phase Awareness (CRITICAL)

You MUST identify the current phase **before any work**.

### Current known state

- **Phase 3.3 – Spatial Room Labeling**
  - VALIDATED
  - TEST-GATED
  - FROZEN

Governed by:
- `docs/DECISIONS_Phase3_3.md`
- `tests/test_phase3_3_gates.py`

### Frozen components (DO NOT MODIFY without RFC)
- `SpatialRoomLabeler`
- Phase 3.3 payload schema
- Phase 3.3 test gates
- Phase 3.3 failure behavior

Any change to these requires:
- An explicit RFC
- Updated decisions
- New test gates

---

## STEP 4 — Mandatory Initial Response

After reading **everything above**, you MUST respond with  
**ONE SINGLE SENTENCE ONLY** that includes:

- The **current project phase**
- What is **completed**
- What is the **immediate priority**

### Example (format only)

> “The project is in Phase 3.3 with spatial room labeling validated and frozen; the immediate priority is Phase 3 Render execution according to WORK_QUEUE_PHASE3_RENDER.md.”

❌ Do NOT implement anything  
❌ Do NOT suggest new features  
❌ Do NOT refactor  
❌ Do NOT optimize  

Wait for **explicit confirmation** before taking any action.

---

## STEP 5 — State Mutation Rule

If your work changes the project state in any way, you MUST:

1. Update `docs/PROJECT_STATUS.md`
2. Ensure test gates still pass
3. Commit documentation **before code**

---

## WHEN THIS PROMPT MUST BE USED

This prompt MUST be used:

- After a crash
- After starting a new session
- After switching machines
- After any loss of context
- After long pauses (>24h)

---

## Final Note

This repository is designed to **think before extracting**.

If something feels “obvious” to code, it probably belongs in the guide.

**Trust the guide.  
Trust the tests.  
Freeze engines.**