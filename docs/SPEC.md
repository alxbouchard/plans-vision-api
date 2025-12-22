# DOCUMENTATION DÉVELOPPEUR

## API Vision de compréhension de plans de construction

## Basée sur GPT-5.2 (Responses API)

## Version 1.0 – Source de vérité

---

## 0. Principe fondamental (à lire avant de coder)

Cette API **ne reconnaît pas des objets**, elle **apprend comment un projet est dessiné**.

Tout le système repose sur 4 règles non négociables :

1. Rien n'est hardcodé
2. Rien n'est deviné
3. Une règle n'existe que si elle est observée
4. Une règle instable est rejetée

Si une implémentation viole une de ces règles, elle est incorrecte.

---

# 1) Scope et définition du "terminé"

---

## 1.1 Objectif utilisateur (2 phrases)

Permettre à un utilisateur de soumettre plusieurs pages de plans d'un même projet afin que le système comprenne, comme un humain, les conventions graphiques utilisées.
Le système doit produire un **guide visuel stable et réutilisable**, validé inter-pages, servant de base fiable pour toute analyse ultérieure.

---

## 1.2 In scope

* Upload d'images PNG de plans
* Analyse Vision page par page
* Génération d'un guide visuel provisoire
* Validation inter-pages des conventions
* Consolidation d'un guide visuel final
* Stockage et consultation du guide

---

## 1.3 Out of scope

* Extraction de bounding boxes
* OCR structuré
* Calculs de surfaces ou métrés
* Généralisation inter-projets
* Entraînement ou fine-tuning
* UI avancée

---

## 1.4 Definition of Done

Le système est considéré terminé quand :

1. Un projet peut être créé
2. Plusieurs pages peuvent être uploadées
3. Un guide provisoire est généré depuis la page 1
4. Ce guide est testé automatiquement sur les pages suivantes
5. Les règles sont classées (stable / partielle / instable)
6. Un guide final est produit ou explicitement refusé
7. Les erreurs sont explicites
8. Aucun symbole n'est hardcodé
9. Un autre agent peut utiliser le guide pour analyser une nouvelle page du même projet

---

# 2) Architecture générale

---

## 2.1 Vue d'ensemble logique

```
Client
 └─ API Vision
     ├─ Storage (images)
     ├─ Pipeline GPT-5.2 multi-agents
     ├─ Validation inter-pages
     └─ Storage (guides)
```

---

## 2.2 Rôles des agents

| Agent              | Responsabilité                   |
| ------------------ | -------------------------------- |
| Guide Builder      | Comprendre la 1re page           |
| Guide Applier      | Tester le guide sur autres pages |
| Self-Validator     | Évaluer la stabilité             |
| Guide Consolidator | Produire le guide final          |

---

# 3) Choix des modèles GPT-5.2

---

## 3.1 Mapping obligatoire

| Agent              | Modèle      | reasoning.effort | verbosity |
| ------------------ | ----------- | ---------------- | --------- |
| Guide Builder      | gpt-5.2-pro | high ou xhigh    | high      |
| Guide Applier      | gpt-5.2     | none ou low      | medium    |
| Self-Validator     | gpt-5.2-pro | high             | high      |
| Guide Consolidator | gpt-5.2     | medium           | high      |

Toute autre combinaison doit être justifiée.

---

# 4) Pipeline fonctionnel détaillé

---

## 4.1 Étape 1 – Création de projet

### Endpoint

```
POST /projects
```

### Réponse

```json
{
  "project_id": "uuid",
  "status": "draft"
}
```

Invariant :

* Un projet commence toujours en `draft`

---

## 4.2 Étape 2 – Upload des pages

### Endpoint

```
POST /projects/{project_id}/pages
```

### Règles

* PNG uniquement
* Ordre conservé
* Pages immuables après upload

### Erreurs

* 415 si MIME invalide
* 409 si projet déjà validé

