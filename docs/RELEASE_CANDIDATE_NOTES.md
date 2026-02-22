# RELEASE CANDIDATE NOTES

## Scope
- Fermeture des gaps 🟡 du registre (gates état event, module OFF, idempotence writes sensibles, pack ops RC).
- Harmonisation des reason codes backend et gardes UI sans ajout de feature.

## Risques restants
- Quelques endpoints legacy polymarket hors scope event peuvent encore utiliser des conventions historiques.
- La robustesse offline dépend de la discipline opérateur (replay FIFO + contrôle audit).

## Known limitations
- Les états legacy (`LIVE/PAUSE/CLOSED`) restent acceptés pour compatibilité, mappés vers (`RUNNING/PAUSED/ENDED`).
- Le bootstrap local suppose un service backend docker nommé `backend-prodlike` (fallback `backend`).

## Instructions deploy
1. Exécuter `./scripts/ops_bootstrap_local.sh`.
2. Vérifier la checklist `docs/OPS_SMOKE_TEST_RC.md`.
3. Lancer le pipeline release links: `docs/release_verify_pipeline.md`.
4. Vérifier cohérence runbook: `docs/runbook_chapi_ready.md`.

## Checklist T-30min
- [ ] API `/healthz` OK.
- [ ] Event `RUNNING` et modules requis ON.
- [ ] Staff ENTRY/BAR/MANAGER validés (1 action réelle chacun).
- [ ] Writes sensibles bloqués correctement en `PAUSED/DEGRADED/FROZEN/ENDED`.
- [ ] Audit logs présents pour actions sensibles (reason + idempotency).
- [ ] Pipeline `assetlinks.json` PASS.
