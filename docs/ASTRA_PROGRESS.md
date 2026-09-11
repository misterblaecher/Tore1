# TORÈ — checkpoint 11 septembre 2026

## DONE
- Proxy admin : auth obligatoire, routes limitées, refus cross-site, timeout, erreurs sans fuite — 9 tests.
- Portail : login partenaire/session rétablis, owner admis au hub, suppression fallback démo/inter-bars, HTTP 204 accepté. Wallet : double-submit bloqué, clé stable après panne, export menu/Wallet authentifié — 7 tests auth/API/retry ; build PASS.
- Site : session préservée sur panne, cache par compte, permissions/visibilité corrigées — 20 tests, lint sans erreur, TypeScript/build PASS.
- Flutter : retry des writes limité aux intentions idempotentes, panier stable, retrait cache après refus serveur, API production explicite — analyze, 170 tests, APK dev debug PASS.
- Backend : autorité partenaire relue en DB (révocation/déclassement), ledger atomique et transferts verrouillés, filtre documents privés dashboard, nouvelles mises avec valeur OFF. Tests des domaines modifiés PASS.
- Lockfiles réparés + npm ci ; CI site et vrai gate Flutter ajoutés ; .dockerignore exclut secrets/bases/venv.

## CURRENT
- Runtime smoke local exécuté sur SQLite dédiée : backend, site, Forum et portail connectés. Ajout Flutter Structure → page Forum web.
- Régressions ajoutées : gift entre expéditeurs distincts, documents inter-structures, finance inter-structures ; ciblées backend PASS.
- Création d’event Flutter séparée du suivi publication/QR pack ; retry QR sans recréation. Handoff CreateOrga portail → Forum. Snapshot Wallet/Menu nettoyé au changement d’event.

