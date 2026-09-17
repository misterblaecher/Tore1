# TORÈ — inventaire de retrait de `lib/rebuild`

Date : 11 septembre 2026  
Branche : `chore/stabilisation-2026-09-11`  
Statut : **décision de convergence — aucune suppression effectuée par ce document**

## 1. Décision canonique

Le runtime Flutter actuel est :

```text
lib/main.dart
  -> ToreMvpApp
  -> core/
  -> features/
  -> shared/
  -> theme/
  -> ui/
```

`lib/rebuild/` **n'est plus le runtime public canonique**. Il ne doit pas être rebranché en bloc.

Les anciennes documentations qui déclarent `main.dart -> ToreRebuildApp` comme architecture cible sont historiques et ne doivent plus piloter de nouveaux changements.

Règle de convergence :

1. **MIGRER** uniquement les comportements encore utiles et absents du runtime actif.
2. **TEMPORAIRE** pour les dépendances nécessaires pendant ce transfert ; aucun nouveau code produit ne doit les importer.
3. **SUPPRIMER** lorsque le comportement est déjà couvert par l'architecture active ou qu'il s'agit d'un shell/showcase/adapter historique.
4. Avant toute suppression : Flutter analyze + tests verts, puis suppression en petits lots.

## 2. Résumé

Sur les **57 fichiers Dart** de `tore/app/lib/rebuild/` :

- **MIGRER : 6**
- **TEMPORAIRE : 9**
- **SUPPRIMER : 42**

La catégorie MIGRER signifie **porter le comportement vers l'architecture active**, pas déplacer le fichier tel quel.

## 3. MIGRER — comportement à conserver

| Fichier | Décision | Cible recommandée | Pourquoi |
|---|---|---|---|
| `config/link_builder.dart` | MIGRER | `core/routing/` ou `shared/links/` basé sur `AppConfig` | Génération centralisée de liens event/bar/menu. Ne pas conserver `AppEnvironment` ni les hosts historiques sans validation du domaine canonique. |
| `models/qr_resolve.dart` | MIGRER PARTIEL | `core/network/error_mapper.dart` + QR actif | Conserver surtout la normalisation des raisons QR et les messages UX utiles. Le modèle `QrResolve` est déjà remplacé par `QrResolveResult`. |
| `routing/deep_link_router.dart` | MIGRER | routeur actif / `ToreMvpApp.onGenerateRoute` + `CodeEntryDetector` | Le shell actif ne couvre actuellement que les routes opérationnelles, tandis que ce parser gère `tore://`, `app.tore.be/open`, event/bar/menu/qr. |
| `services/client_log.dart` | MIGRER PARTIEL | `core/logging/` | Conserver le scrub/redaction PII (`token`, JWT, email, téléphone, query params). Ne pas reprendre automatiquement le stockage historique dans SharedPreferences. |
| `services/remote_config.dart` | MIGRER | `core/config/` utilisant le `ApiClient` et `shared/cache/CacheStore` actifs | Le backend expose toujours `/mobile/remote-config`; le runtime actif ne doit pas perdre `disable_writes_global`, minimum de version/build et contrôle diagnostics. |
| `ui/screens/system/update_required_screen.dart` | MIGRER | écran actif utilisant `ui/app_design_system.dart` | UI associée au minimum de version / freeze global. À réécrire avec le design system actuel, pas avec les primitives rebuild. |

## 4. TEMPORAIRE — garder seulement pendant la migration

| Fichier | Raison temporaire | Condition de suppression |
|---|---|---|
| `config/app_environment.dart` | Dépendance de `link_builder`, remote config et ancien thème. | Après migration vers `AppConfig.environmentName`. |
| `models/backend_models.dart` | DTOs consommés par l'ancien `services/api_client.dart`. | Après vérification des contrats actifs et retrait de l'ancien client. |
| `models/error_model.dart` | Dépendance de l'ancien client / mapping QR. | Après transfert des raisons utiles vers `ErrorMapper`. |
| `models/event_context.dart` | Dépendance de l'ancien client. | Après validation que les providers/contextes actifs couvrent le contrat event. |
| `models/rebuild_types.dart` | Types de l'ancien shell/module catalog. | Après retrait des derniers écrans rebuild qui en dépendent. |
| `models/safe_parsing.dart` | Utilisé par plusieurs DTOs rebuild. | Après migration des quelques parseurs réellement utiles ; ne pas conserver comme seconde couche DTO par défaut. |
| `services/api_client.dart` | Contient encore l'appel remote config et sert de dépendance aux écrans/tests rebuild. | Dès que remote config/deep-link/erreurs utiles sont portés vers le client actif. Ne jamais le rebrancher au runtime. |
| `services/cache_store.dart` | Dépendance du remote config rebuild. | Utiliser exclusivement `shared/cache/cache_store.dart` après migration. |
| `ui/screens/dev/diagnostics_screen.dart` | Peut servir de référence pendant le transfert du scrubber et de remote config. | Supprimer après extraction des diagnostics réellement souhaités ; pas d'écran diagnostics rebuild en production. |

