# Inventaire préalable — consolidation Forum TORÈ

Audit du 15 septembre 2026, avant toute modification du code ou intégration.
`git fetch --all --prune` réussi. Toutes les références locales/distantes, le graphe complet, les messages et les noms de fichiers ont été recherchés, y compris les branches sans nom Forum. Les recherches de contenu historique ont aussi couvert StructureMandate, handover, passation et les bibliothèques médias.

## Matrice des sources

COMPLET signifie couverture retrouvée dans le code source ; validation finale encore à exécuter. PARTIEL signifie adaptation ou fonctions manquantes identifiées.

| Prompt | État audité | Branche source | Commits | Backend / frontend principaux | Migration source | Tests source | Dépendances |
|---|---|---|---|---|---|---|---|
| 1 Baseline | COMPLET | codex/forum-integration-2026-09-15 | 941eb77,37edc9b,7450b38,33316a1 | routers/forum.py, forum_event_workspace.py, forum_accounting.py ; ForumStructure, StructureDiscussions, StructurePortalSettings (components) | 0012_discussion_workspace | test_discussion_workspace, test_forum_structure_mvp, test_forum_event_workspace, test_forum_accounting_access | — |
| 2 Lifecycle | COMPLET | codex/forum-integration-2026-09-15 | 3622cbf,083f6f8,00c4bf9,56fd25e,2600dbc,9b91d00 | structure_lifecycle, structure_visibility | 0013_structure_lifecycle_private_defaults | test_structure_lifecycle_privacy, test_structure_visibility_publication_guard | 1 |
| 3 RBAC | PARTIEL | codex/forum-integration-2026-09-15 | fafc000,a3b3924 | models/structure_rbac, services/structure_rbac, routers/structure_rbac | 0014_structure_capability_rbac | test_structure_capability_rbac | 1,2 ; plusieurs anciennes routes utilisent encore le rang |
| 4 ACL | PARTIEL | codex/forum-channel-acls | 156bde2 | forum_acl_models, services/forum_channel_acl, routers/forum_channel_acl ; ChannelAclSettings | 0014_forum_channel_acl | test_forum_channel_acl | ancienne architecture forum/v2, absente de la base moderne ; adaptation nécessaire à 3 |
| 5 Claim | COMPLET | chore/stabilisation-2026-09-11 | 2827879 | models_structure_claim, structure_claim_service, structure_claims ; StructureClaimAction, Forum | 0013_structure_claim_workflow | test_structure_claim_workflow | 1,2 |
| 6 Ownership | PARTIEL | feat/structure-ownership-recovery | 33c98f2 | ownership_models, forum_ownership ; ForumOwnership | 0012_structure_ownership_recovery | test_forum_ownership_security | 3,5 ; réconcilier rôles persistants |
| 7 Invitations | PARTIEL | feat/forum-member-invitations | 9757f54 | models_structure_invitations, forum_invitations, structure_invitation_email_service ; ForumInvitation, ForumMembers | 0012_structure_invitations | test_forum_structure_invitations, forum-members-invitations.test | 3,6 ; réconcilier navigation moderne |
| 8 Mandats | ABSENT | aucune implémentation dédiée retrouvée | — | dates de membership legacy seulement ; pas de StructureMandate/passation/alumni complète | — | — | 3,6,7 |
| 9 Storage | COMPLET | main, feat/forum-integrated-event-recap | 1e4decf,58dc883 | models/storage, routers/storage, storage_service | 0012_secure_managed_uploads devenu 0015 dans la base | test_secure_storage_uploads | 2,3 |
| 10 Branding | PARTIEL | feat/forum-structure-branding | a0daa7e | storage existant ; lib/structure-branding, pages/StructurePortalSettings, ForumPublic | aucune supplémentaire | test_structure_branding_upload, structure-portal-settings.test | 9 ; fusionner avec components/StructurePortalSettings moderne |
| 11 Médiathèque | PARTIEL | base moderne et anciens frontend Forum | baseline | StructureAlbum/StructureMedia, formulaire URLs legacy ; aucune médiathèque gérée complète retrouvée | tables baseline | test_forum_structure_mvp | 9 ; upload multiple, sélection, suppression, audience à compléter |
| 12 Cohosting | PARTIEL | feat/event-cohosting-rich-manager | dcb2d20 | models/event_cohosting, event_manager, event_cohosting_service, operational_access_service ; ForumEventManager | 0013_event_structure_cohosting | test_event_manager_cohosting | 3,9 ; ancien ROLE_RANK et intégration workspace à réconcilier |
| 13 Public Event + recap | PARTIEL | feat/public-event-pages-recap, feat/forum-integrated-event-recap | 8c4ab98,a6dc213,58dc883,59f9beb | models/forum_events, routers/forum_events ; ForumEvent | 0013_public_event_recap devenu 0016 | test_forum_event_pages, forum-event.test | 9,12 ; cohosts encore issus de rules_flags |

## Choix de base

`origin/feat/forum-integrated-event-recap` à `59f9beb` contient intégralement `codex/forum-integration-2026-09-15` : merge-base `a3b3924`, rev-list gauche/droite `0 / 5`. Diff : 19 fichiers, 1971 insertions, 5 suppressions. Elle conserve les discussions avancées et ajoute storage + recap. Les autres branches spécialisées sont divergentes et ne contiennent pas toutes le workspace moderne.

La chaîne existante 0012 discussion → 0013 lifecycle → 0014 RBAC → 0015 storage → 0016 recap sera conservée pour limiter les ruptures des bases déjà migrées ; les migrations récupérées devront être ajoutées après 0016 et leurs down_revision adaptés.

## État local à préserver

Branche initiale main à 1e4decf. Modifications utilisateur : docker-compose.yml, tore_site/package-lock.json, tore-portal/package-lock.json ; fichier non suivi tore_local_backup.sql. Ne pas les inclure dans les commits de consolidation.
