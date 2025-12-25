# DOC_GATES — Règles de vérification documentaire (MCAF)

But
Rendre la phrase "la doc est à jour" testable et traçable.
On ne se fie pas à une promesse, on produit une preuve.

## Principes

1) On évite les chiffres hardcodés
Ne pas écrire "148+ tests" dans README.
Le nombre de tests change constamment. On le calcule.

2) "À jour" veut dire "vérifié"
Une doc est "à jour" uniquement si une vérification récente a été effectuée et enregistrée.

3) Les phases LOCKED ne changent pas
Quand une phase est LOCKED, on ne modifie pas son contenu sauf correction factuelle critique.
Les ajouts mineurs vont dans CHANGELOG.

## Définition "DOC UP TO DATE"

La doc est considérée "à jour" uniquement si les 4 éléments suivants sont vrais:

A) Tests exécutés
- Une commande pytest a été lancée
- Le résumé est enregistré (nombre de tests collectés, pass, skip, fail)

B) Résumé généré automatiquement
- Le script scripts/test_summary.sh a été exécuté
- Son output a été copié dans docs/DOC_STATUS.md

C) Traçabilité
- docs/DOC_STATUS.md contient:
  - Last verified at (date)
  - Commit hash HEAD
  - Test summary
  - Liste des fichiers docs vérifiés

D) Aucune promesse vague
- Interdit de répondre "oui tout est à jour" sans produire DOC_STATUS.md mis à jour.

## Workflow standard (agent)

1) Exécuter:
- scripts/test_summary.sh

2) Mettre à jour:
- docs/DOC_STATUS.md

3) Commit:
- "docs: verify documentation status"

4) Pousser sur main

## Notes

- Les tests d'intégration opt-in ne sont pas requis pour dire "doc à jour", mais doivent être mentionnés si skipped.
- Ne pas modifier README pour y mettre des chiffres de tests. Référencer le script.

Date: 2025-12-24