**Interdit pendant cette période :** ajouter une nouvelle feature ou un nouvel import depuis `lib/rebuild/`.

## 5. SUPPRIMER — doublons ou architecture historique

### 5.1 Modèles / routing / services

| Fichier | Motif |
|---|---|
| `models/snapshot.dart` | Ancien snapshot lié au shell rebuild et à l'ancien bootstrap. |
| `routing/adapter_routes.dart` | Pont historique V3 ↔ rebuild devenu inutile avec `ToreMvpApp`. |
| `routing/app_routes.dart` | Table de routes de l'ancien shell. |
| `routing/qr_router.dart` | L'ancien routeur cible `AppRoutes`; le routeur QR actif est plus riche et intégré à auth/context/network. |
| `routing/route_guards.dart` | Guards de l'ancien shell ; les guards opérationnels actifs vivent dans `features/operations`. |
| `services/contract_api.dart` | Interface minimale autour de l'ancien client QR, redondante avec les services/providers actifs. |
| `services/cursor_pager.dart` | Utilitaire orphelin ; ne pas garder une abstraction non utilisée "au cas où". |
| `services/idempotency_store.dart` | Store spécifique rebuild et writer simulé ; l'idempotence active doit rester au niveau des intentions réelles + headers serveur. |
| `services/network_state_resolver.dart` | Remplacé par `core/network/network_state_provider.dart`, retry et runtime write guards actifs. |
| `tore_rebuild_app.dart` | Ancien second app shell complet ; ne doit jamais redevenir un entrypoint. |

### 5.2 Adapters, catalogue et anciens shells UI

| Fichier | Motif |
|---|---|
| `ui/adapters/v3_adapter_screens.dart` | Pont de convergence historique. |
| `ui/module_catalog.dart` | Catalogue attaché au shell rebuild ; les modules actifs doivent provenir des contextes/capabilities/backend. |
| `ui/shell/top_icon_button.dart` | Ancien shell. |
| `ui/shell/tore_app_shell.dart` | Ancien shell. |
| `ui/shell/tore_bottom_nav.dart` | Navigation remplacée par `ToreMvpShell`. |
| `ui/shell/tore_shell_top_bar.dart` | Ancien shell. |
| `ui/shell/wallet_top_button.dart` | Ancien shell. |
| `ui/theme/tore_theme.dart` | Deuxième thème ; le canonique est `lib/theme/tore_theme.dart` + tokens actifs. |
| `ui/widgets/common_widgets.dart` | Stub/ancien widget. |
| `ui/widgets/primitives.dart` | Deuxième design system ; le canonique est `lib/ui/app_design_system.dart` et ses composants. |
| `ui/widgets/section_header.dart` | Primitive rebuild redondante. |

### 5.3 Écrans rebuild remplacés par les surfaces actives

