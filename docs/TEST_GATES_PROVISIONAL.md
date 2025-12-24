# TEST_GATES Phase 3.2 Provisional Mode

But
Garantir que le pipeline continue de façon contrôlée quand le guide stable est rejeté.

Gate P1  Stable rejeté mais provisoire existe
- Condition: Analyze produit has_provisional=true, has_stable=false, stable rejected
- Attendu:
  - status returned is "provisional_only" (pas failed)
  - rejection_reason présent

Gate P2  Extract autorisé en provisional_only
- Condition: project.status="provisional_only"
- Attendu:
  - POST /v2/projects/{id}/extract retourne 202 et complète
  - extract/status indique guide_source="provisional"

Gate P3  Politique conservatrice respectée
- Attendu:
  - aucun objet avec confidence_level=LOW
  - si doute, objet non produit ou marqué ambiguous au niveau query

Gate P4  Query fonctionne
- Condition: extraction completed en provisional_only
- Attendu:
  - GET /v2/projects/{id}/query?room_number=203 retourne:
    - soit matches >= 1
    - soit ambiguous=true avec ambiguity_reason
  - jamais de choix arbitraire

Gate P5  UI Step 4 ne montre pas Unknown error
- Attendu:
  - UI affiche "Stable guide rejected, provisional guide available"
  - UI débloque Step 5

Gate P6  UI Step 5 affiche completed
- Attendu:
  - UI lit overall_status et affiche completed
  - UI affiche provenance "provisional mode" si applicable

Gate P7  Pas de régression mode stable
- Condition: projet qui produit un guide stable
- Attendu:
  - status validated, has_stable=true
  - extraction fonctionne comme avant

Gate P8  Renderer inchangé
- Attendu:
  - V3 render gates existants passent
  - zéro appel modèle pendant render

Date: 2025-12-24
