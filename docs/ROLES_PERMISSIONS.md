# TORÈ — Roles & Permissions (Contract)

Objectif : documenter les rôles, memberships et règles d’autorisation **de manière stable** pour tous les clients (Flutter + Portal), en gardant le backend comme **source of truth**.

## Principes (non négociables)
- **Backend = source of truth** pour les permissions et invariants.
- Les clients (App/Portal) ne font que :
  - afficher selon le contexte (modules ON/OFF, état event, droits)
  - masquer l’UI non autorisée
  - appeler l’API (et gérer offline/read-only)
- Toute action write sensible doit être protégée par :
  - auth obligatoire
  - check role/capability côté backend
  - check module ON/OFF
  - check état event (PAUSED/DEGRADED/FROZEN/ENDED)

## Types d’identités
Dans TORÈ on distingue généralement :
- **App user** : utilisateur final (expérience terrain).
- **Partner / Staff** : identité opérationnelle (bar, entry, kitchen, manager).
- **Orga** : gestion événement / staff / annonces.
- **Global Admin** : droits transverses.

> Note: Le format exact des JWT/claims peut évoluer, mais l’objectif est de converger vers un modèle commun avec un `identity_type` clair.

## Modèle “Membership” (rôles)
Les rôles sont **scopés** et stockés via des tables de membership.

### OrganizationMembership
Rôles typiques :
- `OWNER`
- `MANAGER`
- `MEMBER`

Accès typiques :
- création/gestion events liés à l’orga
- staff management
- broadcasts
- incidents (lecture/gestion selon niveau)

### PartnerMembership (bar / staff)
Rôles typiques :
- `OWNER`
- `MANAGER`
- `BARTENDER` (ou staff bar)

Accès typiques :
- menu admin (selon rôle)
- orders live / kitchen / queue
- analytics bar (selon rôle)

### CommitteeMembership (communauté / comité)
Rôles typiques :
- `OWNER`
- `ADMIN`
- `MOD`
- `MEMBER`

Accès typiques :
- forum / posts moderation
- ledger / finances (selon rôle)
- campagnes / baptême ops (selon scope)

### Global Admin
- accès transverse aux opérations sensibles
- audit log
- ops / analytics global

## Capabilities (recommandé pour clients)
Pour éviter de coder des règles complexes dans Flutter/Portal, le backend devrait fournir un snapshot “capabilities” (ex: `/me` ou `events/{id}/context`).

### Exemples de capabilities
- `can.event.manage`
- `can.event.configure_modules`
- `can.orders.view`
- `can.orders.manage`
- `can.wallet.read`
- `can.wallet.transfer`
- `can.wallet.admin`
- `can.entry.scan`
- `can.broadcast.send`
- `can.incidents.manage`
- `can.analytics.view`

**Règle :** le client utilise `can.*` pour afficher/masquer et autoriser l’action.  
Le backend revalide toujours (role + module + état + invariants).

## Event-state gating (invariants)
Les actions sont aussi conditionnées par l’état de l’événement.

États conceptuels typiques :
- `RUNNING`
- `PAUSED` : lecture ok, writes parfois bloqués sauf staff/ops.
- `DEGRADED` : lecture ok, writes strictement limités.
- `FROZEN` : writes bloqués (sauf admin/ops si prévu).
- `ENDED` : writes bloqués, uniquement lecture / analytics.

> Le backend doit exposer une règle centralisée du type `ensure_event_action_allowed(event_id, action)`.

## Module gating (ON/OFF)
Chaque événement active/désactive des modules :
- un module OFF ne doit **pas** apparaître dans l’UI
- un module OFF doit **refuser** toute action serveur correspondante

> Règle : backend expose `modules_enabled[]` dans un contexte event.

## Où les checks doivent vivre
- **Backend** : toujours.
- **Portal** : guards + UI gating (confort, pas sécurité).
- **Flutter** : UI gating basé sur le contexte (confort, pas sécurité).

## Conventions d’erreurs (recommandé)
- `403 FORBIDDEN` : pas les droits (role/capability)
- `409 CONFLICT` : action invalide selon état event
- `412 PRECONDITION_FAILED` : module OFF / write interdit / précondition non respectée
- `401 UNAUTHORIZED` : pas authentifié / token invalide
