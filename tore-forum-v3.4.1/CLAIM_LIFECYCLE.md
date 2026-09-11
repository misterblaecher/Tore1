# STRUCTURE CLAIM LIFECYCLE — v3.4

```text
PENDING
  ├─ APPROVED
  ├─ REJECTED
  └─ CANCELLED
```

Champs : id, structureId, requesterUserId, status, reason, proof, createdAt, reviewedAt, reviewedBy.

## Request
Authentification obligatoire. Maximum un PENDING par requester + structure. La Structure cible conserve son lifecycle.

## Approve
Le prototype crée/réactive le membership si nécessaire, appelle le workflow de transfert de propriété, passe le claim à APPROVED et écrit les audits.

## Reject
Le claim devient REJECTED ; la Structure reste inchangée.

## Cancel
Le requester peut annuler son propre PENDING.

En production, la review devra être gérée par TORÈ Admin côté serveur.
