# AGENTS.md — Rules for AI Development Agents

This repository is governed by strict rules.
Any AI agent working in this repo MUST follow them.

This file is the highest authority for development behavior.

---

## Core Principles (Non-Negotiable)

1. Nothing is hardcoded.
2. Nothing is guessed.
3. A rule exists only if it is visually observed.
4. Unstable or contradictory rules MUST be rejected.
5. Saying "I don't know" is a valid and correct outcome.

Violating any of these principles is a bug.

---

## Output Discipline (Critical)

- All agent outputs MUST be valid JSON.
- Outputs MUST conform to the declared Pydantic schemas.
- Free-form prose outside JSON is forbidden.
- Heuristic parsing of text is forbidden.

If a model output cannot be validated by schema, the pipeline MUST fail loudly.

---

## Validation Rules

- Single-page projects produce provisional guides only.
- Multi-page projects require cross-page validation.
- Any contradiction invalidates the affected rule.
- If no stable rules remain, guide generation MUST be refused.

Refusing to produce a result is a correct and expected outcome.

---

## Development Workflow (Mandatory)

All work MUST follow this order:

1. Read AGENTS.md
2. Read docs/PROJECT_STATUS.md
3. Read the relevant docs/FEATURE_*.md
4. Write or update tests FIRST
5. Run pytest
6. Implement until all tests pass
7. Commit

No commit is allowed if tests are failing.

---

## Project State Updates (MANDATORY)

After completing any task that:
- changes observable behavior
- adds, removes, or closes a test gate
- modifies refusal or validation logic
- advances or locks a project phase

The agent MUST:

1. Update docs/PROJECT_STATUS.md
2. Summarize changes in 2–3 bullet points
3. Commit the status update together with the code changes

If no project-level behavior changed, DO NOT update PROJECT_STATUS.md.

Failure to update the project state when required is a bug.

---

## Forbidden Practices

- Parsing model output using string matching
- Inferring semantics from symbols without legend validation
- Silently degrading output quality
- Adding UI or viewer assumptions
- Implementing Phase 2 features during Phase 1

If unsure whether something is allowed, STOP and ASK.

---

## Definition of Success

A change is successful only if:

- All tests pass
- All outputs are schema-valid
- Errors are explicit and documented
- The project state is accurate
- Scope was not expanded unintentionally

---

## Final Rule

When in doubt:
- Do not guess
- Do not invent
- Do not expand scope
- Ask before implementing

## Autonomous Execution Mode

When explicitly enabled by the human, the agent is allowed to:

- Execute a sequence of tasks without stopping for confirmation
- Continue working across commits within the same phase
- Self-assign the next task ONLY if it is explicitly allowed by:
  - docs/PROJECT_STATUS.md
  - the current FEATURE doc
  - docs/TEST_GATES.md

The agent MUST stop and wait for human input if:
- A task would move the project to a new phase
- A task would expand scope
- A task is not clearly allowed by the current phase documents

When Autonomous Execution Mode is enabled, the agent MUST:
1. State the task it is starting
2. Execute it fully (tests → implementation → tests)
3. Commit the result
4. Update docs/PROJECT_STATUS.md if the state changed
5. Automatically proceed to the next allowed task