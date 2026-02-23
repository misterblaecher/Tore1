#!/usr/bin/env bash
set -euo pipefail

cat <<'ROUTES'
01_boot,/boot
02_consent,/consent
03_home_hub,/home-hub
04_qr_scanner,/qr
05_join_event,/join
06_event_hub,/event-hub
07_menu,/menu
08_wallet,/wallet
09_ticker,/ticker
10_profile_settings,/profile-settings
11_orga_control,/orga/control
12_orga_urgency,/orga/urgency
13_orga_entry,/orga/entry
14_bar_dashboard,/bar/dashboard
15_bar_orders,/bar/orders
16_bar_zones,/bar/zones
ROUTES
