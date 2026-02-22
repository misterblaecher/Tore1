# RC E2E PASS (TORÈ)

## Commandes exactes

### Backend
- `cd tore-backend && pytest -q`

### Portal
- `cd tore-portal && npm ci && npm run build`

### Flutter (documenté, à lancer en local mobile)
- `cd tore-mobile && flutter analyze`
- `cd tore-mobile && flutter build apk --release`

## Parcours manuel (10 minutes)

Références:
- `docs/OPS_SMOKE_TEST_RC.md`
- `docs/terrain_smoke_e2e.md`

Checklist terrain courte:
1. Ouvrir Event Control Hub et vérifier `event_state` visible.
2. Basculer `PAUSED` puis vérifier blocage writes sur Wallet/Polymarket.
3. Mettre un module OFF (wallet/polymarket) puis vérifier garde UI + backend (`module_off`).
4. Revenir `RUNNING/LIVE` et exécuter un topup idempotent (2 appels, 1 seule écriture).
5. Exécuter un transfer wallet idempotent (2 appels, 1 seul débit).
6. Vérifier bannières event_state sur pages ops sensibles.
7. Passer l'event en `ENDED`, vérifier refus des writes.

## Critères PASS / FAIL

### PASS
- `pytest -q` vert.
- Build portal OK (`npm run build`).
- Writes wallet/polymarket refusés en `PAUSED/FROZEN/ENDED`.
- Module OFF renvoie `412` + `reason=module_off`.
- Writes désactivés côté portal quand module `READ_ONLY/OFF`.
- Idempotency-Key requis sur endpoints write wallet ciblés.

### FAIL
- Écriture wallet possible alors que runtime bloque.
- Écriture possible sans `Idempotency-Key`.
- Action sensible acceptée sans `reason_code`/`reason_text`.
- Route module OFF accessible sans garde visible.
