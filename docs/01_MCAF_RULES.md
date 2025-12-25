# MCAF Rules
Non négociable.

## 1. Zéro hardcode de logique métier
Interdit:
- listes de mots
- listes d’exclusion
- heuristiques sémantiques cachées
- patterns “magiques” en code

## 2. Le Visual Guide est la seule intelligence
- Le guide peut contenir des payloads machine exécutables
- Le code exécute des payloads, il n’interprète pas du texte libre
- Si le guide n’a pas la règle, l’extraction échoue proprement

## 3. Les moteurs sont des exécuteurs purs
- Aucun fallback sémantique
- Output traçable via logs et tests

## 4. Échec silencieux mais observable
- rooms_emitted = 0 est valide
- Logs doivent expliquer pourquoi
- Tests doivent verrouiller ce cas

## 5. Les tests définissent la vérité
- On ne modifie pas des tests pour “faire passer”
- Si un gate casse, suspecter d’abord une violation MCAF

## 6. L’évolution se fait dans le guide
- Prompts et schémas peuvent évoluer via décisions et gates
- Les moteurs ne changent pas de comportement sans RFC
