# AGENTS.md Rules for AI Development Agents

This repository is governed by strict rules.
Any AI agent working in this repo MUST follow them.

## Core Principles

1. Nothing is hardcoded.
2. Nothing is guessed.
3. A rule exists only if it is visually observed.
4. Unstable or contradictory rules MUST be rejected.
5. Saying "I don't know" is a valid and correct outcome.

Violating any of these principles is a bug.

## Output Discipline

- All agent outputs MUST be valid JSON.
- Outputs MUST conform to the declared Pydantic schemas.
- Free form prose outside JSON is forbidden.
- Heuristic parsing of text is forbidden.

If a model output cannot be validated by schema, the pipeline MUST fail.

## Validation Rules

- Single page projects produce provisional guides only.
- Multi page projects require cross page validation.
- Contradictions MUST lead to rule invalidation.
- If no stable rules remain, guide generation MUST be refused.

## Development Workflow

- Tests are the source of truth.
- Write or update tests BEFORE implementing logic.
- Do not commit if tests fail.
- No new dependency without explicit justification.

## Forbidden Practices

- Parsing model output using string matching.
- Inferring semantics from symbols without legend validation.
- Silently degrading output quality.
- Adding UI logic or viewer assumptions.

## Definition of Success

A change is successful only if:
- All tests pass
- All outputs are schema valid
- Errors are explicit and traceable
