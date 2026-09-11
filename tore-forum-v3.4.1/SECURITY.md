# SECURITY — TORÈ Forum v3.4.2

## Autorisation centrale

`AuthorizationService` décide les accès. Les services imposent en plus les invariants métier, les whitelists, le tenant scope et le Permission Grant Ceiling. Une vue cachée, un bouton absent, du CSS ou une URL non affichée ne constituent jamais une permission.

## Immutable tenant scope

Champs protégés : `id`, `structureId`, `createdAt`. Toute tentative de mutation ou propriété inconnue est refusée explicitement.

Le tenant d’un CREATE provient du contexte actif autorisé. Le repository expose `getForStructure`, `listForStructure`, `insertForStructure`, `updateForStructure`, `removeForStructure`.

## Permission Grant Ceiling

Un acteur avec `roles.manage` ne peut créer, modifier, assigner ou inviter vers un rôle contenant une permission qu’il ne possède pas lui-même.

Les permissions suivantes sont **strictement non délégables aux rôles personnalisés** :

- `structure.admin`
- `ownership.transfer`
- `accounting.unlock`

Elles ne peuvent pas être obtenues indirectement via création/modification de rôle, invitation ou changement de membership. Les rôles système restent protégés.

Même si des données legacy contiennent un rôle personnalisé contaminé par une permission non délégable, la v3.4.2 bloque sa réassignation et sa redélégation.

## Owner invariants

Owner est un rôle système. Le propriétaire principal reste défini par `Structure.ownerUserId`, son membership ACTIVE et le rôle système Owner.

Le transfert passe uniquement par `StructureService.transferOwnership()`. En v3.4.2, posséder artificiellement `ownership.transfer` dans un rôle legacy ne suffit plus : l’acteur doit être le véritable Owner principal courant.

## Stats ≠ finance

`stats.view` autorise uniquement : entries, scans, capacity, hourly, entryPoints et publicSummary opérationnel.

`accounting.view` est requis pour : revenue, cost, estimatedProfit, actualProfit, margin, turnover.

Le filtrage est effectué avant le consumer. Deux exports existent : opérationnel et financier.

Une permission secondaire manquante n’empêche pas la lecture de la ressource principale : par exemple un utilisateur avec `events.view` sans `stats.view` peut lire l’Event, mais ne reçoit pas le bloc Stats.

## Visibility Center

Le Visibility Center est la source de vérité de section. La v3.4.2 couvre notamment :

- Presentation
- Events
- Membres
- Albums
- Folklore
- Sponsors
- Contact
- Publications / Actualités
- Stats Summary
- Documents

### Stats Summary

Un résumé d’Event est visible seulement si :

1. l’Event est visible pour l’audience ;
2. un `publicSummary` existe ;
3. la section `stats` autorise cette audience.

Le DTO public du résumé ne contient jamais de finance.

### Publications

Le statut et la visibilité sont séparés :

- `isPublishedNow(post)` décide si le post est temporellement publié ;
- `canAudienceRead(post.visibility, audience)` décide qui peut le lire ;
- la section `publications` doit elle-même être autorisée.

Un post `PUBLISHED + Membres` est donc invisible au public et visible aux Membres ou niveaux supérieurs. Un post `SCHEDULED` n’apparaît pas avant `publishAt`.

### Contact

La route `/structures/:slug/contact` et le bloc Contact de la homepage appliquent la politique `contact`. Une URL directe ne contourne pas cette règle.

## Fichiers et branding

Les blobs de démonstration restent dans IndexedDB. Preview/download passent par l’autorisation ; les object URLs sont révoquées.

La v3.4.2 conserve chaque ancien binaire lors d’un remplacement de document sous une clé de version distincte (`doc:{id}:vN`) pour les versions créées après cette release.

Logo et bannière sont stockés dans le Media/Blob repository local. Le hero public consomme réellement `bannerBlobKey`. Changer/supprimer un branding passe par un service protégé et produit un AuditLog.

## PublicPage

Lifecycle : DRAFT, PUBLISHED, HIDDEN, SUSPENDED, ARCHIVED. DRAFT/HIDDEN ne sont pas publics. Une preview exige une permission réelle. `?preview=` n’élève jamais les droits.

## Search / archives

La recherche filtre avant de produire un résultat. Le titre d’une ressource inaccessible n’est pas retourné. Archives reste une vue agrégée des ressources autorisées et ne copie pas les données.

## Browser QA

Le runner tue l’arbre Chromium/Chrome/Edge et le serveur local dans `finally`, applique des timeouts par processus et un timeout global, puis retourne un statut explicite : PASS, FAIL, INCONCLUSIVE ou SKIPPED.

## Audit

Les actions sensibles journalisent actor, structureId, action, resource/resourceId, before, after, timestamp. Ownership transfer, claims, public page lifecycle, event transitions, finance exports/locks, settings, branding et rôles sont couverts.

## Backend contract

Le frontend v3.4.2 prépare les invariants mais **IndexedDB/localStorage ne sont pas une frontière de sécurité production**.

Le backend devra :

- authentifier les sessions côté serveur ;
- dériver le tenant depuis la session/autorisation serveur ;
- ignorer/refuser les `structureId` non autorisés dans les bodies ;
- appliquer le Permission Grant Ceiling côté serveur ;
- protéger les rôles système et ownership côté serveur ;
- filtrer finance, Visibility, recherche et exports avant sérialisation ;
- fournir des URLs signées pour les fichiers privés ;
- stocker les AuditLogs sensibles côté serveur, idéalement append-only ;
- mettre en place rate limits, monitoring et contrôles RGPD.
