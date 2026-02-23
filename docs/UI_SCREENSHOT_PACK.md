# UI Screenshot Pack (TORÈ Rebuild)

## Goal
Generate a deterministic screenshot set for Night-1 review across USER/ORGA/BAR flows.

## Recommended device settings
- Device: Android emulator (Pixel 6 class) and at least one physical device sanity pass.
- Theme: dark mode ON.
- Font scale pass A: `1.0`.
- Font scale pass B: `1.3`.
- Keep animations ON for default captures (disable only for reduced-motion verification).
- Disable notification popups/overlays before capture.

## Launch and capture setup
```bash
cd tore/app
flutter clean && flutter pub get
flutter run --dart-define=TORE_ENV=stage --dart-define=TORE_STARTUP_URL=tore://home-hub
```

### Fast landing with `TORE_STARTUP_URL`
Set `TORE_STARTUP_URL` to jump directly into a flow when QA supports startup routing.
Examples:
- `--dart-define=TORE_STARTUP_URL=tore://home-hub`
- `--dart-define=TORE_STARTUP_URL=tore://orga/control`
- `--dart-define=TORE_STARTUP_URL=tore://bar/orders`

If startup routing is unavailable for a route, navigate from Home Hub manually.

## Route list for capture
### USER
- `/boot`
- `/consent`
- `/home-hub`
- `/qr`
- `/join`
- `/event-hub`
- `/menu`
- `/wallet`
- `/ticker`
- `/profile-settings`

### ORGA
- `/orga/control`
- `/orga/urgency`
- `/orga/entry`

### BAR
- `/bar/dashboard`
- `/bar/orders`
- `/bar/zones`

## Capture manifest
| Screen | Route | Mode | Required state | Notes |
|---|---|---|---|---|
| Boot | `/boot` | USER | Fresh launch | Include env badge if visible |
| Consent Charter | `/consent` | USER | First-launch flow | CTA fully visible |
| Home Hub | `/home-hub` | USER | Signed-in user | Cards loaded or explicit empty state |
| QR Scanner | `/qr` | USER | Scanner open | Manual input action visible |
| Join Event | `/join` | USER | Join form ready | Primary JOIN CTA enabled |
| Event Hub | `/event-hub` | USER | Joined event | Modules shown with state badge |
| Menu | `/menu` | USER | Event active | Confirm CTA + cart/footer visible |
| Wallet | `/wallet` | USER | Wallet data available | Mono numeric display |
| Ticker | `/ticker` | USER | Feed loaded | List rows visible |
| Profile Settings | `/profile-settings` | USER | Settings loaded | Contrast/reduced motion toggles |
| Control Hub | `/orga/control` | ORGA | ORGA role granted | Counters + write controls visible |
| Urgency | `/orga/urgency` | ORGA | ORGA role granted | Freeze/emergency actions visible |
| Entry Staff | `/orga/entry` | ORGA | ORGA role granted | Recent scans list shown |
| Bar Dashboard | `/bar/dashboard` | BAR | BAR role granted | Revenue/orders summary visible |
| Orders Live | `/bar/orders` | BAR | BAR role granted | Active order cards with badges |
| Zones QR Admin | `/bar/zones` | BAR | BAR role granted | Zone toggles + export controls |

## File naming convention
Use ordered deterministic names:
- `01_boot.png` ... `16_bar_zones.png`

## Quick quality checks during capture
1. Offline/degraded banners are readable and actionable.
2. Primary tap targets remain >=44px.
3. High-contrast + ruby badges remain legible.
4. Numeric UI preserves mono styling.
5. No obvious scroll jank in list-heavy views.
