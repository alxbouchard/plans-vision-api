# TEST_GATES_PHASE3_3.md

Gate 1 Room vs Door disambiguation (synthetic)
Fixture must contain:
- Room label block: "CLASSE 203" (or equivalent label with a 2 to 4 digit token)
- Door number: "203" near a door
- Door number: "203-1" near a door
Expected:
- room_number 203 emitted as room OR ambiguity true with reason, but never silent empty
- door_number 203 and 203-1 emitted as doors
- no conflation of door numbers as rooms

Gate 2 No hardcoded semantics
- Static grep test: no forbidden keyword list introduced in code logic
- Allowed: keywords may appear in test fixtures only

Gate 3 Feature flag safety
- With flag false: identical behavior and no extra model calls
- With flag true: detector called only on plan pages

Gate 4 Persistence
- After extract, overlay returns page_type and objects via DB, not in memory only

Gate 5 E2E query
- After extract, query room_number 203 returns:
  - matches length >= 1 OR ambiguous true
  - message explains ambiguity when ambiguous true

Pass criteria
All gates must pass in CI with OPENAI_API_KEY=dummy (unit tests).
Integration tests that require a real key must be opt in via RUN_INTEGRATION=1.
