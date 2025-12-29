# WORK_QUEUE_PHASE3_7_SEMANTIC.md

## Objectif

Réduire drastiquement les faux positifs rooms sans perdre les vrais locaux.
Définir un JSON final stable destiné au RAG (rooms et doors fiables).

**Contrainte MCAF absolue:**
- Aucun changement au moteur SpatialRoomLabeler (FROZEN)
- Aucun hardcode de mots à filtrer dans le code
- Tout le raffinement se fait via le Visual Guide (payloads + règles déclaratives)
- On ne "répare" pas en changeant le code si la sémantique est mauvaise, on améliore le guide

## Baseline (Phase 3.5)

| Fixture | Tokens | Rooms Emitted | Observation |
|---------|--------|---------------|-------------|
| addenda_page_1 | 2779 | 296 | Beaucoup de faux positifs (ABOVE, BELOW, mots fonctionnels) |
| test2_page6 | 1170 | 510 | Codes équipements confondus avec rooms |

## Nouveaux Payloads Autorisés (Phase 3.7)

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

### 2. Context Rules (co-occurrence)

```json
{
  "kind": "context_rule",
  "rule_type": "require_nearby_number",
  "token_type": "room_name",
  "max_distance_px": 100,
  "confidence_boost": 0.3,
  "reason": "room_labels_have_numbers"
}
```

Le guide observe que les vrais locaux ont généralement un numéro à proximité.

### 3. Zone Exclusion (layout-based)

```json
{
  "kind": "zone_exclude",
  "zone_type": "title_block",
  "bbox_hint": "bottom_right_corner",
  "reason": "title_blocks_not_rooms"
}
```

Le guide observe que certaines zones (title block, légende, bordereau) ne contiennent pas de locaux.

### 4. Must Be Inside Closed Region (optionnel)

```json
{
  "kind": "spatial_constraint",
  "constraint_type": "inside_closed_region",
  "applies_to": "room_name",
  "confidence_required": 0.7,
  "reason": "rooms_are_enclosed_spaces"
}
```

Uniquement si le guide l'observe et le décrit. Jamais hardcodé.

## Tickets Phase 3.7

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
- Ajouter logique dans `TokenBlockAdapter.create_blocks()` pour filtrer
- Log obligatoire: `tokens_excluded_count`, `exclude_reasons`

**Gate:** Sur addenda_page_1, `tokens_excluded > 0` quand exclude payloads présents

### Ticket 7.3: Context Rule - Require Nearby Number

**Objectif:** Réduire la confidence des room_name isolés (sans room_number proche).

**Implémentation:**
- Si `context_rule.require_nearby_number` et pas de number proche → confidence *= 0.5
- Toujours émettre mais avec confidence réduite

**Gate:** Sur addenda_page_1, rooms sans number ont confidence < 0.6

### Ticket 7.4: Zone Exclusion

**Objectif:** Exclure les tokens dans les zones non-plan (title block, légende).

**Implémentation:**
- GuideBuilder observe les zones récurrentes (coins, bordures)
- Génère payload `zone_exclude` avec bbox approximatif
- TokenBlockAdapter ignore les tokens dans ces zones

**Gate:** Sur addenda_page_1, aucun room dans title block zone

### Ticket 7.5: Validation E2E Semantic

**Objectif:** Valider que les faux positifs sont drastiquement réduits.

**Test:**
```python
def test_addenda_semantic_filtering():
    rooms = extract_rooms("addenda_page_1")
    assert len(rooms) > 0  # Pas de régression
    assert len(rooms) <= 40  # Plafond faux positifs

def test_test2_semantic_filtering():
    rooms = extract_rooms("test2_page6")
    assert len(rooms) > 0
    assert len(rooms) <= 80
```

## Gates (Non Discutables)

### GATE 7A - Addenda Semantic

| Metric | Baseline | Target | Justification |
|--------|----------|--------|---------------|
| rooms_emitted | 296 | > 0 AND <= 60 | Plafond réaliste pour une page |
| rooms_with_number | N/A | >= 70% | Vrais locaux ont un numéro |
| true_rooms_preserved | N/A | >= 90% | Pas de régression |

**Validation code:**
```python
def test_gate_7a_addenda():
    rooms = extract_rooms("addenda_page_1")
    assert len(rooms) > 0, "Regression: no rooms"
    assert len(rooms) <= 60, f"Too many rooms: {len(rooms)}"
    with_number = [r for r in rooms if r.room_number]
    ratio = len(with_number) / len(rooms)
    assert ratio >= 0.70, f"Only {ratio:.0%} have room_number"
```

### GATE 7B - Test2 Semantic

| Metric | Baseline | Target | Justification |
|--------|----------|--------|---------------|
| rooms_emitted | 510 | > 0 AND <= 150 | Plafond réaliste |
| rooms_with_number | N/A | >= 50% | Plan peut avoir labels mixtes |
| true_rooms_preserved | N/A | >= 90% | Pas de régression |

**Validation code:**
```python
def test_gate_7b_test2():
    rooms = extract_rooms("test2_page6")
    assert len(rooms) > 0, "Regression: no rooms"
    assert len(rooms) <= 150, f"Too many rooms: {len(rooms)}"
    with_number = [r for r in rooms if r.room_number]
    ratio = len(with_number) / len(rooms)
    assert ratio >= 0.50, f"Only {ratio:.0%} have room_number"
```

### GATE 7C - Zero Hardcode

```bash
# Ce grep doit retourner 0 résultats
grep -r "ABOVE\|BELOW\|TYP\|REFER" src/extraction/ --include="*.py" | grep -v "test\|#"
```

Toutes les exclusions proviennent du guide uniquement.

## Livrables

1. `docs/WORK_QUEUE_PHASE3_7_SEMANTIC.md` (ce fichier)
2. `tests/test_phase3_7_semantic_gates.py`
3. Mise à jour `docs/PROJECT_STATUS.md`
4. Mise à jour prompts GuideBuilder pour observer exclusions

## Stop Conditions

- Si un ticket nécessite de modifier SpatialRoomLabeler: STOP, RFC
- Si une exclusion doit être hardcodée: STOP, ajouter au guide
- Si les gates ne passent pas après 3 itérations: STOP, revoir la stratégie guide

## Ordre d'Exécution

1. Ticket 7.1 (GuideBuilder exclude)
2. Ticket 7.2 (TokenBlockAdapter exclude)
3. Valider GATE 7C (zero hardcode)
4. Ticket 7.3 (context rules)
5. Ticket 7.4 (zone exclusion)
6. Valider GATE 7A et 7B (semantic filtering)
7. Ticket 7.5 (E2E validation)

## Définition de Done

- [ ] GATE 7A: addenda_page_1 rooms_emitted <= 40
- [ ] GATE 7B: test2_page6 rooms_emitted <= 80
- [ ] GATE 7C: grep hardcode = 0
- [ ] Tous les vrais locaux préservés
- [ ] JSON stable pour RAG
