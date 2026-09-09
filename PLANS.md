# TORÈ — Convergence MVP et contenu public

Date d'audit : 13 août 2026
Périmètre actif : `tore/app` + contrats publics de `tore-backend`

## Décisions structurantes

- `lib/rebuild/` reste la direction visuelle, mais ne doit plus posséder sa propre session, son propre client réseau ni ses propres données métier.
- Riverpod, `core/network/ApiClient`, `AuthSessionNotifier`, les repositories de `features/` et `shared/cache/CacheStore` deviennent les frontières actives de l'application.
- Le premier lot remplace le bootstrap du rebuild par un shell discovery-first réel : accès invité/connexion, Home, détail événement, join, bars, profil et scanner contextuel.
- Les endpoints publics de discovery ne retournent que les événements `PUBLIC` + `PUBLISHED`; les événements terminés sont exclus par défaut.
- Les données absentes restent absentes dans l'UI. Aucun nom, identifiant, solde, statistique ou événement de démonstration ne sert de fallback de production.
- Le Portail Structures reste une surface web séparée. Le prototype Forum du rebuild n'entre pas dans le shell MVP.
- Aucun ancien fichier n'est supprimé dans ce lot. Les références et remplacements seront prouvés avant nettoyage.

## Matrice d'état au début du lot

| Fonctionnalité | État constaté | Décision de convergence |
|---|---|---|
| Session email / Google / invité | Réelle mais non accessible depuis le rebuild | Brancher le shell racine sur `authSessionProvider` |
| Client HTTP authentifié + refresh | Réel mais non utilisé par le rebuild | Utiliser exclusivement `core/network/ApiClient` |
| Rôles USER / ORGA / BAR | Partiellement connectés dans l'ancien code, mode rebuild forcé à USER | Hors du chemin critique MVP; dériver ensuite des capabilities serveur |
| Home rebuild | Démonstration locale | Remplacer par une Home Riverpod alimentée par `EventsRepository` et `BarsRepository` |
| Discovery globale | Endpoint `/events` réel mais contrat trop pauvre et non filtré | Étendre le contrat public avec filtres réels et métadonnées disponibles |
| Recherche / filtres | Absents du rebuild réel | Recherche, statut, date, bar et structure via query params backend |
| Event Detail | Ancien écran partiellement connecté | Enrichir le modèle et rendre le détail obligatoire avant join |
| Join | Endpoint réel et idempotent, UI partielle | Reuse `/join_public`, même clé par intention, double tap bloqué, erreurs explicites |
| Bars | Repository réel avec cache, écran non accessible | Intégrer la liste et une page bar réelle au shell MVP |
| Profil | API réelle, écran ancien partiel | Rendre l'édition pseudo, bio, photo URL et visibilité accessible; affiliations/historique au lot suivant |
| Scanner | Réel mais dominant dans le rebuild | Conserver comme onglet secondaire/raccourci contextuel |
| Connectivité / offline | Provider réel non branché au rebuild | Afficher une bannière discrète et bloquer les writes hors ligne |
| Cache events/bars | Partiel | Normaliser les résultats avec source cache + date de synchronisation |
| Forum mobile rebuild | Démonstration locale | Retirer du shell production; Portail web séparé |
| Wallet / ticker / Rooms / commandes | Réel ou partiel selon module, mais fixtures silencieuses dans le rebuild | Exclure du shell MVP jusqu'à connexion et critères propres |
| Identité Android | Nom/bundle configurés, icône à vérifier | Hors du lot vertical; finalisation plateforme dans un lot dédié |
| Identité iOS | Nom et bundle Flutter par défaut | Risque connu; finalisation plateforme dans un lot dédié |

## Doublons à résorber progressivement

- Clients réseau : `lib/rebuild/services/api_client.dart`, `lib/core/network/api_client.dart`, façade `lib/api.dart`.
- Caches : `lib/rebuild/services/cache_store.dart` et `lib/shared/cache/cache_store.dart`.
- Événements : DTOs rebuild, `shared/models/event.dart`, `EventSummary`, `EventPublicView` et maps de `lib/api.dart`.
- Thèmes/composants : `lib/rebuild/ui/theme`, `lib/theme`, `lib/ui`, `lib/shared/widgets`.
- Shells/navigation : `ToreRebuildApp`, `AppShell` et écrans de navigation historiques.

La convergence se fait par adoption dans le chemin actif, puis suppression ultérieure après preuve de non-référence.

## Architecture cible

```text
main.dart
  ProviderScope
    Auth/session gate
      MVP presentation shell
        Riverpod providers
          repositories
            core ApiClient + auth interceptor
            shared cache
              backend commun
```

