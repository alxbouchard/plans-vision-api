# TICKET: Tokens-First GuideBuilder (PyMuPDF Priority)

**Status: PARTIAL — B/C/D/E COMPLETE, Step A BLOCKED**
**Created: 2025-12-29**
**Updated: 2025-12-29**

## Context

Le consolidator refuse correctement de générer des payloads quand Vision ne peut pas lire les room labels à 150-200 DPI. C'est un signal MCAF correct: on ne devine pas.

Mais PyMuPDF peut extraire parfaitement le texte vectoriel du PDF:
- 43 room names: CHAUFFERIE, CLASSE, CORRIDOR, VESTIBULE...
- 301 room numbers: 110, 118, 121, 122, 127...
- Paires validées par proximité: CHAUFFERIE+110 (11px), TÉLÉCOM+122 (12px)

## Decision

1. Dès qu'un PDF vectoriel est disponible, l'analyse utilise PyMuPDF tokens-first
2. Vision = fallback si PDF sans texte, ou pour éléments non-textuels
3. Le bruit (ex: "05" répété 50x) est géré par le guide via `exclude` payload, pas hardcodé

## Implementation Steps

### A) PDF Storage Association

Permettre d'associer chaque page PNG à sa page PDF source.

Options:
1. Upload PDF entier → extraction automatique des pages PNG
2. Stocker `pdf_path` + `pdf_page_index` sur chaque Page entity

**Choix recommandé**: Option 1 (upload PDF → pages PNG auto)

### B) TokenProvider Interface

```python
class TokenProvider(Protocol):
    def extract_tokens(self, page_source: PageSource) -> list[TextToken]

@dataclass
class TextToken:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    font_size: float
    page_index: int
```

Implémentations:
- `PyMuPDFTokenProvider` - prioritaire si PDF disponible
- `VisionOCRTokenProvider` - fallback

### C) Token Summary for GuideBuilder

Le GuideBuilder reçoit un résumé structuré (pas tous les tokens):

```json
{
  "token_summary": {
    "total_text_blocks": 2779,
    "room_name_candidates": [
      {"text": "CLASSE", "count": 8, "example_bbox": [1264, 751, 1271, 776]},
      {"text": "CORRIDOR", "count": 3, "example_bbox": [1229, 515, 1236, 551]},
      {"text": "CHAUFFERIE", "count": 1, "example_bbox": [1469, 401, 1476, 441]}
    ],
    "room_number_candidates": [
      {"text": "132", "count": 1, "near_name": "CLASSE", "distance_px": 15},
      {"text": "110", "count": 1, "near_name": "CHAUFFERIE", "distance_px": 11}
    ],
    "high_frequency_numbers": [
      {"text": "05", "count": 47, "note": "likely wall/partition code"}
    ],
    "pairing_pattern": {
      "observed_relation": "number_below_name",
      "typical_distance_px": 10-20,
      "confidence": "high"
    }
  }
}
```

### D) GuideBuilder Prompt Update

Ajouter dans `guide_builder_user.txt`:

```
## Text Tokens (from PDF vector layer)

The following text tokens were extracted from the PDF:
{token_summary}

Use this information to:
1. Confirm room_name patterns (uppercase words like CLASSE, CORRIDOR)
2. Confirm room_number patterns (2-4 digit numbers near names)
3. Identify pairing relationship (position: below, right, etc.)
4. Identify exclude candidates (high-frequency codes like "05" = wall type)
```

### E) Exclude Payload via Observation

Le guide observe que "05" apparaît 47 fois → génère un payload exclude:

```json
{
  "kind": "exclude",
  "pattern": "^0[0-9]$",
  "reason": "High-frequency code (47 occurrences), likely wall/partition identifier"
}
```

## Files to Modify

1. `src/models/entities.py` - Add `pdf_path`, `pdf_page_index` to Page
2. `src/storage/file_storage.py` - PDF storage support
3. `src/extraction/token_provider.py` - New file: TokenProvider interface
4. `src/extraction/pymupdf_token_provider.py` - New file: PyMuPDF implementation
5. `src/agents/guide_builder.py` - Accept token_summary parameter
6. `src/agents/prompts/guide_builder_user.txt` - Add token_summary section
7. `src/pipeline/orchestrator.py` - Inject token_summary into GuideBuilder

## Files NOT to Modify

- `src/extraction/spatial_room_labeler.py` (FROZEN)
- `src/agents/schemas.py` - RulePayload schema (FROZEN for Phase 3.7 v1)

## Acceptance Criteria

1. Upload Addenda PDF page 1
2. POST /analyze
3. Assert:
   - status = "validated"
   - stable_rules_json contains 3 payloads (room_name, room_number, pairing)
   - At least 1 exclude payload present (for high-frequency codes)
4. POST /extract with ENABLE_PHASE3_3_SPATIAL_LABELING=true
5. Assert: rooms_emitted > 0

## Success Metric

Addenda page 1 produces valid guide WITHOUT increasing Vision DPI.

---

## Progress (2025-12-29)

### ✅ Step B: TokenProvider Interface — COMPLETE
- Already exists in `src/extraction/tokens.py`
- `PyMuPDFTokenProvider` extracts text tokens from PDF
- `VisionTokenProvider` as fallback
- `get_tokens_for_page()` main entry point

### ✅ Step C: Token Summary — COMPLETE
- Created `src/extraction/token_summary.py`
- `generate_token_summary()` produces structured summary
- Identifies room_name candidates, room_number candidates
- Detects high-frequency codes (potential noise)
- Detects pairing patterns
- 14 tests passing in `tests/test_token_summary.py`

### ✅ Step D: GuideBuilder Prompt — COMPLETE
- Updated `src/agents/prompts/guide_builder_user.txt` with `{token_summary_section}`
- Updated `src/agents/prompts.py` to inject token summary into prompt
- Updated `src/agents/guide_builder.py` to accept `token_summary` parameter
- Updated `src/pipeline/orchestrator.py` to extract tokens and pass summary

### ✅ Step E: Exclude Payload — COMPLETE
- Updated prompt to guide model to observe high-frequency codes
- Model can generate `RULE_0XX_EXCLUDE` for patterns like `^0[0-9]$`

### ⏸️ Step A: PDF Storage Association — BLOCKED
**REQUIRES MIGRATION TICKET**

Changes needed:
- Add `pdf_path` and `pdf_page_index` to Page entity
- Add columns to PageTable in database.py
- Need migration script for existing DBs
- Need non-regression test

Current workaround: `pdf_path` can be passed explicitly to `orchestrator.run()`.

### Tests
- `tests/test_tokens_first_validation.py`: 5 tests validating PyMuPDF extraction
- All 37 related tests passing
