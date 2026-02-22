# REGISTRE UI V3 — TORÈ SOLAR MYTHIC OS

## 1) Inventaire écrans Flutter (scope `tore/app/lib`)

### Écrans OK / partiellement alignés V3
- `main.dart` : boot entry + splash rituel + routage d'ouverture.
- `features/auth/presentation/auth_gate_screen.dart`.
- `features/auth/presentation/email_auth_screen.dart`.
- `features/auth/presentation/complete_profile_screen.dart`.
- `app_shell.dart` (bottom nav + scan central).
- `features/navigation/presentation/home_territory_feed_screen.dart`.
- `features/navigation/presentation/events_discovery_screen.dart`.
- `features/navigation/presentation/polymarket_tab_screen.dart`.
- `features/navigation/presentation/profile_screen.dart`.
- `features/qr/presentation/qr_scanner_screen.dart`.

### À refaire / consolider
- Uniformisation visuelle full V3 sur tous les écrans navigation.
- États fallback homogènes (loading/empty/error) sur Home + Events + Polymarket.
- Signal “session expirée” visible dans le gate auth et flux de relog propre.

### À supprimer / masquer progressivement
- Placeholders “coming soon” ou modules OFF visibles hors scope V3.
- Routes mortes liées à modules non-prioritaires (forum, hunt, battles, safe kit) si encore exposées à l'utilisateur.

## 2) Routes/navigation actuelles
- Entrée app: `_BootEntry` dans `main.dart`.
- Gate auth:
  - non-auth → `AuthGateScreen`
  - invité → `AppShell`
  - connecté + displayName vide → `CompleteProfileScreen`
  - connecté + displayName présent → `AppShell`
- App shell bottom nav: Home / Events / Scan (central) / Polymarket / Profil.

## 3) Problèmes observés avant stabilisation
- Commandes Flutter indisponibles dans cet environnement local (pas de binaire `flutter`), analyse/build non exécutables ici.
- Pas d'affichage explicite “session expirée” côté gate après invalidation token.
- Composants fallback partiels et hétérogènes selon écrans.

## 4) Plan minimal (10 points)
1. Vérifier docs de vérité produit/roadmap et alignement V3.
2. Mettre à jour le registre UI V3 (ce document).
3. Renforcer design system partagé (buttons/cards/headers/halo/radii/spacing).
4. Uniformiser banner réseau ONLINE/DEGRADED/OFFLINE.
5. Ajouter composants fallback unifiés (ErrorState/EmptyState/LoadingSkeleton).
6. Renforcer signal auth expirée sans boucle logout/login.
7. Afficher message session expirée au niveau `AuthGateScreen`.
8. Introduire écran gate scanner explicite (`QrScannerGateScreen`) et l'utiliser depuis `AppShell`.
9. Vérifier rapidement imports/compilation statique (sans exécuter Flutter ici).
10. Commit + PR avec checklist de validation manuelle.
