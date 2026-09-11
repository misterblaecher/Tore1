# CHANGELOG v3.3 → v3.4

## Tenant integrity
- Ajout de `src/core/integrity.js`.
- `id`, `structureId`, `createdAt` sont immuables.
- Les services utilisent des whitelists et refusent les champs inconnus.
- Le tenant de CREATE vient du contexte actif, jamais du payload normal.
- `get/insert/update/removeForStructure` renforcés.
- Upload Document refuse désormais explicitement un `structureId` injecté.
- Tests d’attaque sur Event, Channel, Album, Folklore, Planning, Accounting, PublicPost, Document et Role.

## Finance separation
- `stats.view` retourne seulement les statistiques opérationnelles.
- `accounting.view` est requis pour revenue, cost, profits, margin et turnover.
- `StatsService.list/get/byEvent` renvoient des DTO filtrés.
- Exports opérationnel et financier séparés.

## Owner governance
- Owner = rôle système `systemRole: true`.
- Interdiction de downgrade/revoke/alumni/delete/rename ou retrait des permissions critiques.
- Invariant : exactement un Owner ACTIVE correspondant à `Structure.ownerUserId`.
- `StructureService.transferOwnership()` dédié, audité et rollbackable.
- Rôle Bureau de repli créé si nécessaire pour les anciennes structures.

## Authentication / Claims
- Onboarding et claims exigent un User authentifié.
- `StructureClaim` séparé : PENDING / APPROVED / REJECTED / CANCELLED.
- Un claim PENDING ne change jamais `Structure.status`.
- Un seul claim PENDING par user + structure.
- Approval : membership + transfer ownership + audit.

## Public page lifecycle
- `PublicPage` séparée : DRAFT / PUBLISHED / HIDDEN / SUSPENDED / ARCHIVED.
- Nouvelle structure = DRAFT par défaut.
- Publication explicite, hide/republish réels et audités.
- Structures ACTIVE v3.3 migrées vers page PUBLISHED.
- Structure LOCKED : page non rendue publiquement.

## Events / validation / archives
- Event transitions centralisées dans le domain layer et consommées par l’UI.
- Dates Event obligatoires et validées avant conversion ISO.
- Validation numérique/date renforcée.
- Archives = vue agrégée permission-aware, sans duplication.
- Recherche Archives alignée sur l’agrégation.

## PWA / migration
- State v3.4 : version 5.
- Migration v3.3 conservatrice.
- Cache `tore-forum-v3.4-shell`.
- Données privées exclues du cache shell.
