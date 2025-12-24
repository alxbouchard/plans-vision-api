# FEATURE Phase 3.2 Provisional Mode

Objectif
Permettre au pipeline PDF-first de continuer vers l'extraction (Phase 2) et les requêtes (Query) même quand le guide stable (Phase 1) est rejeté, tant qu'un guide provisoire existe.

Principe
- Le guide stable sert à définir des conventions inter-pages robustes.
- Un petit set de pages (ex: addenda de 3 pages) peut être exploitable pour retrouver un élément précis, même si les conventions ne sont pas suffisamment stables entre pages.
- On introduit un état explicite "provisional_only" qui autorise l'extraction en mode conservateur.

Définitions
- Guide provisoire: sortie JSON du Guide Builder sur la page 1.
- Guide stable: guide final consolidé basé sur règles STABLE.
- Rejet stable: le système refuse de produire un guide stable (ratio stable insuffisant), mais le provisoire existe.
- Provisional Mode: mode d'extraction autorisé quand stable rejeté mais provisoire disponible.

Invariants
- Rien n'est hardcodé.
- Aucun choix arbitraire en cas d'ambiguïté.
- Les sorties doivent indiquer clairement si elles proviennent d'un guide stable ou provisoire.
- Le renderer V3 reste pur: zéro appel modèle.

Changements attendus
1) Phase 1 status
- Ajouter un statut explicite quand le guide stable est rejeté mais un provisoire existe.
- Exemple: project.status = "provisional_only"
- Conserver les champs:
  - has_provisional = true
  - has_stable = false
  - rejection_reason (pour le stable)

2) Autorisation Phase 2 extract
- Autoriser /v2/projects/{id}/extract si:
  - has_stable_guide = true
  - OU has_provisional_guide = true (provisional_only)
- Dans le cas provisional_only:
  - Exécuter extraction avec seuils conservateurs
  - Marquer provenance et risque:
    - guide_source = "provisional"
    - confidence_policy = "conservative"
    - results_confidence_floor = "medium" (pas de low)

3) Query
- Query doit fonctionner même si extraction a été faite en provisional_only.
- Les résultats doivent inclure:
  - guide_source: stable|provisional
  - ambiguous: true|false
  - ambiguity_reason si ambiguous=true
  - object_kind: room|door|schedule_item|unknown

4) UI Reference Demo
- Step 4 doit afficher:
  - "Stable guide rejected, provisional guide available"
  - et débloquer Step 5 Extract.
- Step 5 doit afficher la provenance:
  - "Extract completed (provisional mode)" ou "Extract completed (stable mode)"

5) Error UX
- Ne pas afficher "Unknown error" quand stable est rejeté.
- Afficher une explication simple:
  - "Guide stable non généré car les conventions ne sont pas assez stables entre pages. Extraction possible en mode provisoire, résultats conservateurs."

API impact
- Aucun nouvel endpoint requis.
- Ajustements des réponses existantes:
  - /projects/{id}/status
  - /projects/{id}/guide
  - /v2/projects/{id}/extract/status
  - /v2/projects/{id}/index
  - /v2/projects/{id}/query

Definition of Done
- Un projet addenda 3 pages peut:
  - Upload PDF, Build mapping, Analyze
  - Obtenir status "provisional_only" au lieu de failed
  - Lancer Extract et obtenir un index non vide quand c'est possible
  - Faire Query "203" et obtenir au moins un match ou ambiguous=true
- Tous les gates définis dans docs/TEST_GATES_PROVISIONAL.md passent.
- Aucune régression sur le mode stable.
- UI Reference Demo reflète correctement l'état provisional_only.

Date: 2025-12-24