| Fichier | Remplacement / décision |
|---|---|
| `ui/screens/access/access_actions.dart` | QR/entry actifs. |
| `ui/screens/access/access_quick_grid.dart` | QR/entry actifs. |
| `ui/screens/access/access_scan_frame.dart` | `features/qr/presentation/qr_scanner_screen.dart`. |
| `ui/screens/access/access_scanner_screen.dart` | Scanner actif déjà monté depuis `ToreMvpApp`. |
| `ui/screens/access/access_screen.dart` | Scanner / event context actifs. |
| `ui/screens/access/active_order_card.dart` | Menu/cart/orders actifs. |
| `ui/screens/bar/bar_screens.dart` | `features/bars` + `features/operations` BAR. |
| `ui/screens/forum/forum_cards.dart` | Le Forum/Portail Structures est web-first ; ne pas maintenir un second Forum mobile rebuild. |
| `ui/screens/forum/forum_screen.dart` | Même décision : Forum web, données partagées, pas second shell Forum mobile. |
| `ui/screens/help/runbook_screens.dart` | Runbooks/docs hors shell utilisateur rebuild. |
| `ui/screens/home/bars_preview.dart` | Discovery/Bars actifs. |
| `ui/screens/home/hero_status_card.dart` | Home discovery actif. |
| `ui/screens/home/home_screen.dart` | `DiscoveryScreen(compactHome: true)`. |
| `ui/screens/home/nearby_events_preview.dart` | Discovery actif. |
| `ui/screens/home/quick_actions.dart` | Navigation active. |
| `ui/screens/home/ticker_preview.dart` | Ancien aperçu associé au shell rebuild. |
| `ui/screens/orga/orga_exports_screen.dart` | ORGA opérationnel actif / portail ; ne pas conserver un second shell. |
| `ui/screens/orga/orga_screens.dart` | `EventOperationalHubScreen` actif. |
| `ui/screens/screen_view.dart` | Wrapper de l'ancien design system. |
| `ui/screens/showcase/showcase_screens.dart` | Showcase historique, jamais une surface production. |
| `ui/screens/user/user_screens.dart` | Monolithe UI USER rebuild remplacé par les features actives. |

## 6. Points de parité obligatoires avant suppression

### Deep links

Le comportement utile de `routing/deep_link_router.dart` doit être couvert dans l'architecture active avant suppression :

- `tore://...`
- compatibilité `https://app.tore.be/open?...`
- event
- join
- QR
- bar
- menu
- refus des hosts/schémas inconnus

Les domaines publics définitifs doivent être décidés au moment de la migration ; ne pas recopier aveuglément `tore.app`, `dev.tore.app` et `stage.tore.app`.

### QR / erreurs

Le `QrRouterService` actif reste canonique. Il faut seulement conserver/rapprocher les raisons utilisateur utiles de l'ancien mapping : QR expiré, replay, module off, event paused, backend down, unauthenticated, not found, invalid request, offline write blocked.

### Remote config

Avant retrait de `services/remote_config.dart`, le runtime actif doit consommer le contrat backend et couvrir :

- `disable_writes_global`
- `disable_writes_message`
- `min_supported_build`
- `min_supported_version`
- `diagnostics_enabled`
- cache court + fallback sûr

### Logging / PII

Avant retrait de `services/client_log.dart`, conserver des tests unitaires pour la redaction de :

- `Authorization` / Bearer
- token / JWT / secret / password / key
- email
- téléphone
- paramètres sensibles d'URL

## 7. Ordre de retrait recommandé

1. **PR/commit A — migration sans suppression** : deep links + link builder + remote config + update-required + redaction tests dans l'architecture active.
2. Flutter `analyze` + `test` verts.
3. **PR/commit B — suppression pure UI** : ancien app shell, shell widgets, home/user/bar/orga/forum/showcase/theme/primitives/adapters.
4. Flutter `analyze` + `test` verts.
5. **PR/commit C — suppression services/modèles rebuild** : ancien client, cache, DTOs, routing restant, tests rebuild remplacés ou supprimés.
6. Flutter `analyze` + `test` verts + smoke Discovery → Event Detail → Join → Event Hub → Profile.

## 8. Tests historiques `test/rebuild`

Les tests `tore/app/test/rebuild/*` ne doivent pas forcer la conservation de production code mort.

Règle :

- migrer vers les tests actifs ceux qui couvrent encore une propriété utile (deep links, redaction, QR safety, idempotence) ;
- supprimer les tests qui ne font que certifier l'ancien shell, les anciennes routes ou l'ancien thème ;
- aucun test ne doit réintroduire une dépendance runtime vers `lib/rebuild/`.

## 9. Done criteria

`lib/rebuild/` pourra être supprimé entièrement lorsque :

- le runtime ne référence aucun fichier rebuild ;
- les 6 comportements marqués MIGRER sont portés ou explicitement abandonnés ;
- les tests utiles ont été déplacés ;
- `flutter analyze` est vert ;
- `flutter test` est vert ;
- le smoke principal utilisateur est vert ;
- aucun nouveau code n'a été ajouté sous `lib/rebuild/` pendant la convergence.