Les widgets ne font pas de requêtes réseau directes. Les repositories exposent des résultats typés comprenant la fraîcheur du cache. Les écritures sensibles reçoivent une clé d'idempotence stable pour l'intention courante.

## Lots de migration

1. **Lot vertical MVP Discovery** — shell authentifié/invité, Home réelle, filtres, Event Detail, join idempotent, bars, profil et scanner contextuel dans l'AppBar. **Implémenté dans ce jalon.**
2. **Profil et rôles** — profil V2 complet, affiliations serveur, visibilité, historique opt-in, mode switch capability-driven.
3. **Offline explicite** — cache daté homogène, invalidation, états dégradés, politique par opération.
4. **Identité plateforme** — icônes, splash, nom et bundle iOS, revue Android.
5. **Nettoyage prouvé** — supprimer les branches rebuild/legacy devenues sans référence, après couverture de navigation et tests.

## Dépendances et contrats

- `/auth/guest`, `/auth/email/*`, `/auth/google`, `/auth/me`
- `GET /events` avec filtres publics et pagination/limite bornée
- `GET /events/{id}/public`
- `POST /events/{id}/join_public` avec `Idempotency-Key`
- `GET /bars` et `GET /bars/{id}/events`
- `GET/PATCH /auth/me` et `GET/PUT /me/profile`

Champs encore absents du modèle de données backend pour un Event Detail complet : image/bannière dédiée, description publique persistable, capacité/places et type d'événement. Le contrat expose explicitement `description: null` tant que le schéma ne permet pas de la renseigner; l'UI affiche alors un état absent sans l'inventer.

## Risques

- Le singleton historique `ApiClient` complique les overrides de tests; ne pas multiplier les instances en production.
- Les anciens endpoints et modèles utilisent plusieurs conventions de nommage.
- Le backend monolithique rend les petites évolutions de contrat sensibles aux régressions.
- Le mode invité possède un vrai token backend; il doit rester clairement présenté comme invité et non comme faux compte.
- La base actuelle ne permet pas tous les filtres roadmap (quartier/type/proximité précise) sans évolution de schéma.

## Critères d'acceptation du lot vertical

- Un utilisateur choisit invité ou connexion avant d'entrer dans le shell.
- La Home et la liste affichent uniquement les événements renvoyés par le repository, ou un état loading/empty/error/cache explicite.
- Recherche et filtres réellement supportés modifient la requête backend.
- Toute carte ouvre Event Detail avant le join.
- Le join utilise le backend, conserve sa clé pendant l'intention et ignore les doubles taps.
- Les erreurs 401/403/404/409/429/5xx et l'offline n'affichent jamais un faux succès.
- Les bars et leurs événements sont issus du backend/cache.
- Le scanner reste accessible sans dominer la Home.
- Aucune fixture rebuild n'est accessible dans le shell de production.

## Validation

```text
dart format lib test
flutter analyze
flutter test
flutter build apk --debug --flavor dev

tore-backend/.venv/Scripts/python.exe -m pytest -q \
  tests/test_discovery_events.py \
  tests/test_join_event_flow.py \
  tests/test_bar_events_endpoint.py \
  tests/test_auth_real.py
```

## Résultat du jalon

- `flutter analyze` : aucun problème.
- `flutter test` : 124 tests réussis après le Lot 2.
- Backend : 341 tests réussis après le Lot 2; les avertissements restants concernent les dépréciations historiques `datetime.utcnow()` et FastAPI `on_event`.
- Android : APK dev et prod debug générés dans `tore/app/build/app/outputs/flutter-apk/`.
- Contrôle production : le point d'entrée actif ne référence plus `ToreRebuildApp`, ses fixtures, `_applyShowcaseDefaults()` ni `fetchMeSnapshot()`.

Limites encore reportées : filtre quartier/proximité GPS (aucune permission de localisation ni calcul de distance fiable), historique de profil opt-in, affiliations détaillées et sélecteur ORGA/BAR. L'identité visuelle iOS est migrée; seul son bundle reste en attente de confirmation Apple (`com.example.mobile` → `be.tore.app`).

## Portail factuel avant Lot 2 — 13 août 2026

Le flux d'exécution actif a été suivi depuis `main.dart` jusqu'aux appels HTTP :

- `ProviderScope` démarre `ToreMvpApp`, puis le gate de session réel choisit connexion, invité ou shell.
- Discovery appelle réellement `GET /events`; le détail appelle `GET /events/{id}/public`; le join appelle `POST /events/{id}/join_public` avec une clé d'idempotence stable.
- L'écran de join bloque le double tap, l'absence de session et l'offline avant toute écriture.
- Les événements privés, brouillons ou terminés restent absents des lectures publiques.
- Bars et profil proviennent des repositories réels; les caches datent leur dernière synchronisation.
- Le point d'entrée ne référence aucune donnée de showcase. Le dernier import visuel situé sous `rebuild/` a été remplacé par le thème central actif.