## NEXT
1. Ajouter régressions collision gift entre 2 expéditeurs et isolation documents/finance entre structures ; revue concurrence SQLite/PostgreSQL.
2. Finir/tester les nouveaux composants StructureEvents/StructurePages (publication vers App, permissions, erreurs). Vérifier handoff CreateOrga : ancien formulaire opé exige AppUser alors que login partenaire utilise JWT ; aiguiller proprement vers tore_site.
3. Corriger création event opé (retry stable, succès création distinct d'échec QR pack), EntryStaff (erreurs poll/réponse), et refresh snapshot Wallet lors changement événement.
4. Valider migration sur copie PostgreSQL et smoke connexion → event publié → discovery → join ; adapter Compose production avec secrets et sauvegardes.
5. Exécuter gate release final ; CI ajoutée mais non exécutée sur GitHub.

## TEST STATUS
- Portail : npm test = 9 proxy + 7 auth/API/retry PASS ; npm run build PASS (Node local 25.5 ; CI Node 20).
- Site : 20/20 PASS ; lint 0 erreurs/7 warnings ; build PASS (bundle volumineux) ; npx tsc --noEmit -p tsconfig.app.json PASS. Discussions re-testées 2/2 après correction option RTL invalide.
- Flutter : analyze sans problème ; suite finale 170/170 PASS ; APK tore/app/build/app/outputs/flutter-apk/app-dev-debug.apk généré (SDK 3.41.1).
- Backend : suite complète initiale 361 PASS / 7 FAIL. Les 7 échecs corrigés, retest auth/RGPD/migrations/policy 33/33 PASS. Lot final security/RGPD/wallet/forum/discussions 29/29 PASS (inclut nouveaux tests déclassement et ledger). Suite complète non répétée après corrections ciblées.
- Backend : ciblage régressions gift/forum/finance 12 PASS (428 warnings historiques).
- TypeScript : `tore-portal` `npx tsc --noEmit` PASS ; `tore_site` `npx tsc --noEmit -p tsconfig.app.json` PASS. Vitest/Vite non relancés : esbuild sandbox refuse l’accès au répertoire parent.
- Flutter : la relance `dart format` / `flutter analyze` ciblée reste non confirmée, le SDK ne répond pas dans cette sandbox ; ne pas présenter le parcours visuel Android comme validé.
- Runtime event : `/events/4/public` et join idempotent réel vérifiés sur SQLite smoke ; modules retournés cohérents avec Event Hub.
- Migrations : tests base fraîche jusqu'à 0012, upgrades historiques et downgrade en base jetable PASS. PostgreSQL non exécuté.
- Commandes dans RELEASE_CHECKLIST.md. Venv valide .venv-release ; ancien .venv cassé.

## BLOCKERS
- Agents interrompus par quota ; travail intégré et vérifié localement ensuite. Pas de nouvelle délégation.
- iOS nécessite macOS/Xcode ; SMTP réel, domaine/credentials de déploiement et validation réglementaire externes restent requis.

## IMPORTANT CONTEXT
- Continuer sans audit global. Modifications Forum/discussions et migration 0012 existaient au départ : conservées.
- tore-portal = JWT partenaires/opérations ; tore_site = AppUser/Structures. Ces sessions restent distinctes côté legacy ; ne pas déduire de permissions depuis account_mode.
- Tests corrigés : rôle ADMIN_GLOBAL désormais enregistré en DB (claim seul interdit), test SMTP utilise transport simulé au lieu d'une fausse clé provider ; assertions head Alembic suivent ScriptDirectory. Baseline historique 0001 utilise métadonnées courantes : fixture upgrade fournit les JSON requis, sans réécriture de migration.
- TORE_VALUE_PREDICTIONS_ENABLED=0 par défaut ; anciens tests opt-in explicite. Aucun cash-out réel validé.
- Ne jamais afficher .env. Aucun commit/déploiement. .venv-release/.npm-cache ignorés. Sous Windows Vite/esbuild/Flutter nécessitent exécution escaladée pour accès parents/SDK.

## RUNTIME STATUS
Backend: RUNNING — `http://127.0.0.1:8001` (health 200, db_ok true)
Site / Forum: RUNNING — `http://127.0.0.1:8080`
Portal: RUNNING — `http://127.0.0.1:5173`
Flutter Android: RUNNING — emulator `emulator-5554`, API locale via `10.0.2.2:8001`
Flutter Web: RUNNING — `http://127.0.0.1:7357` (debug server)
PostgreSQL: UNAVAILABLE — Docker daemon absent ; SQLite runtime valid.

## SMOKE TESTS
- [x] Backend health + migrations 0012 + DB
- [x] Site public + annuaire structures
- [x] Forum public Structure A et B
- [x] Forum authentifié Structure A
- [x] Discussion publiée puis retrouvée après reload navigateur
- [x] Documents privés non exposés publiquement
- [x] Isolation multi-tenant A/B : dashboard/documents B refusés (403)
- [x] Événement structure créé en brouillon puis publié vers `/events/{id}/public`
- [x] Profil, wallet et CORS local
- [x] Portal login partenaire + bar/events API
- [x] Flutter APK lancé sur Android et health backend observé
- [x] Lien Flutter Structure → page Forum ajouté au code
- [x] Gift : deux expéditeurs avec même clé, balances/transactions isolées + retry stable
- [x] Documents Structure A/B : lecture et écriture étrangères refusées côté serveur
- [x] Finance Structure/Committee A/B : lecture et écriture étrangères refusées côté serveur
- [x] Structure Events/Pages : routes/API de création-publication et permissions couvertes par tests ciblés
- [x] Runtime event public → join réel et retry idempotent
- [ ] Discovery → Event Detail → Join → Event Hub → Profile visuel complet sur Android
- [ ] Wallet Admin / Bar Menu Admin visuel après login (API couvert, login préparé)
- [ ] PostgreSQL smoke

## ASTRA_REQUIRED
- PostgreSQL nécessite Docker/serveur disponible ; ne pas installer d’infrastructure lourde dans cette session.
