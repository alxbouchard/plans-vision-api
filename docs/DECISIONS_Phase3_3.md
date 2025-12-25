# DECISIONS_Phase3_3.md

Decision 1 No keyword semantics
We do not use language keywords (example: CLASSE) to infer room vs door.
We rely on measurable evidence: geometry neighborhood and token patterns.

Decision 2 Ambiguity is a first class outcome
If the system cannot prove a label is a room, it returns ambiguity true instead of guessing.

Decision 3 Minimal vision usage
We add at most one additional vision call per plan page for text block detection, behind a feature flag.

Decision 4 Internal fields allowed
We may add internal fields to ExtractedRoom for better reasoning (label_bbox, ambiguity).
Public API v2 response stays unchanged until explicit approval.

Decision 5 Provisional mode boosts recall carefully
In provisional_only mode we can relax thresholds but only for explicitly labeled objects.
