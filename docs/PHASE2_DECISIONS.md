# PHASE2_DECISIONS — Locked choices for bulletproof implementation

These decisions remove ambiguity for the agent.

## Output geometry
- Phase 2.0 outputs bbox only
- Polygon is optional and must not block Phase 2.0

## Page types
- Page classification is mandatory and gates downstream extraction

## Stability and guide usage
- If stable guide exists, use it as primary support
- If only provisional guide exists, allow extraction but mark outputs provisional_only and lower confidence

## Safety defaults
- Prefer false negatives over false positives
- Never infer semantics not supported by guide or legible legend
- When multiple candidates exist, return ambiguous

## IDs
- Object IDs must be deterministic for the same page content
- Use stable hashing of page_id plus normalized label and geometry buckets

## Versioning
- schema_version for v2 is 2.0
- v1 endpoints remain unchanged

## Performance
- Extraction must be asynchronous like Phase 1 analyze
- Status endpoint must report step progress

## Do not implement in Phase 2.0
- PDF out annotated
- Viewer UI
- Full wall vectorization
- Measurement and dimensions
