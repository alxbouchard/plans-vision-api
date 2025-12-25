# Project Map

## Pipelines
Analyze
- GuideBuilder
- GuideApplier
- SelfValidator
- GuideConsolidator (guide stable + payloads)

Extract
- Charge payloads du guide stable
- Exécute les moteurs gelés (ex: Phase 3.3 SpatialRoomLabeler)

Render
- Overlays / PDF master (selon API_CONTRACT_Render_v3)

## Où se trouve quoi
- src/agents/prompts: prompts
- src/agents/schemas.py: schémas (FinalRule, RulePayload)
- src/extraction: moteurs + pipeline
- src/pipeline/orchestrator.py: orchestration analyse + persistance
- src/storage: DB + repositories

## Docs source officielle
- docs/PROJECT_STATUS.md
- docs/DECISIONS_*.md
- docs/TEST_GATES_*.md
- docs/API_CONTRACT_*.md
- docs/WORK_QUEUE*.md
