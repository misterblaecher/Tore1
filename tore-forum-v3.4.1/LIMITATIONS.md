# LIMITATIONS RESTANTES — v3.4.2

La v3.4.2 ferme la passe principale de hardening du prototype frontend. La QA navigateur réelle passe sur GitHub Actions avec Google Chrome (7/7 scénarios), mais les limites suivantes restent bloquantes avant production.

## Sécurité / backend

- authentification et sessions serveur ;
- enforcement serveur de `structureId`, RBAC, Visibility et Permission Grant Ceiling ;
- base de données réellement multi-tenant ;
- protection serveur du rôle Owner et de `transferOwnership()` ;
- filtrage serveur des données financières avant sérialisation ;
- recherche permission-aware côté serveur ;
- exports autorisés/générés côté serveur ;
- audit logs sensibles stockés côté serveur, idéalement append-only ;
- rate limiting, anti-abus et monitoring.

## Fichiers / médias

- stockage cloud privé ;
- URLs signées ou endpoints de téléchargement autorisés ;
- antivirus / validation MIME serveur ;
- quotas et politique de rétention ;
- versioning durable côté storage backend.

Le versioning Document v3.4.2 est réel localement pour les nouvelles versions créées après cette release, mais reste basé sur IndexedDB.

## Intégrations

- synchronisation réelle avec l’app TORÈ ;
- invitations email/lien/QR réellement envoyées ;
- validation des StructureClaims par TORÈ Admin ;
- éventuels webhooks/jobs de publication programmée côté serveur.

## Web / conformité

- rendu SSR/SSG/metadata serveur pour le SEO public ;
- politique RGPD : export, suppression/anonymisation, consentement, rétention ;
- sauvegardes, restauration et plan de reprise ;
- observabilité production.

## QA

Le Browser QA v3.4.2 exécute désormais réellement Chrome en CI et passe 7/7. Pour le backend futur, ajouter ensuite :

- E2E authentifiés contre une vraie API/database ;
- tests de concurrence et transactions ;
- tests RLS/tenant côté serveur ;
- tests d’URLs signées et expirations ;
- tests de migration DB et restauration.

**Important :** IndexedDB/localStorage + RBAC frontend restent des protections de prototype et de cohérence métier, pas une frontière de sécurité production.