Preuves ajoutées au gate : interaction invité jusqu'à la frontière repository, premier succès réseau puis relecture cache, Home vide/erreur, et garde statique anti-fixtures. Le libellé « Structures suivies » a été corrigé en « Structures », car le backend ne fournit pas encore ce sous-ensemble dans cette vue.

## Lot 2 — contenu public Event et Bar

### Schéma et compatibilité

La migration additive `0007_public_content_branding` enrichit les lignes existantes sans les recréer :

- Event : description complète/courte, bannière, vignette, type, capacité déclarée, type d'accès, devise, adresse, ville et coordonnées. Le prix existant `entry_price_cents` reste la source de vérité.
- Bar : description, logo, bannière, couleurs, adresse, informations pratiques, lien carte, modules publics, statut partenaire et visibilité publique.
- Les anciens événements reçoivent `EUR`; les anciens bars restent `ACTIVE` et `PUBLIC`. Les médias et autres métadonnées facultatives restent `null` et l'UI affiche alors un fallback graphique, jamais une donnée inventée.

Les URLs publiques acceptent uniquement HTTP(S), les couleurs suivent `#RRGGBB`, les coordonnées et capacités sont bornées. Les écritures bar exigent le rôle manager du bar. Les écritures événement exigent le propriétaire utilisateur ou un OWNER/MANAGER de la structure hôte.

### Contrats et cache mobile

- `GET /events`, `GET /events/{id}/public` et `GET /bars/{id}/events` exposent les métadonnées riches réellement persistées.
- `GET /bars/{id}/public` alimente la page publique du bar.
- `PATCH /partner/portal/bar`, les créations/mises à jour événement du portail et `PATCH /events/{id}/public-content` portent les écritures autorisées.
- Clés de cache migrées : `discovery_events_v2_*`, `event_detail_v3_*`, `bars_v2_list`, `bar_v2_detail_*`, `bar_v2_events_*`. Une ancienne forme ne peut donc pas être relue sous le nouveau contrat.
- Le mobile revalide URL et couleur avant rendu; une image inaccessible retombe sur un visuel TORÈ sobre.

### Surfaces produit

- Home : recherche, catégories Tout/Live/Ce soir/À venir, filtre ville réel, raccourcis Bars et Structures, états chargement/vide/erreur/cache.
- Event Detail : média réel ou fallback, titre/type/état, horaires, lieu/adresse, organisateur, prix/devise, accès, capacité déclarée, description, modules, page bar, join puis partage.
- Bar : identité et bannière réelles, logo, description, informations pratiques, modules, carte et soirées publiques à venir. La page recharge son propre modèle par identifiant, sans dépendre d'un résumé de navigation.

### Design et identité native

- Le thème actif utilise les tokens TORÈ centraux : nuit, rubis, or, surfaces, espacements et rayons cohérents; aucune dépendance active au thème du showcase rebuild.
- Android : `be.tore.app` en production, `be.tore.app.dev` en dev, nom TORÈ/TORÈ Dev, icônes classiques/rondes/adaptatives TORÈ, splash nuit, schéma `tore://` et App Link `https://app.tore.be/open`.
- iOS : nom affiché TORÈ, icônes TORÈ sans alpha, splash nuit, schéma `tore://`, entitlement `applinks:app.tore.be` et texte caméra explicite.
- Le bundle iOS reste temporairement `com.example.mobile`. La consigne impose une confirmation Apple explicite avant de le remplacer par `be.tore.app`; cette confirmation n'est pas déductible du dépôt.

## Critères Lot 2 et statut

- [x] Migration additive et compatibilité d'une ligne historique testées.
- [x] Lectures publiques riches sans exposition d'événements privés/brouillons/terminés.
- [x] Écritures Event/Bar réellement autorisées et entrées invalides rejetées.
- [x] Modèles et caches versionnés côté Flutter.
- [x] Home, Event Detail et Bar Detail utilisent uniquement des données réelles ou des fallbacks graphiques explicites.
- [x] Identité Android complète et identité visuelle iOS complète.
- [ ] Bundle iOS final : attente de confirmation Apple pour `be.tore.app`.
- [ ] Build iOS : à exécuter sur macOS/Xcode; indisponible depuis l'environnement Windows actuel.

Validation finale Lot 2 : `flutter analyze` sans problème, 124 tests Flutter réussis, 341 tests backend réussis, migration Alembic jusqu'à `0007_public_content_branding (head)` vérifiée sur une base neuve, métadonnées XML/plist valides, 15 icônes iOS sans canal alpha, et APK debug dev/prod générés.