---

## 4.3 Étape 3 – Guide Builder (page 1)

### Input

* Page 1 PNG

### Output

* guide_visuel_provisoire (texte)
* règles déduites
* incertitudes

### Prompt

Utiliser **strictement** le prompt `VISION_GUIDE_BUILDER` fourni précédemment.

Aucune modification autorisée.

---

## 4.4 Étape 4 – Guide Applier (pages suivantes)

### Input

* Page N
* guide_visuel_provisoire

### Output

* règles confirmées
* règles en échec
* variations observées

### Prompt

`VISION_GUIDE_APPLIER`

---

## 4.5 Étape 5 – Self-validation inter-pages

### Input

* guide_visuel_provisoire
* observations multi-pages

### Output

* score de stabilité par règle
* recommandations

### Prompt

`VISION_SELF_VALIDATOR`

---

## 4.6 Étape 6 – Consolidation finale

### Input

* guide provisoire
* rapport de validation

### Output

* guide_visuel_stable
* limites explicites

### Prompt

`VISION_GUIDE_CONSOLIDATOR`

---

## 4.7 Règle critique

Si trop de règles sont instables, **le guide final ne doit pas être généré**.
Retourner une erreur métier explicite.

---

# 5) Modèle de données

---

## 5.1 Entités

### Project

```json
{
  "id": "uuid",
  "status": "draft | validated",
  "owner_id": "uuid",
  "created_at": "timestamp"
}
```

### Page

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "order": 1,
  "file_path": "string"
}
```

### VisualGuide

```json
{
  "project_id": "uuid",
  "provisional": "text",
  "stable": "text",
  "confidence_report": {}
}
```

---

## 5.2 Invariants stricts

* Un projet validé ne redevient jamais draft
* Une page ne peut jamais être modifiée
* Un guide stable est immuable
* Une règle instable n'apparaît jamais dans le guide final
* Un user ne voit jamais les projets d'un autre tenant

---

# 6) Erreurs et UX de l'échec

---

## Réseau

* Message : "Connexion interrompue"
* Action : retry
* Retry : oui

## Auth

* Message : "Session expirée"
* Action : reconnecter
* Retry : non

## Validation

* Message : "Donnée invalide"
* Action : corriger
* Retry : après correction

## Métier

* Message : "Conventions incohérentes"
* Action : fournir plus de pages
* Retry : oui

## Serveur

* Message : "Erreur interne"
* Retry : oui avec backoff

---

# 7) Observabilité et sécurité

---

## 7.1 Logs structurés obligatoires

Champs :

* timestamp
* project_id
* agent
* step
* status
* error_code
* latency_ms

---

## 7.2 Événements analytics

* project_created
* page_uploaded
* guide_build_started
* guide_build_failed
* guide_build_completed

---

## 7.3 Sécurité

* Clé API via variables d'environnement
* Aucun secret en dur
* Validation stricte des inputs
* Isolation stricte par tenant

---

# 8) Données d'exemple

---

## Valides

* Projet école 5 pages
* Projet bureau 3 pages
* Variations graphiques mineures
* Corridors longs
* Blocs multiples

## Invalides

* Pages de projets différents
* Images floues
* Plan technique non architectural
* Une seule page sans texte

---

# 9) Stratégie d'exécution recommandée

---

## A) Test first

1. Écrire scénarios d'acceptation
2. Implémenter jusqu'à succès
3. Aucun code sans critère clair

---

## B) Agent QA destructeur

Doit tester :

* accès cross-tenant
* pages incohérentes
* double soumission
* échecs GPT simulés

---

## C) Dernier 10 %

Découper en 20 à 50 tickets très petits :

* gestion timeout
* messages clairs
* retries contrôlés
* états vides

---

## RÈGLE FINALE

Si ce n'est pas visible, ça n'existe pas.
Si ce n'est pas stable, ça n'est pas utilisable.

---
