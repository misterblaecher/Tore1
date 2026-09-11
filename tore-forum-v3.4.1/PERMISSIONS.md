# PERMISSIONS v3.4.2

## Structure / governance
- `structure.admin` — **système / non délégable**
- `structure.manage`
- `ownership.transfer` — **système / non délégable** ; ne remplace pas la vérification de l’Owner principal

## Members / roles
- `members.view`
- `members.manage`
- `roles.manage`

## Events
- `events.view`
- `events.manage`
- `events.publish`

## Documents
- `documents.view`
- `documents.download`
- `documents.manage`

## Albums
- `albums.view`
- `albums.manage`

## Folklore
- `folklore.view`
- `folklore.manage`

## Planning
- `planning.view`
- `planning.manage`

## Stats / finance
- `stats.view` — données opérationnelles uniquement
- `accounting.view` — données financières
- `accounting.manage`
- `accounting.unlock` — **système / non délégable**

## Governance / content
- `visibility.manage`
- `audit.view`
- `channels.post`
- `channels.manage`
- `publications.manage`
- `archives.view`

## Permission Grant Ceiling

Pour un rôle personnalisé, l’acteur ne peut accorder que les permissions qu’il possède lui-même.

En plus, les permissions système suivantes sont interdites dans un rôle personnalisé, même si l’acteur est Owner :

```text
structure.admin
ownership.transfer
accounting.unlock
```

Elles restent attachées aux workflows système prévus à cet effet.

Le plafond est appliqué sur :

- création de rôle ;
- modification de rôle ;
- changement de rôle d’un membre ;
- invitation d’un membre avec un rôle ;
- rôles legacy contaminés : réassignation/redélégation refusée.

## Permission optionnelle

Une permission secondaire manquante ne doit pas casser une page principale autorisée. Exemple :

```text
events.view = true
stats.view = false
```

La fiche Event reste accessible ; le bloc Stats n’est pas lu/rendu.

Permissions internes et niveaux de visibilité sont indépendants. `stats.view` n’implique jamais `accounting.view`.