## Lot 3 — audit d'identité et matrice de convergence (avant schéma)

Audit établi le 13 août 2026 avant toute migration Lot 3. Principe directeur : `AppUser.id` reste l'identifiant TORÈ immuable; aucune saisie de profil ne crée un droit. Les capacités sont recalculées côté serveur depuis les appartenances actives à chaque requête protégée.

| Entité existante | Source d'autorité actuelle | Champs sains | Manques / doublons constatés | Compatibilité | Décision de convergence |
|---|---|---|---|---|---|
| `AppUser` | Auth app + token haché en base | UUID, affichage, avatar, bio, création, email/téléphone privés, suppression | Pas de pseudo unique, ville dédiée, `updated_at`, statut explicite ni rôle global; `address_text` ne doit pas devenir public | Bonne; extensions nullables possibles | Identité TORÈ canonique. Ajouter pseudo, ville, dates/statut et rôle global administré; conserver les champs privés hors des serializers publics. |
| `AppUserPrivacySetting` + anciens booléens `AppUser` | Propriétaire via `/auth/me` | Une ligne par user, consentements Bar, visibilité grossière | Visibilités dupliquées (`profile_visibility`, `visibility`, `show_*`); pas de politique par section; défaut historique trop public | À normaliser avec fallback conservateur | Étendre cette table, niveaux `PUBLIC`/`TORE_USERS`/`PRIVATE`, privé par défaut, historique explicitement opt-in. Les valeurs inconnues sont interprétées `PRIVATE`. |
| `/auth/me` et `/me/profile` | Session app | Lecture/écriture de champs profil | Deux contrats, exposition mêlée de préférences et mode; schémas `dict`; ancien `/users/{id}` trop pauvre | Maintenir les routes anciennes | Créer des contrats profil owner/public/contextuel dédiés; garder `/auth/me` compatible mais sans en faire la preuve d'autorisation. |
| `account_mode` + `RoleUpgradeRequest` | Code partagé + approbation admin historique | Mode UI persisté | Confond mode et permission; noms `organizer/team`; secret statique; le client en déduit ORGA/BAR | À déprécier sans suppression | `account_mode` devient un simple héritage non autorisant. Les modes disponibles viennent exclusivement de `/me/capabilities`. |
| `Organization` | Créateur et responsables de structure | Identité publique, visibilité, workflow d'adhésion/invitation | Aucun logo propre (ancien `logoUrl` écrit dans `website_url`) | Bonne | Structure canonique pour les affiliations du profil. Ne pas créer de nouvelle table Structure. |
| `OrganizationMembership` | Invitation, join policy ou responsable `MANAGER+` | Lien user/structure, rôle, statut, audit de création | Dates de mandat/fin/révocation, visibilité, validateur et origine absents; rôles `OWNER/MANAGER/MEMBER/FOLLOWER` plus courts que la cible | Très bonne, additive | Devient l'affiliation canonique. Étendre la ligne; `ACTIVE` seul autorise, `ENDED/REVOKED/REJECTED/PENDING` restent descriptifs. Mapper `MANAGER` vers fonctions de bureau sans inventer un titre. |
| `CommitteeMembership` / invites Committee | Responsables Committee | Membre, rôle, année et invitation | Second modèle de structure, `is_active` au lieu d'un statut riche | Historique compatible | Conserver pour les modules Committee; exposer plus tard comme affiliation legacy non autorisante tant qu'aucun lien fiable Organization↔Committee n'existe. |
| `EventStaff` | Invitation Event ou hôte autorisé | User app, event, rôle, activation et révocation | Pas d'expiration; nomenclature `entry/bar/manager/helper` | Bonne, additive | Source contextuelle Event. Ajouter expiration; mapper vers `ENTRY_STAFF`, `BAR_STAFF`, `EVENT_MANAGER`, `EVENT_STAFF`; contrôle serveur à chaque accès. |
| `EventStaffAssignment` et QR/invites Staff | Hôte / partenaire autorisé | Rôle, création, expiration des invitations, révocation d'assignment | Lié surtout à `PartnerUser`, chevauche `EventStaff` | À conserver | Workflow d'émission; une acceptation app converge vers `EventStaff`. Ne pas créer de troisième système Event. |
| `PartnerUser`, `PartnerBarAccess`, `PartnerMembership` | Auth partenaire PIN/magic link + responsables Bar | Rôles owner/manager/staff/bartender, activation | Identité partenaire entière séparée de `AppUser`; deux tables Bar proches | Nécessite un pont nullable | Conserver l'autorité Bar existante. Ajouter un lien optionnel contrôlé `PartnerUser.app_user_id`; seule une liaison validée peut produire des capacités Bar dans la session app. |
| Tokens app/refresh et auth interceptor Flutter | Hash serveur; jetons bruts côté appareil | Rotation refresh, révocation serveur | Jetons stockés dans `SharedPreferences`; cache privé non invalidé; traces partielles de token en debug | À corriger immédiatement | Utiliser `flutter_secure_storage`; migrer/supprimer les anciennes clés; vider tous les namespaces privés au logout/401. |
| Caches Flutter partagés/Community | `SharedPreferences` | TTL et caches publics disponibles | Pas de namespace user systématique; caches owner/capabilities/affiliations absents; plusieurs stores | Compatible | Cache public séparé; quatre espaces explicites public/owner/capabilities/affiliations, privés préfixés par user ID et invalidables ensemble. |
| Guards/providers Flutter | `AuthSessionNotifier`, `meProvider`, plusieurs providers métier | Session centralisée et signal 401 | UI déduit ORGA/BAR de `accountMode`; `tryMe` assimile aussi 403 à session invalide | À normaliser | Un provider capabilities serveur pilote uniquement l'accès visuel; le backend reste l'autorité. Un 401 purge secrets/caches; un 403 métier ne détruit pas la session. |
| Audit logs existants | `write_audit_log` | Acteur, action, entité, scope et payload | Couverture inégale des changements d'identité/affiliation | Bonne | Réutiliser le journal existant pour confidentialité, rôle global, validation et révocation; aucune donnée sensible dans le payload. |

