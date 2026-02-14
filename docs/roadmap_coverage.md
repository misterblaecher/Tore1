# TORÈ — Roadmap Coverage Map (PR0)

## Scope & method
- Source of truth used: official roadmap in task prompt (P0 → P9).
- Repository audit inputs:
  - Flutter app features (`tore/app/lib/features/*`)
  - Backend routers/services/tests (`tore-backend/app/*`, `tore-backend/tests/*`)
  - Portal pages (`tore-portal/src/pages/*`)
- Status legend:
  - ✅ = déjà présent et utilisable
  - 🟡 = partiel (présent mais incomplet vis-à-vis de la roadmap officielle)
  - 🔴 = absent / non observable dans ce repo

---

## Feature → état (P0 → P9)

| Phase | Feature roadmap | État | Scope | Constats rapides |
|---|---|---:|---|---|
| P0 | Splash/Boot online-retry-offline-read-only | 🟡 | App | Boot/auth présent, mais durcissement mode lecture global à harmoniser. |
| P0 | Réseau harmonisé global ONLINE/DEGRADED/OFFLINE + provider unique | 🟡 | App+Backend | Health/network providers et bannières existent, convergence complète à finaliser. |
| P0 | Scanner QR universel parfait (<1s, unknown/expired/revoked screens) | 🟡 | App+Backend | Scanner + router + écrans unknown/forbidden déjà présents; QoS terrain et auto-lampe à finaliser. |
| P1 | USER bars + events list (Live/Today/Upcoming) | ✅ | App+Backend | Repositories/écrans bars/events présents. |
| P1 | Join event complet + charte | 🟡 | App+Backend | Join via QR/codes en place en partie; charte conditionnelle à compléter. |
| P1 | Event hub modulaire ON-only + banner état event <2s | 🟡 | App+Backend | Modules/event control existent; propagation SLA <2s à verrouiller de bout en bout. |
| P2 | ORGA hub cockpit + state actions reasoned | 🟡 | App+Backend | Hub/admin pages et contrôles présents; enforcement reason obligatoire selon états à compléter. |
| P2 | Wizard create event <60s + templates + QR pack | 🟡 | App+Backend | Create event + QR pack screen présents; templates/flow chrono et export print à renforcer. |
| P2 | Entry rush mode + offline queue + attendance export | 🟡 | App+Backend | Entry flow, logs, exports testés; mode rush UX + queue offline robuste à finaliser. |
| P2 | Staff roles + revoke + QR pack | 🟡 | App+Backend | Staff management exists; revoke/token invalidation unifiée à compléter. |
| P2 | Broadcast ORGA→users + anti-spam | 🟡 | App+Backend | Ticker/broadcast partiels; endpoints/rate-limit à consolider. |
| P2 | Urgence/incidents + export dossier | 🔴 | App+Backend | Pas de module incident complet observable. |
| P2 | Rentabilité live v1 | 🟡 | App+Backend | Reports/costs présents, cockpit rentabilité live à compléter. |
| P3 | Bar dashboard + orders live + status sync | ✅ | App+Backend | Pages/services/tests orders live et dashboard présents. |
| P3 | Full menu admin + inventory/rupture + import/export | 🟡 | App+Backend | Menu admin solide; bulk/import-export & rupture avancée à compléter. |
| P3 | Analytics v1 + exports | ✅ | App+Backend | Routers/pages analytics + exports présents. |
| P4 | Wallet gifts + privacy consent | 🟡 | App+Backend | Wallet et consent existent partiellement; gifts P2P UX/flags à finir. |
| P4 | Ticker multi-types + respect états event | 🟡 | App+Backend | Ticker feed présent; couverture complète multi-types/overrides à renforcer. |
| P5 | Polymarket global | ✅ | App+Backend | Routers/services/pages/tests polymarket global présents. |
| P5 | Polymarket event + create + resolver + animations | 🟡 | App+Backend | Backend event polymarket mature; animations/front final à compléter. |
| P5 | Classement + menu bonus v1 | 🟡 | App | Leaderboard/menu existent, UX roadmap spécifique à compléter. |
| P6 | Musique Spotify/Apple + vote + owner enable + DJ override | 🔴 | App+Backend | Intégration musique complète non observée. |
| P7 | COMITÉ OS foundations + roles | 🔴 | App+Backend | Non observé (hors abstractions génériques). |
| P7 | Forum + archives + finances + exports + baptême | 🔴 | App+Backend | Non observé. |
| P8 | Extensions Liège/folklore (wifi/battles/hunts/checkin/safe kit/map/calendar/glossary) | 🟡 | App+Backend | Battles/hunts/wifi en partie présents; safe kit/carte/calendrier/glossaire absents. |
| P9 | Signed QR + expiration partout | 🟡 | App+Backend | Services QR et snapshots existent; couverture “partout” à achever. |
| P9 | Idempotency keys sur tous writes + audit logs complets | 🟡 | App+Backend | Forte base (tests/idempotence/audit), reste à uniformiser globalement. |
| P9 | RGPD exports/suppression/rétention | 🔴 | App+Backend | Non observé comme module complet. |
| P9 | Trust & safety (sanctions/lockdown/freeze modules/plan B) | 🟡 | App+Backend | Event state overrides déjà amorcés; suite trust&safety à compléter. |

