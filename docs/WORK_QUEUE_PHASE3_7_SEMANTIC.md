# WORK_QUEUE_PHASE3_7_SEMANTIC.md

## Objectif

Réduire drastiquement les faux positifs rooms sans perdre les vrais locaux.
Définir un JSON final stable destiné au RAG (rooms et doors fiables).

**Contrainte MCAF absolue:**
- Aucun changement au moteur SpatialRoomLabeler (FROZEN)
- Aucun hardcode de mots à filtrer dans le code
- Tout le raffinement se fait via le Visual Guide (payloads + règles déclaratives)
- On ne "répare" pas en changeant le code si la sémantique est mauvaise, on améliore le guide

## Constraint: RuleKind is FROZEN

**Phase 3.7 v1 utilise UNIQUEMENT les RuleKind existants:**
- `token_detector` - Detect tokens (room_name, room_number)
- `pairing` - Pair name and number tokens
- `exclude` - Exclude patterns from room_name detection

**INTERDIT en Phase 3.7 v1:**
- Pas de nouveau payload kind (context_rule, zone_exclude, spatial_constraint)
- Tout nouveau kind = RFC + changement de schéma
- Ces features sont reportées à Phase 3.7 v2 si nécessaire

## Baseline (Phase 3.5)

| Fixture | Tokens | Rooms Emitted | Observation |
|---------|--------|---------------|-------------|
| addenda_page_1 | 2779 | 296 | Beaucoup de faux positifs (ABOVE, BELOW, mots fonctionnels) |
| test2_page6 | 1170 | 510 | Codes équipements confondus avec rooms |

## Payloads Autorisés (Phase 3.7 v1)

### 1. Exclude Token Patterns (déclaratifs)

```json
{
  "kind": "exclude",
  "token_type": "room_name",
  "detector": "regex",
  "pattern": "ABOVE|BELOW|TYP|SEE|REFER|NOTE",
  "reason": "functional_annotation"
}
```

Le guide observe que certains mots majuscules sont des annotations fonctionnelles, pas des noms de locaux.

### 2. Token Detector (existant)

```json
{
  "kind": "token_detector",
  "token_type": "room_name",
  "detector": "regex",
  "pattern": "[A-Z]{2,}",
  "min_len": 2
}
```

### 3. Pairing (existant)

```json
{
  "kind": "pairing",
  "name_token": "room_name",
  "number_token": "room_number",
  "relation": "below",
  "max_distance_px": 200
}
```

## Tickets Phase 3.7 v1

### Ticket 7.1: Exclude Patterns dans GuideBuilder

**Objectif:** Le GuideBuilder observe les mots fonctionnels et génère des payloads `exclude`.

**Implémentation:**
- Modifier le prompt GuideBuilder pour observer les annotations récurrentes
- Générer des payloads `kind=exclude` pour les patterns observés
- Ne PAS hardcoder de liste - le guide doit observer

**Gate:** Guide produit au moins 1 payload `exclude` sur addenda_page_1

### Ticket 7.2: TokenBlockAdapter respecte Exclude

**Objectif:** Le TokenBlockAdapter filtre les tokens qui matchent un payload `exclude`.

**Implémentation:**
- Logique dans `TokenBlockAdapter.create_blocks()` pour filtrer (DÉJÀ FAIT)
- Log obligatoire: `excluded_by_rule`, `excluded_reasons`

**Gate:** Sur addenda_page_1, `excluded_by_rule > 0` quand exclude payloads présents

### Ticket 7.3: Tests E2E Gates

**Objectif:** Valider que les gates passent après exclude payloads.

**Test:**
```python
def test_gate_7a_addenda():
    rooms = extract_rooms("addenda_page_1")
    assert len(rooms) > 0, "Regression: no rooms"
    assert len(rooms) <= 60, f"Too many rooms: {len(rooms)}"
    with_number = [r for r in rooms if r.room_number]
    ratio = len(with_number) / len(rooms)
    assert ratio >= 0.70, f"Only {ratio:.0%} have room_number"

def test_gate_7b_test2():
    rooms = extract_rooms("test2_page6")
    assert len(rooms) > 0, "Regression: no rooms"
    assert len(rooms) <= 150, f"Too many rooms: {len(rooms)}"
    with_number = [r for r in rooms if r.room_number]
    ratio = len(with_number) / len(rooms)
    assert ratio >= 0.50, f"Only {ratio:.0%} have room_number"
```

## Gates (Non Discutables)

### GATE 7A - Addenda Semantic

| Metric | Baseline | Target | Justification |
|--------|----------|--------|---------------|
| rooms_emitted | 296 | > 0 AND <= 60 | Plafond réaliste pour une page |
| rooms_with_number | N/A | >= 70% | Vrais locaux ont un numéro |

**Validation script:** `python scripts/phase3_7_gate_check.py`

### GATE 7B - Test2 Semantic

| Metric | Baseline | Target | Justification |
|--------|----------|--------|---------------|
| rooms_emitted | 510 | > 0 AND <= 150 | Plafond réaliste |
| rooms_with_number | N/A | >= 50% | Plan peut avoir labels mixtes |

**Validation script:** `python scripts/phase3_7_gate_check.py`

### GATE 7C - Zero Hardcode

```bash
# Ce grep doit retourner 0 résultats
# Cherche des listes hardcodées de mots à exclure dans src/extraction/
grep -rE 'EXCLUDED_WORDS|STOPWORDS|BLACKLIST|ROOM_EXCLUDES|"\bABOVE\b"|"\bBELOW\b"|"\bTYP\b"|"\bREFER\b"' src/extraction/ --include="*.py"
```

Toutes les exclusions proviennent du guide uniquement.
Les patterns comme `[A-Z]{2,}` dans les payloads sont OK car ils viennent du guide.

## Future (Phase 3.7 v2 - si nécessaire)

Ces features sont reportées et nécessitent un RFC:

- `context_rule` - Require nearby number
- `zone_exclude` - Title block exclusion
- `spatial_constraint` - Must be inside closed region
- Golden set pour valider "true_rooms_preserved >= 90%"

## Livrables Phase 3.7 v1

1. `docs/WORK_QUEUE_PHASE3_7_SEMANTIC.md` (ce fichier)
2. `scripts/phase3_7_gate_check.py` (FAIT)
3. Mise à jour prompts GuideBuilder pour observer exclusions
4. `tests/test_phase3_7_gates.py`

## Stop Conditions

- Si un ticket nécessite de modifier SpatialRoomLabeler: STOP, RFC
- Si une exclusion doit être hardcodée: STOP, ajouter au guide
- Si un nouveau RuleKind est nécessaire: STOP, RFC Phase 3.7 v2
- Si les gates ne passent pas après 3 itérations: STOP, revoir la stratégie guide

## Ordre d'Exécution

1. Ticket 7.1 (GuideBuilder exclude)
2. Ticket 7.2 (TokenBlockAdapter exclude) - DÉJÀ FAIT
3. Valider GATE 7C (zero hardcode)
4. Ticket 7.3 (E2E tests)
5. Valider GATE 7A et 7B

## Définition de Done

- [ ] GATE 7A: addenda_page_1 rooms_emitted <= 60, rooms_with_number >= 70%
- [ ] GATE 7B: test2_page6 rooms_emitted <= 150, rooms_with_number >= 50%
- [ ] GATE 7C: grep hardcode = 0
- [ ] Guide génère au moins 1 exclude payload
- [ ] Logs contiennent excluded_by_rule et excluded_reasons
