# Test Gates Master

## Phase 3.3 (locaux)
Source: tests/test_phase3_3_gates.py

GATE A Guide payloads persisted
- stable_rules_json contient:
  - token_detector(room_name)
  - token_detector(room_number)
  - pairing(room_name <-> room_number)

GATE B Payloads loaded
- logs: phase3_3_guide_payloads_loaded
- payloads_count >= 3

GATE C Rooms emitted
- sur au moins une page plan
- rooms_emitted > 0

## Règle
Si un gate échoue:
- pas de contournement
- pas de hardcode
- corriger à la source autorisée (souvent prompts ou guide)
