# OPS SMOKE TEST RC (12 points max)

1. `./scripts/ops_bootstrap_local.sh` termine sans erreur.
2. `GET /healthz` renvoie `200` et `db_ok=true`.
3. Login portal manager + ouverture event-control OK.
4. Banner `event_state` visible sur pages ops critiques.
5. Join event (QR + code manuel) OK côté mobile.
6. Entry scan x3 online puis x2 offline + replay sans doublon.
7. Order flow `PENDING -> ACCEPTED -> READY -> CLAIMED` OK.
8. Wallet write idempotent: double requête même key = une seule écriture.
9. Polymarket write bloqué si `event_state != RUNNING`.
10. Module OFF: aucun quick-link mobile + guard portal URL direct.
11. Audit: action sensible écrit bien un log (avec reason/idempotency).
12. Pipeline release links passe (`docs/release_verify_pipeline.md`) + validation `assetlinks.json` PASS.
