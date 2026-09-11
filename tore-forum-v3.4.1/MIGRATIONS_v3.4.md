# MIGRATION v3.3 → v3.4

State v3.4 : `seed.version = 5`. La clé locale reste compatible pour migration en place.

Ajouts : PublicPage, StructureClaim, Role.systemRole, permission `ownership.transfer`, champs branding.

## PublicPage
- ancienne Structure ACTIVE → PUBLISHED
- autre statut → DRAFT

## Owner
La migration marque Owner système, restaure ses permissions critiques, réactive/crée le membership correspondant à `ownerUserId`, crée un rôle Bureau de repli si nécessaire et rétrograde d’éventuels Owner ACTIVE supplémentaires.

## Claims
`structureClaims` est initialisé vide si absent. Aucun ancien statut Structure n’est automatiquement converti en claim.

## IndexedDB
Store blobs compatible, aucune purge.

## PWA
Cache : `tore-forum-v3.4-shell`. Les anciens caches shell sont invalidés ; aucune donnée privée métier n’est ajoutée au cache.
