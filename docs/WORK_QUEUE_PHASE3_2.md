# WORK_QUEUE Phase 3.2 Provisional Mode

Objectif
Implémenter le mode provisional_only pour continuer vers Phase 2 même si le guide stable est rejeté.

Tâches autorisées

1) Status model
- Ajouter un état "provisional_only" dans le statut projet.
- Ajuster /projects/{id}/status pour refléter rejected vs failed.

2) Extraction gating
- Autoriser /v2/projects/{id}/extract si has_provisional=true même si has_stable=false.
- Introduire un paramètre interne guide_source: stable|provisional.

3) Politique conservatrice
- En mode provisional:
  - relever les thresholds d'extraction
  - bloquer low confidence
  - améliorer ambiguïté query

4) API schemas V2
- Ajouter champs:
  - guide_source
  - confidence_policy
dans les réponses extract/status, index, query.

5) UI Reference Demo
- Step 4: afficher rejected stable correctement, débloquer Step 5.
- Step 5: afficher completed sur overall_status et afficher guide_source.

6) Tests
- Ajouter tests unitaires pour:
  - transition rejected -> provisional_only
  - extract autorisé
  - no low confidence in provisional
  - query ambiguity
- Ajouter tests UI gates si harness existe, sinon tests JS simples ou snapshot minimal.

7) Docs
- Mettre à jour docs/PROJECT_STATUS.md pour inclure Phase 3.2.
- Mettre à jour README.md section demo si nécessaire.

Interdits
- Modifier les seuils stable_ratio ou la logique stable existante.
- Ajouter des règles sémantiques hardcodées (ex: "CLASSE => room").
- Ajouter des endpoints nouveaux sauf validation explicite.

Date: 2025-12-24