### Matrice de visibilité retenue

Chaque section a son niveau propre. `PRIVATE` autorise uniquement le propriétaire et un rôle global `SUPPORT`/`ADMIN`; `TORE_USERS` ajoute les sessions app authentifiées non invitées; `PUBLIC` ajoute les visiteurs anonymes. Le profil général conditionne toute la réponse, puis la règle de chaque section restreint encore les champs. Photo, bio, affiliations et badges sont privés par défaut après migration. Historique d'événements, participations et statistiques restent masqués tant que leur opt-in n'est pas vrai, même si leur niveau vaut `PUBLIC`. Les affiliations non `ACTIVE`, les mandats internes et toute ligne marquée `PRIVATE` ne sont jamais publiés. Email, téléphone, adresse, tokens, paiements, modération et sécurité ne figurent dans aucun schéma public.

### Correspondance des rôles sans rupture

- Global : nouveau `USER` (défaut), `SUPPORT`, `ADMIN`; modification réservée aux procédures administratives.
- Structure : `OWNER` reste owner; `MANAGER` couvre provisoirement les fonctions autorisées de bureau; `MEMBER` et `FOLLOWER` restent inchangés. Les intitulés `PRESIDENT`, `BUREAU`, `TRESORIER`, `STAFF`, `ALUMNI` sont acceptés dans le contrat étendu, sans promotion automatique d'une ancienne chaîne libre.
- Event : `manager` → `EVENT_MANAGER`, `entry` → `ENTRY_STAFF`, `bar` → `BAR_STAFF`, `helper` → `EVENT_STAFF`.
- Bar : `PartnerBarAccess`/`PartnerMembership` restent l'autorité; `owner|manager` ouvre la gestion Bar et `staff|bartender` une capacité staff, uniquement si le partenaire est explicitement relié au même `AppUser`.

Les rôles temporaires expirés et les affiliations révoquées sont filtrés au moment de calculer les capacités. Aucune capacité n'est embarquée durablement dans le token : une révocation devient donc effective à la requête suivante.

## Lot 3 — réalisation et validation finale

### Convergence livrée

- `AppUser` reste l'identité TORÈ unique. Il porte désormais pseudo unique, ville, mise à jour, statut de compte, rôle global administré et distinction explicite invité/compte enregistré.
- `AppUserPrivacySetting` est la source des niveaux de visibilité par section. Tout profil ancien ou toute valeur inconnue migre vers `PRIVATE`.
- `OrganizationMembership` est l'affiliation canonique : mandat, dates, visibilité, origine/validateur et révocation auditée. Les anciennes chaînes libres restent `LEGACY`, privées et non autorisantes.
- `EventStaff` reste la source des rôles Event et reçoit une expiration. L'autorité Bar existante est préservée via un pont nullable validé entre `PartnerUser` et `AppUser`.
- `account_mode` reste lisible pour rétrocompatibilité mais ne prouve plus aucune permission. Les modes ORGA/BAR actifs proviennent exclusivement des capabilities recalculées par le serveur.

### Migration et contrats

