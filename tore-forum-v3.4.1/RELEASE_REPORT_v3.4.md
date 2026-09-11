# TORÈ Forum v3.4 — Release Report

## Corrigé

- Injection `structureId` à la création : refus explicite.
- Mutation de `structureId`, `id` et `createdAt` : refus centralisé.
- Repositories tenant-scoped renforcés pour get/list/insert/update/delete.
- Whitelists de champs par service.
- Stats opérationnelles séparées des données financières.
- Exports stats opérationnel / financier séparés.
- Dashboard financier filtré selon `accounting.view`.
- Owner protégé contre downgrade, revoke, alumni, rôle cassé ou suppression.
- Transfert de propriété dédié, rollback en cas d’échec et audit.
- Onboarding et claims impossibles sans authentification.
- `StructureClaim` séparé du lifecycle Structure.
- Claim duplicate PENDING refusé.
- `PublicPage` séparée du lifecycle Structure : DRAFT / PUBLISHED / HIDDEN / SUSPENDED / ARCHIVED.
- Publication publique explicite ; nouvelle structure en DRAFT par défaut.
- Lifecycle Event piloté par le domain/service et consommé par l’UI.
- Archive Center unifié en vue agrégée permission-aware.
- Validation datetime/numeric durcie.
- Migration v3.3 → v3.4 sans reset systématique.
- Service Worker versionné v3.4 shell-only.

## Testé

La suite principale contient 10 suites de tests et 201 appels `assert.*` statiques,
auxquels s’ajoutent les assertions répétées dans les boucles d’attaque multi-tenant.

Scénarios négatifs couverts :
- injections CREATE/UPDATE tenant ;
- IDs étrangers connus ;
- téléchargement document étranger ;
- Owner downgrade/revoke/role mutation ;
- transfert ownership ;
- anonymat onboarding/claim ;
- claim duplicate/reject/approve ;
- fuite finance via Stats ;
- public page draft/hide/republish ;
- validations date/nombre ;
- migration Owner/PublicPage.

Les deep-links et assets principaux retournent HTTP 200 avec le serveur SPA.
Les principaux modules JS passent `node --check`.

## QA navigateur

Le runner Chromium réel est inclus et a été exécuté aux largeurs 1440, 768 et 390 px.
Dans le sandbox de livraison, le Chromium système se bloque au démarrage sur D-Bus,
y compris indépendamment de l’application ; le test visuel est donc **INCONCLUSIVE**,
jamais présenté comme PASS.

## Encore frontend / mock

- identité/authentication ;
- stockage de métadonnées ;
- blobs de fichiers/médias ;
- synchronisation App TORÈ ;
- invitations email/QR ;
- validation de claims par TORÈ Admin ;
- audit persistence ;
- recherche/index ;
- exports et PDF.

## Avant production

Le backend devra obligatoirement réimplémenter et imposer :
- authentification/session serveur ;
- RBAC et Visibility côté serveur ;
- tenant dérivé de la session, jamais d’un body utilisateur ;
- filtrage finance avant sérialisation réseau ;
- URLs privées/signées ;
- recherche permission-aware côté serveur ;
- exports autorisés côté serveur ;
- audit append-only ;
- monitoring/rate limits ;
- RGPD et politique de rétention.
