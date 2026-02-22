# ÉTAPE 0 — Registre TORÈ V3 (Solar Mythic OS)

## 1) Inventaire des pages Flutter existantes (routes/screens)

### Entrée & auth
- `main.dart` : boot/splash, routing deep-link, gate auth (`AuthGateScreen`), `CompleteProfileScreen`, `AppShell`.
- Auth screens :
  - `features/auth/presentation/auth_gate_screen.dart`
  - `features/auth/presentation/email_auth_screen.dart`
  - `features/auth/presentation/complete_profile_screen.dart`
  - `features/auth/presentation/welcome_screen.dart`

### Navigation principale (USER)
- `features/navigation/presentation/home_territory_feed_screen.dart`
- `features/navigation/presentation/events_discovery_screen.dart`
- `features/navigation/presentation/polymarket_tab_screen.dart`
- `features/navigation/presentation/profile_screen.dart`
- `features/qr/presentation/qr_scanner_screen.dart`

### Écrans clés secondaires
- Events: `events_screen`, `event_hub_screen`, `event_public_screen`, `create_event_wizard_screen`, `event_polymarket_screen`, etc.
- QR flow: `join_event_screen`, `join_event_confirm_screen`, `qr_unknown_screen`, `qr_forbidden_screen`, `qr_expired_screen`, `qr_invalid_screen`, `wifi_screen`.
- Bars/Wallet/Ticker/Hunt/Battles/Community/Staff/etc. présents dans `lib/features/**/presentation`.

---

## 2) Navigation actuelle (bottom nav / shell)
- Shell: `app_shell.dart`.
- Tabs actuels détectés: `Home`, `Events`, `Polymarket`, `Profil`.
- Scan géré via FAB central (hors tab logique).
- Chaque onglet a son `Navigator` dédié (IndexedStack + keys).

---

## 3) Auth flow actuel (OTP, guest, complete-profile, PartyOut upgrade)
- Provider session: `core/auth/auth_session_provider.dart`.
- États: `loading`, `guest`, `authenticated`, `unauthenticated`, `bootstrapError`.
- OTP email: `/auth/email/request_otp` puis `/auth/email/verify_otp`.
- Guest: `/auth/guest`, stockage local `guest_mode_enabled` + `guest_device_id`.
- Complete profile gate: `main.dart` redirige vers `CompleteProfileScreen` si nom vide.
- Role upgrade PartyOut: `profile_screen.dart` via code Organisateur/Équipe + pending (`roleRequestPending`) via `requestRoleUpgrade`.

---

## 4) QR router (formats supportés)
- Parser: `core/qr/qr_parser.dart`.
- Formats:
  - JSON (`{"type":...}`)
  - Préfixes `type:payload`
  - URI (`tore://...`, `https://...` + query)
- Types supportés: `joinEvent`, `menu`, `staffEntry`, `staffBar`, `wifi`, `hunt`, `battle`, `order`, `polymarket`, `orga`, `staffInvite`, `staffBackup`, `orgaInvite`, `barProfile`, `userProfile`, `unknown`.

---

## 5) Endpoints API utilisés (app mobile)
- Base: `lib/api.dart` (+ `core/network/api_endpoints.dart`).
- Catégories majeures présentes:
  - Auth: `/auth/*`
  - Bars/events: `/bars`, `/bars/{id}/events`, `/events/*`
  - Profil: `/me/profile`, `/me/privacy`, `/me/events`, `/me/orgas`
  - Wallet/orders: `/wallet/me`, `/orders/{id}`
  - Orgas/committees/glossary/maps/calendar/modules
- Référence brute extraite automatiquement: 71 routes dans `lib/api.dart`.

---

## 6) Design system existant
- `ui/app_design_system.dart`:
  - `AppColors`, `AppTextStyles`, `AppSpacing`
  - composants: `PrimaryButton`, `SecondaryButton`, `AppCard`, `SectionTitle`, `AppChip`
- Thème global complémentaire dans `theme/`.

---

## 7) Problèmes à corriger maintenant
- [x] “Market” doit redevenir **Polymarket** partout (labels/titles/nav).
- [x] Profil invité trop chargé → version ultra minimale.
- [x] L’app laisse trop d’actions sensibles sans compte (scan/check-in/staff/create event).
- [x] Incohérences DA/UI entre écrans (uniformisation Solar Brutalism).

---

## Mini-plan d’implémentation (5 points)
1. **Refactor shell/nav** : imposer Home / Events / Scan / Polymarket / Profil.
2. **Auth gate stricte** au boot pour non-authentifié + reprise explicite invité via CTA.
3. **Rework Solar Brutalism** des écrans clés (AuthGate, Home, Events, Scan, Polymarket, Profil).
4. **Guest gating** des actions sensibles avec message "Connecte-toi pour continuer".
5. **Nettoyage labels & cohérence** (Polymarket partout, strings FR propres, pas de régression OTP/guest/profile).
