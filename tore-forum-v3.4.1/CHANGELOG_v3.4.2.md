# CHANGELOG v3.4.1 → v3.4.2

## Security / roles

- Ajout d’un Permission Grant Ceiling centralisé.
- Un acteur ne peut plus déléguer une permission qu’il ne possède pas.
- `structure.admin`, `ownership.transfer` et `accounting.unlock` sont strictement non délégables aux rôles personnalisés.
- Protection appliquée à la création/modification de rôle, à l’assignation d’un rôle et aux invitations.
- Les rôles système restent immuables.
- `transferOwnership()` exige désormais le véritable Owner principal courant, même si un rôle legacy contient artificiellement `ownership.transfer`.

## Optional permissions

- La fiche Event ne lit plus Stats lorsque `stats.view` est absent.
- Une permission secondaire manquante ne transforme plus une page principale autorisée en erreur globale.
- Le dashboard conserve les guards existants sur Finance, Audit, Documents et Stats.

## Visibility Center

- Ajout de la section `Contact`.
- Ajout de la section `Publications / Actualités`.
- Le résumé Stats public respecte désormais la politique `stats`.
- Les résumés publics Stats sont limités aux données opérationnelles.
- Les anciennes structures reçoivent une politique Contact/Publications explicite lors du chargement v3.4.2.

## Publications

- Séparation de `isPublishedNow()` et de la lecture par audience.
- Support réel des publications PUBLISHED à visibilité Public, TORÈ, Membres, Staff, Bureau, Trésorerie et Privé.
- Une section Publications masquée bloque tous les posts, même un post marqué Public.
- Une publication SCHEDULED reste invisible avant `publishAt`.
- Le formulaire admin expose la visibilité de la publication.

## Public branding

- `bannerBlobKey` est réellement rendu dans le hero de la page structure.
- Overlay sombre conservant l’identité visuelle TORÈ et la lisibilité.
- Paramètres → Branding : changer/supprimer logo et bannière.
- Uploads branding stockés dans IndexedDB via le BlobRepository.
- Changements branding audités.

## Onboarding

La dernière étape couvre maintenant :

- Présentation ;
- Events ;
- Membres ;
- Albums ;
- Folklore ;
- Sponsors ;
- Contact ;
- Publications ;
- Stats.

La publication initiale reste explicite.

## Documents

- Le remplacement de document conserve désormais l’ancien binaire sous `doc:{documentId}:vN`.
- Les anciennes versions créées après v3.4.2 peuvent être preview/download.
- La suppression d’un document nettoie aussi ses blobs historiques.

## Browser QA

- Auto-détection Chrome / Edge / Chromium conservée.
- Process group isolé sur Unix.
- `taskkill /T /F` sur Windows.
- SIGTERM puis SIGKILL sur Unix.
- timeout par navigateur + timeout global de suite.
- cleanup serveur et navigateurs dans `finally`.
- statuts explicites : PASS / FAIL / INCONCLUSIVE / SKIPPED.
- scénarios : public, dashboard, Event, Visibility, Settings, Publications mobile, Onboarding mobile.

## PWA

- Cache shell incrémenté vers `tore-forum-v3.4.2-shell`.
- Nouveaux modules de hardening intégrés au shell.
- Les données métier privées ne sont toujours pas mises en cache.

## Tests

- Ajout de `final-hardening-v3.4.2.test.mjs`.
- Couverture : grant ceiling, non-delegable permissions, transfert ownership, Event sans Stats, Stats visibility, posts multi-audience, Contact visibility, Publications section, banner render et document binary versioning.
- Ajout du workflow GitHub Actions `Forum v3.4.2 QA`.