---

## Plan de PRs (ordre strict imposé)

> Priorisation respectée: P0 d’abord, puis P1…, avec P2 traité comme jalon “chapi-ready” dès sa fenêtre.

### Tranche immédiate (à enchaîner)
1. **PR0 (ce document)** — coverage map + plan.
2. **PR1** — P0 boot/splash + read-only mode global write-guard.
3. **PR2** — P0 réseau unifié (provider unique + bannières globales).
4. **PR3** — P0 scanner universel (latence perçue, low-light torch, routes unknown/expired/revoked).

### P1
5. PR4 bars/events list UX parity.
6. PR5 join complet + charte activable.
7. PR6 event hub ON-only + propagation état <2s.

### P2 (chapi-ready DoD)
8. PR7 ORGA cockpit + actions état avec reason.
9. PR8 wizard event<60s + templates + QR pack print/share.
10. PR9 entry rush + offline queue + export attendance.
11. PR10 staff roles/revoke + QR pack.
12. PR11 broadcast + anti-spam.
13. PR12 incidents urgence + export dossier.
14. PR13 rentabilité live v1.

### P3
15. PR14 dashboard bar + orders live sync.
16. PR15 menu admin complet + inventory + import/export.
17. PR16 analytics v1 + exports.

### P4
18. PR17 wallet gifts + privacy consent.
19. PR18 ticker multi-types + overrides états event.

### P5
20. PR19 polymarket global hardening.
21. PR20 polymarket event create/resolve + animations.
22. PR21 leaderboard + menu bonus.

### P6
23. PR22 music module v1 (feature-flagged if needed).

### P7
24. PR23 committee OS foundations + roles.
25. PR24 forum/archives/finances/exports (+ baptême skeleton OFF by default si nécessaire).

### P8
26. PR25 wifi QR lifecycle/revoke.
27. PR26 battles/affonds ranking.
28. PR27 hunts QR + cagnottes défendables.
29. PR28 check-in boissons.
30. PR29 safe kit.
31. PR30 carte + itinéraires.
32. PR31 calendrier guindaille.
33. PR32 glossaire folklore.

### P9
34. PR33 signed QR + expiry partout.
35. PR34 idempotency keys + audit logs write endpoints.
36. PR35 RGPD exports/suppression/rétention.
37. PR36 trust&safety capstone + plans lecture/freeze.

---

## DoD checks for PR0
- [x] Carte de couverture documentée avec statuts ✅🟡🔴.
- [x] Classification App only / Backend only / App+Backend incluse.
- [x] Séquencement PRs explicite en ordre P0→P9.
- [x] Aucune modification produit/fonctionnelle (documentation only).

## Non-goals (PR0)
- Pas de changement code Flutter/Backend/Portal.
- Pas d’exécution de la roadmap produit dans ce PR (uniquement audit + plan).