La migration additive `0008_unified_profile_affiliations` étend les tables existantes sans en créer un système parallèle. Elle est idempotente face à la baseline historique, garde les anciens profils privés, ne transforme aucun intitulé libre en rôle et possède un downgrade testé vers `0007_public_content_branding`.

Endpoints ajoutés ou normalisés :

- `GET /me/profile`, `PATCH /me/profile`, `PATCH /me/privacy` ;
- `GET /profiles/{user_id}` et compatibilité contextuelle de `GET /users/{user_id}` ;
- `GET /me/affiliations`, `GET /me/capabilities` ;
- `GET /me/profile/preview?as=PUBLIC|TORE_USER|OWNER` ;
- `POST /affiliations/{affiliation_id}/revoke` ;
- workflows Organization existants réutilisés pour invitation, demande, approbation et adhésion selon la politique de la structure.

Les payloads profil refusent tout champ inconnu, notamment rôles, admin, capabilities et affiliations. Les changements de profil/confidentialité et révocations produisent un `AuditLog` sans donnée d'authentification.

### Visibilité exacte

Le profil général est le premier verrou; chaque section ne peut qu'être aussi restrictive ou davantage. `PUBLIC` autorise l'anonyme, `TORE_USERS` un compte TORÈ authentifié non invité, `PRIVATE` uniquement propriétaire et `SUPPORT`/`ADMIN`. Photo, bio, affiliations, badges, historique, participations et gamification sont privés par défaut. Historique, participations et gamification exigent en plus leur opt-in. Un historique visible ne publie aux tiers que des événements eux-mêmes `PUBLIC` et `PUBLISHED`. Une affiliation publique doit être `ACTIVE`, non révoquée et explicitement visible. Les réponses contextuelles n'exposent jamais email, téléphone, adresse, token, paiement, modération ou sécurité.

### Flutter et sécurité locale

Le Profil V2 actif couvre invité, session expirée, chargement, erreur, profil minimal/complet, édition persistée, conflit de pseudo, confidentialité, aperçu serveur, affiliations, cache daté et rôles réels. Les sections XP, victoires, classements, badges et gamification sont absentes faute de données réelles. Home et Discovery consomment le provider de capabilities serveur.

Les tokens ont migré de `SharedPreferences` vers `flutter_secure_storage`; les anciennes clés sont supprimées. Les caches public, owner, capabilities et affiliations sont séparés; les trois espaces privés sont namespacés par user ID et purgés au logout ou après échec de refresh. Une capability relue offline ne peut jamais rouvrir un mode opérationnel.

### Résultats au 13 août 2026

- Checkpoint Lots 1–2 : commit local `cfea0e2` (`feat: checkpoint TORÈ lots 1 et 2`), non poussé.
- Backend complet : 353 tests réussis. Les avertissements sont les dépréciations historiques FastAPI `on_event` et `datetime.utcnow()`.
- Flutter : `dart format lib test`, `flutter analyze` sans problème et 141 tests réussis.
- Migration : base neuve jusqu'à `0008_unified_profile_affiliations`, montée depuis `0007` avec profil/affiliation legacy, valeur inconnue conservatrice, et downgrade vers `0007` réussis.
- Android : `app-dev-debug.apk` et `app-prod-debug.apk` générés, tous deux ignorés par Git.
- iOS : identifiants préparés dans `BundleIdentifiers.xcconfig` (`com.example.mobile.dev` / `com.example.mobile`). L'identifiant production `be.tore.app` reste à confirmer et réserver dans Apple Developer. Aucun build iOS n'est déclaré depuis Windows.

### Dette et prochain lot

Le backend demeure un monolithe et conserve les anciennes routes `account_mode`/role-upgrade uniquement pour compatibilité; elles devront être dépréciées puis supprimées après migration de tous les consommateurs. `CommitteeMembership` ne peut pas encore converger automatiquement sans lien fiable Committee↔Organization. Le singleton Flutter `ApiClient` complique toujours l'isolation des tests. Les warnings de dates UTC et de lifespan sont historiques.

Prochain lot recommandé : surfaces ORGA/BAR minimales pilotées par `/me/capabilities`, avec navigation refusée par défaut, revalidation serveur à chaque écriture, acceptation d'invitations app→Event/Bar, et aucun dashboard complet avant stabilisation de ces contrats.

## Lot 4 — audit opérationnel avant schéma

Audit établi le 14 août 2026 après le checkpoint Lot 3 `5116675`. Le Lot 4 réutilise les autorités existantes et ne crée ni second registre de staff, ni seconde table de commandes.

