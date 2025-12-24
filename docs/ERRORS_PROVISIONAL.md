# ERRORS Phase 3.2 Provisional Mode

Objectif
Normaliser les messages et codes d'erreur quand le guide stable est rejeté.

Cas 1  Stable guide rejected
- Code: STABLE_GUIDE_REJECTED
- HTTP: 200 (status endpoint) ou 409 (si action requiert stable uniquement)
- Message UX:
  "Guide stable non généré car conventions insuffisamment stables entre pages. Guide provisoire disponible. Extraction possible en mode provisoire."

Cas 2  Extract blocked because no guide
- Code: EXTRACT_BLOCKED_NO_GUIDE
- HTTP: 409
- Message UX:
  "Extraction impossible car aucun guide n'est disponible. Lancez Analyze."

Cas 3  Query returns ambiguous
- Code: QUERY_AMBIGUOUS
- HTTP: 200
- Payload:
  ambiguous=true, ambiguity_reason string
- Message UX:
  "Plusieurs correspondances. Précisez room vs door, ou page."

Cas 4  Provisional mode low confidence suppressed
- Code: PROVISIONAL_SUPPRESSED_LOW_CONFIDENCE
- HTTP: 200
- Message UX:
  "Résultats conservateurs: certains objets incertains ont été ignorés."

Date: 2025-12-24
