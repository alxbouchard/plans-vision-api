# DECISIONS Phase 3.2 Provisional Mode

Décision 1
On introduit un état explicite "provisional_only" au lieu de traiter le rejet du guide stable comme un échec.

Motif
Le rejet stable correspond à un manque de stabilité inter-pages, pas à un document inutilisable.

Décision 2
En mode provisional_only, on autorise l'extraction Phase 2 mais avec une politique conservatrice:
- aucune extraction low confidence
- aucune interprétation sémantique non visible
- ambiguïté obligatoire si collisions (ex: 203 local vs 203 porte)

Décision 3
On ne modifie pas le seuil stable_ratio.
Le seuil reste un garde-fou.
On ajoute un chemin alternatif, explicite, pour les cas où stable est rejeté.

Décision 4
Le renderer V3 reste pur et indépendant.
Le mode provisional_only ne change rien au rendu PDF.

Décision 5
Aucune nouvelle route.
On modifie uniquement des statuts et des champs de réponse.
Ceci limite le scope et évite de casser les clients.

Décision 6
La UI Reference Demo est un consommateur passif.
Elle doit afficher les statuts correctement et ne pas deviner.

Date: 2025-12-24
