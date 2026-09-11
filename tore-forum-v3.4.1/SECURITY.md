# SECURITY — TORÈ Forum v3.4

## Autorisation centrale
`AuthorizationService` décide les accès. Les services imposent en plus les invariants métier, les whitelists et le tenant scope. Une vue cachée/CSS/URL ne constitue jamais une permission.

## Immutable tenant scope
Champs protégés : `id`, `structureId`, `createdAt`. Toute tentative de mutation ou propriété inconnue est refusée explicitement.

Le tenant de CREATE provient du contexte actif autorisé. Le repository expose `getForStructure`, `listForStructure`, `insertForStructure`, `updateForStructure`, `removeForStructure`.

## Stats ≠ finance
`stats.view` autorise uniquement : entries, scans, capacity, hourly, entryPoints, publicSummary opérationnel.

`accounting.view` est requis pour : revenue, cost, estimatedProfit, actualProfit, margin, turnover.

Le filtrage est effectué avant le consumer. Deux exports existent : opérationnel et financier.

## Owner invariants
Owner est un rôle système. Permissions critiques garanties : `structure.admin`, `structure.manage`, `members.manage`, `roles.manage`, `ownership.transfer`.

Invariant : `ownerUserId` existe, son User existe, son membership est ACTIVE et utilise le rôle Owner, et exactement un Owner ACTIVE existe.

Le transfert passe uniquement par `StructureService.transferOwnership()`.

## Claims
Une revendication est un `StructureClaim` séparé. Elle ne modifie jamais directement `Structure.status`. Authentification obligatoire et un seul PENDING par requester + structure.

## PublicPage
Lifecycle : DRAFT, PUBLISHED, HIDDEN, SUSPENDED, ARCHIVED. DRAFT/HIDDEN ne sont pas publics. Une preview exige une permission réelle. `?preview=` n’élève jamais les droits.

Règle LOCKED v3.4 : la page publique n’est pas rendue. L’admin reste accessible aux memberships autorisés pour permettre la résolution/support.

## Search / archives
La recherche filtre avant de produire un résultat. Le titre d’une ressource inaccessible n’est pas retourné. Archives est une vue agrégée des ressources autorisées et ne copie pas les données.

## Fichiers
Les blobs de démonstration sont en IndexedDB. Preview/download passent par l’autorisation ; les object URLs sont révoquées.

## Audit
Les actions sensibles journalisent actor, structureId, action, resource/resourceId, before, after, timestamp. Ownership transfer, claims, public page lifecycle, event transitions, finance exports/locks, settings et rôles sont couverts.

## Backend contract
Le serveur devra dériver le tenant depuis une session/autorisation serveur, jamais faire confiance à un `structureId` du body, et réimplémenter auth, RBAC, scoping, finance filtering, recherche, exports, URLs signées, audit append-only, rate limits et monitoring.

Le frontend v3.4 prépare ces invariants mais IndexedDB/localStorage ne sont pas une frontière de sécurité production.