| Domaine | Existant | Autorité | Réutilisable | Manquant / risque | Décision Lot 4 |
|---|---|---|---|---|---|
| Staff Event | `EventStaff`, rôles `admin/manager/entry/bar/helper`, révocation et expiration | Session AppUser + ligne Event scopée | Oui, table canonique | Le resolver historique ignore `manager` et l'hôte; événement terminé encore visible | Centraliser le calcul d'actions Event, filtrer expiration/révocation/fin d'Event et garder `EventStaff` comme seul droit opérationnel. |
| Invitations Event principales | `EventStaffInviteCode`, idempotence, expiration, rotation et audit | Hôte Event / responsable de structure | Oui, même table et même workflow | Code brut, non ciblé, réutilisable, statut `ACTIVE` trop pauvre | Étendre additivement la table avec hash, cible, actions, acceptation et usage unique. Les routes legacy restent compatibles mais ne servent pas au nouveau parcours sécurisé. |
| Invitations/QR historiques | `StaffInviteToken`, `EventQrToken`, codes backup hashés | Staff/admin Partner ou App | Partiel | `StaffInviteToken` stocke le brut; systèmes plus anciens et multi-usages | Classer `StaffInviteToken` legacy. Réutiliser le hashing des backup codes et ne jamais journaliser le token du nouveau parcours. |
| Entrée | `EventStaff`, `/events/{id}/entry/checkin`, compteurs/logs, idempotence et audit | Backend Event + feature `entry_enabled` | Oui | L'ancien écran met les scans en queue et affiche `PENDING SYNC`; context global non autorisant | Réutiliser le service/check-in réel, imposer l'Event du contexte validé et bloquer totalement les scans offline dans le parcours Lot 4. |
| Anti-double scan | `EntryLog` par idempotency key, `EntryScanLog` par hash/scan ID, suppression locale courte | Backend | Oui | Plusieurs endpoints historiques | Le hub Lot 4 appelle le check-in idempotent existant; double détection locale et décision serveur restent cumulées. |
| Accès Bar | `PartnerUser`, `PartnerBarAccess`, `PartnerMembership`, pont `app_user_id` | Auth Partner + lien AppUser explicite | Oui | Validité, source, actions, statut et révocation absents de `PartnerBarAccess` | Étendre `PartnerBarAccess`; conserver `PartnerMembership` comme source legacy compatible et non modifiable depuis le profil. |
| Invitations Bar | `PartnerInvite` | Portail Partner | Partiel | Pas de claim sécurisé AppUser et aucun besoin minimal si un accès relié existe déjà | Ne pas créer un second workflow dans ce lot. Le parcours mobile exige un `PartnerUser.app_user_id` et un accès Bar actif existant. |
| Commandes | `Order`, `OrderStatusTransitionIdempotency`, services Orders et routes Partner | Bar de la commande + rôle Partner | Oui | Aucune route AppUser bridgée; transition idempotente enfermée dans le router Partner | Extraire/réutiliser la transition idempotente et exposer des routes AppUser strictement scopées au Bar autorisé. |
| Isolation commandes | `_assert_order_bar_access`, `patch_order_status` | `order.bar_id == bar autorisé` | Oui | Preuve actuellement liée au token Partner | Réutiliser la même comparaison côté service avec capability AppUser recalculée; l'ID fourni ne suffit jamais. |
| Capabilities | `/me/capabilities` Lot 3 | Backend à chaque requête | Oui | Réponse par rôles, actions et origine incomplètes; Event terminé non filtré | Ajouter une liste uniforme de capabilities stables et scopées, garder les agrégats `events/bars/structures` pour compatibilité. |
| Contextes Flutter | `AppContextController` et quelques caches rebuild | Sélection locale | Partiel | Clés globales, non namespacées, restauration sans revalidation | Créer un contexte opérationnel user-namespacé; la sélection n'accorde jamais un droit et disparaît au logout/révocation. |
| Modes/guards Flutter | capabilities Lot 3, anciens `RouteGuards` rebuild | Mélange serveur/client | Partiel | Rebuild contient fixtures et `account_mode`; pas adapté au shell actif | Nouveau guard pur deny-by-default fondé sur capability+scope. Ne pas réactiver le rebuild/showcase. |
| Deep links/QR | parser, resolver, scanner gate, routes rebuild | Payload puis backend | Partiel | Paramètres route/ID pourraient être pris comme preuve | Toute route opérationnelle attend session, capabilities fraîches, action et scope concordants avant navigation. |
| Caches opérationnels | `CacheStore` privé Lot 3 et cache rebuild | SharedPreferences | Partiel | Pas de namespace mode/scope | Ajouter clés `ops.<user>.<type>.<scope>`; purge avec les caches privés et aucune réouverture de droit depuis l'offline. |
| Audit/idempotence | `AuditLog`, `EventAuditLog`, plusieurs tables idempotency | Backend | Oui | Conventions fragmentées | Réutiliser `AuditLog` et les tables existantes; token brut exclu des payloads. |

