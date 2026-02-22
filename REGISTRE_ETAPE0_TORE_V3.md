# REGISTRE ÉTAPE 0 — TORÈ V3

## 1) Inventaire des écrans existants
- Boot/splash et entrée session: `lib/main.dart` (`_BootEntry`, `_BootSplash`).
- Auth: `auth_gate_screen.dart`, `email_auth_screen.dart`, `complete_profile_screen.dart`.
- Shell navigation: `lib/app_shell.dart`.
- Tabs principales actuelles:
  - Home territoire: `home_territory_feed_screen.dart`.
  - Events discovery: `events_discovery_screen.dart`.
  - Polymarket tab: `polymarket_tab_screen.dart`.
  - Profil: `profile_screen.dart`.
- Scan/QR:
  - Scanner: `qr_scanner_screen.dart`.
  - Router: `qr_router.dart`.
  - Écrans QR statut/erreur: `features/qr/presentation/*`.

## 2) Navigation actuelle (shell, bottom nav, router)
- `AppShell` = 4 tabs + FAB scan central (`FloatingActionButtonLocation.centerFloat`), via `IndexedStack` et `Navigator` par tab.
- Bottom nav actuelle: Home / Events / (Scan en centre) / Polymarket / Profil.
- Deep links gérés dans `main.dart` (`onGenerateRoute`) pour `tore://open` et `https://app.tore.be/open`.
- QR routing métier géré dans `features/qr/qr_router.dart`.

## 3) Auth flow actuel
- OTP email:
  - Demande OTP: `/auth/email/request_otp`.
  - Vérification OTP: `/auth/email/verify_otp`.
- Guest:
  - Activation guest via `authSessionProvider.notifier.continueAsGuest()` + `/auth/guest`.
- CompleteProfile:
  - `main.dart` force `CompleteProfileScreen` si user auth et `displayName` vide.
- Role upgrade organizer/team:
  - Depuis `ProfileScreen` via `requestRoleUpgrade(mode, code)` (`/auth/role/request-upgrade`).

## 4) QR router formats supportés
- Préfixes type `event_checkin:`, `bar:`, `profile:` supportés via parser colon format.
- JSON QR (`{...}`) supporté.
- URI/deep link supporté (`tore://`, `https://`) avec mapping type.
- Types: join_event, menu, staff_entry, staff_bar, wifi, hunt, battle, order, polymarket, orga, staff_invite, staff_backup, orga_invite, bar_profile, user_profile.

## 5) Endpoints utilisés (socle)
- Auth: `/auth/guest`, `/auth/me`, `/auth/google`, `/auth/email/request_otp`, `/auth/email/verify_otp`, `/auth/refresh`, `/auth/upgrade_guest`, `/auth/role/request-upgrade`.
- Core app: bars/events via `Api` (`api.dart`), polymarket list/create/positions/detail via services existants.
- Orders/menu/event modules existants déjà branchés, sans ajout d’endpoint requis pour TORÈ V3.

## 6) Design system actuel
- Fichier central: `lib/ui/app_design_system.dart`.
- Existant: `SolarBackground`, `AppCard`, `PrimaryButton`, `AppChip`, `SectionTitle`.
- Palette déjà proche Solar (noir, or, rouge), mais composants Solar dédiés incomplets/non uniformes.

## 7) Problèmes critiques identifiés
- Market vs Polymarket: coexistence historique de composants/nommage (`features/market/*` + UI polymarket).
- Profil invité trop complet: à limiter strictement au minimum.
- Accès trop large sans compte: gating à corriger selon action sensible.
- UI non homogène: mélange de cards/styles legacy et Solar partiel.
- Restes V1/V2: présence de modèles/écrans historiques (ex. `profile_v2_model.dart`, variantes navigation).
- Risques Dio/erreurs réseau: plusieurs écrans avec gestion hétérogène (fallback cache parfois absent).

## Mini-plan d’implémentation (max 6 points)
1. Corriger gating lancement/session (guest doit entrer en shell, non-auth vers AuthGate).
2. Renforcer design system Solar Brutalism (SolarCard, SolarPrimaryButton, SolarChip, SolarSectionTitle).
3. Refaire Home territoire selon structure V3 + fallback offline propre.
4. Refaire Events discovery (filtres clairs, CTA organizer strict, style Solar homogène).
5. Renforcer Polymarket et Scan (terminologie cohérente + porte rituelle + notice auth invité).
6. Nettoyer Profil invité/authentifié pour supprimer incohérences invité/login et dette UI visible.
