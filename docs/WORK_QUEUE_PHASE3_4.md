# WORK_QUEUE_PHASE3_4.md
# Single Page Room Extraction

## Objectif

Rendre l'API capable de comprendre UNE seule page de plan et d'extraire des rooms de façon fiable, sans hardcode, en respectant MCAF.
Le multi-page doit seulement augmenter la confiance, pas être requis pour que ça marche.

## Contexte figé

Phase 3.3 est FERMÉE et GELÉE.

Interdiction totale de modifier:
- SpatialRoomLabeler
- RulePayload schema Phase 3.3 existant
- tests/test_phase3_3_gates.py
- Decision 6/7/8 dans docs/DECISIONS_Phase3_3.md

## Payloads Phase 3.3 (référence)

```json
1. token_detector(room_name)
   pattern: "[A-Z]{2,}"
   min_len: 2

2. token_detector(room_number)
   pattern: "\\d{2,4}"
   must_be_boxed: false

3. pairing
   relation: "below"
   max_distance_px: 100
```

## Interdictions MCAF

- Aucune liste de mots (CLASSE, CORRIDOR, BUREAU, etc.)
- Aucune exclusion list hardcodée
- Aucune logique "arc = door", "carré = fenêtre" dans le code
- Si règle manque → échec observable, pas invention

---

## Tickets

### Ticket 1 — GuideBuilder: observations room_number et pairing systématiques

**But**: Sur une seule page, forcer la collecte d'évidence room_number et pairing au même niveau que room_name.

**Action**: Modifier guide_builder_user.txt pour exiger explicitement:
- Observations room_number (minimum 2)
- Observation relation spatiale room_name ↔ room_number
- Pas de hardcode, seulement patterns visuels et exemples vus

**Critère**: Le GuideBuilder produit systématiquement les 3 types d'observations quand visibles.

---

### Ticket 2 — GuideApplier: payload_validations dans output JSON

**But**: Validation explicite des payloads sur chaque page.

**Action**: Ajouter dans le schema de sortie GuideApplier:

```json
"payload_validations": [
  {"kind": "token_detector", "token_type": "room_name", "status": "confirmed|contradicted|not_applicable", "evidence": "..."},
  {"kind": "token_detector", "token_type": "room_number", "status": "confirmed|contradicted|not_applicable", "evidence": "..."},
  {"kind": "pairing", "status": "confirmed|contradicted|not_applicable", "evidence": "..."}
]
```

**Règle clé**: Si la page contient visiblement des labels de locaux mais que le guide n'a pas les 3 payloads → `overall_consistency: "inconsistent"` + observations de correction.

---

### Ticket 3 — GuideConsolidator: règle spéciale Phase 3.4

**But**: Ne pas exclure room_number/pairing juste parce que score < 0.8 sur single page.

**Action**: Modifier guide_consolidator_user.txt:
- Si room labels visibles ET observations room_name/room_number/pairing présentes → produire les 3 payloads en stable_rules
- Stabilité moyenne acceptable (>= 0.5) pour ces 3 payloads spécifiques
- Si évidence vraiment absente → rejection_reason clair + log missing_required_payloads

---

### Ticket 4 — Test Gates Phase 3.4

**Fichier**: tests/test_phase3_4_single_page_gates.py

#### GATE A — Single page guide payloads

```
Given: 1 plan page PNG avec labels visibles
When: analyze
Then: stable_rules_json contient exactement:
  - token_detector(room_name)
  - token_detector(room_number)
  - pairing(room_name ↔ room_number)
Else: FAIL
```

#### GATE B — Payload validations

```
Given: same page
When: apply guide
Then: payload_validations contient 3 entrées (confirmed ou contradicted)
  - Pas de silence, pas de null
Else: FAIL
```

#### GATE C — Extraction on single page

```
Given: same project
When: extract avec ENABLE_PHASE3_3_SPATIAL_LABELING=true
Then: rooms_emitted > 0 sur cette page
Else: FAIL
```

---

### Ticket 5 — Robustesse DPI

**But**: Le système doit fonctionner indépendamment du DPI d'export.

**Test**:
- Exporter même PDF à 150 dpi et 300 dpi
- Les deux doivent passer GATE C
- rooms_emitted peut varier mais jamais tomber à 0

---

## Procédure de dev

1. Travailler ticket par ticket
2. Après chaque ticket: tests ciblés, commit
3. Mettre à jour docs/PROJECT_STATUS.md à chaque changement d'état

## Définition de terminé

Phase 3.4 est terminée quand:
- GATE A passe (single page → 3 payloads)
- GATE B passe (payload_validations présentes)
- GATE C passe (rooms_emitted > 0)
- DPI gate passe (150 dpi et 300 dpi)

## Si blocage

Arrêter et proposer un RFC, pas un workaround.
