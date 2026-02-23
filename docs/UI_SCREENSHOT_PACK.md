# UI Screenshot Pack (TORÈ Rebuild)

## Goal
Generate a deterministic screenshot set for premium-night review (pixel + interactions pass).

## Environment
- Device: Android emulator (Pixel 6 or similar), dark mode ON.
- Font scale pass 1: `1.0`.
- Font scale pass 2: `1.3` (a11y overflow pass).
- Disable system animations **only** for reduced-motion checks.

## Run
```bash
cd tore/app
flutter clean && flutter pub get
flutter run
```

## Optional quick launcher (dev-only)
If available in dev build, open the debug route launcher and jump directly to each route in order below.
Otherwise use in-app nav from Home Hub.

## Deterministic capture sequence
Capture each screen in this strict order:

| Screen | Route | How to reach | Expected state/banner |
|---|---|---|---|
| Boot | `/boot` | App start | Optional network banner |
| Consent Charter | `/consent` | First-launch flow | CTA visible and >=44px |
| Home Hub | `/home-hub` | Post-consent | Cards list or empty state |
| QR Scanner | `/qr` | Home > Scanner | Manual input + action CTA |
| Join Event | `/join` | Hub > Join | JOIN CTA semantics present |
| Event Hub | `/event-hub` | Join success | Module badges + state badge |
| Menu | `/menu` | Hub > Menu | CONFIRMER CTA + cart footer |
| Wallet | `/wallet` | Hub > Wallet | Mono numeric balance |
| Ticker | `/ticker` | Hub > Ticker | Builder list loaded |
| Profile Settings | `/profile-settings` | Hub > Profile | High contrast toggle state |
| Orga Control Hub | `/orga/control` | Role ORGA | Mono counters + write toggles |
| Orga Urgency | `/orga/urgency` | Orga > Urgency | FREEZE semantics |
| Entry Staff | `/orga/entry` | Orga > Entry | Scan chips and last scans list |
| Bar Dashboard | `/bar/dashboard` | Role BAR | Revenue mono number |
| Orders Live | `/bar/orders` | Bar > Orders | Builder list with badges |
| Zones QR Admin | `/bar/zones` | Bar > Zones | Zone toggles + export footer |

## Capture naming convention
Use deterministic file names:
- `01_boot.png`
- `02_consent.png`
- ...
- `16_bar_zones.png`

## Manual checklist while capturing
1. Banner semantics text is announced by screen reader when offline/degraded.
2. Tap targets (CTA, switches, chips) are at least 44px.
3. Yellow CTA on black is readable.
4. Ruby badges stay readable in high-contrast mode.
5. Numeric values use mono style.
6. Motion is short (micro ~150ms, transition ~220ms).
7. Reduced-motion setting collapses animation durations.
8. QR errors use unified microcopy mapping.
9. Offline write attempts show actionable snackbar.
10. No obvious scroll jank on list-heavy screens.