### Architecture retenue avant implémentation

- `app/services/operational_access_service.py` portera le calcul des capabilities et les guards Event/Bar testables sans FastAPI.
- `app/services/event_staff_invitation_service.py` portera émission hashée, acceptation idempotente, replay/expiration/cible et révocation sur `EventStaffInviteCode`/`EventStaff`.
- Un router fin `app/routers/operational_access.py` exposera hubs, staff, invitations et commandes AppUser; chaque endpoint revalidera le scope.
- La state machine Order reste celle de `orders_service`; son chemin idempotent sera partagé avec les routes Partner existantes.
- Flutter recevra un domaine `features/operations/` avec modèles, repository, contexte namespacé, guard central et hubs minimaux. Les widgets n'interpréteront jamais `account_mode`.
- Offline Entry : refus explicite. Aucun QR/ticket brut n'est ajouté à une queue locale par le nouveau parcours.

## Lot 4 — réalisation et validation finale

### Autorité et parcours livrés

- `/me/capabilities` expose désormais des objets uniformes `EVENT` et `BAR` avec scope, actions, source, activation, expiration, statut et mise à jour. Les listes scopées sont l'autorité opérationnelle; le booléen historique `modes.organizer` reste seulement compatible avec le Lot 3 et `operational_modes` reflète strictement les contextes utilisables.
- Le workflow Event sécurisé étend `EventStaffInviteCode` : cible AppUser, token opaque stocké uniquement sous SHA-256, expiration obligatoire, usage unique, acceptation idempotente, déclin, révocation et audit sans token brut. L'acceptation active la ligne canonique `EventStaff`.
- Le mode USER demeure le défaut. Le shell actif n'affiche ORGA ou BAR qu'à partir d'une capability scopée fraîche, demande le contexte si plusieurs existent et persiste seulement la sélection dans `tore_cache.operations.<user>.<type>.<scope>`.
- Les hubs lisent les données réelles : Event/état/horaires/rôle/actions/entrées/staff/invitations et Bar/identité/statut/rôle/actions/commandes. Aucune donnée financière, statistique ou showcase n'a été ajoutée.
- Le parcours Entry existant est conservé mais toute validation ou correction est bloquée hors ligne. Une panne ne produit plus `PENDING SYNC`, n'incrémente plus l'affichage et ne conserve plus de QR dans la queue depuis cet écran.
- Les transitions Order partagent la state machine et l'idempotence existantes. Les écritures AppUser vérifient capability, `bar_id`, état Event et transition; l'interface verrouille une commande pendant l'écriture et rafraîchit après confirmation serveur.

### Revalidation et refus par défaut

Les capabilities sont relues à la connexion, après acceptation/révocation, au changement de mode, au retour au premier plan, au retour réseau et après `401/403`. Le cache des données de hub est court (5 minutes), séparé par utilisateur/type/scope et strictement en lecture seule offline. Les capabilities opérationnelles ne sont jamais restaurées depuis ce cache. Toute sélection devenue absente repasse immédiatement à USER et supprime le contexte. Les routes nommées/deep links `event-staff-invite`, `/ops/event/{id}` et `/ops/bar/{id}` passent par session, capabilities, action et scope avant affichage.

### Résultats au 14 août 2026

- Checkpoint Lot 3 : commit local `5116675` (`feat: add unified profiles privacy and affiliations`), non poussé.
- Backend complet : 363 tests réussis; 7 931 avertissements historiques de dépréciation, aucun échec.
- Flutter complet : 154 tests réussis; `flutter analyze` sans problème.
- Migrations : base neuve jusqu'à `0009_scoped_operational_access`, montée depuis `0008` avec ligne Partner legacy préservée et downgrade vers `0008` réussis.
- Android release : `app-dev-release.apk` et `app-prod-release.apk` générés (96,9 Mo chacun), ignorés par Git.
- Contrôles finaux : `git diff --check` propre; aucun APK/AAB suivi; aucun secret, fixture/showcase ou nouvel usage autorisant de `account_mode` dans le Lot 4.

### Dette conservée

Les anciennes invitations QR/code et routes Partner restent en place pour compatibilité et devront être dépréciées progressivement. `PartnerMembership` reste un fallback Bar sans période explicite faute de métadonnée legacy; son lien AppUser explicite et l'état actif du Bar restent obligatoires. Le backend historique demeure volumineux et produit encore de nombreux warnings `datetime.utcnow()`/FastAPI, mais les nouvelles règles Lot 4 sont isolées dans des services dédiés.
