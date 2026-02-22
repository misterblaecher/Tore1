# SOIREE RUNBOOK — TORÈ

## 1) Checklist pré-soirée
- [ ] `APP_ENV=prod` (ou `ENV=PROD`) configuré côté backend.
- [ ] `DATABASE_URL` pointe vers **Postgres** (pas SQLite) en production.
- [ ] `RUN_MIGRATIONS=1` et `MIGRATIONS_FATAL=1` activés.
- [ ] `ADMIN_API_KEY` défini pour la page staff account-requests.
- [ ] SMTP configuré (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`).
- [ ] CORS prod configuré (`CORS_ORIGINS` ou `TORE_CORS_ORIGINS`, sans `*`).
- [ ] QR signing keys présentes (`TORE_QR_SIGNING_KEYS`).

## 2) Vérifier la santé backend
```bash
curl -sS https://<backend>/healthz
curl -sS https://<backend>/api/healthz
```
Résultat attendu: HTTP 200 + payload JSON OK.

## 3) Account requests (staff)
- Portal: `/staff/account-requests`
- Pré-requis: token portal + variable `VITE_ADMIN_API_KEY` (même valeur que `ADMIN_API_KEY` backend).
- Actions:
  - filtrer `pending` / `processed`
  - `Mark processed`
  - `Export CSV`

## 4) QR debug / types supportés
Page portal: `/staff/qr-debug`

Types reconnus MVP:
- `event_checkin:<event_id>`
- `bar:<bar_id>`
- `profile:<user_id>`

Fallback UX: message `QR non reconnu`.

## 5) Procédure incident
1. Vérifier `/healthz`.
2. Si KO backend:
   - activer maintenance sur frontend (bannière déjà affichée en app si health down)
   - éviter check-in live (scan bloqué hors-ligne)
3. Rollback Render:
   - Backend: redeploy last known good commit
   - Portal: rollback vers dernier deploy stable
4. Après rollback:
   - re-check `/healthz`
   - test OTP email
   - test route `/staff/account-requests`

## 6) Variables d'env prod indispensables
- `DATABASE_URL`
- `APP_ENV=prod` (ou `ENV=PROD`)
- `PUBLIC_URL` / `BASE_URL`
- `CORS_ORIGINS` (ou `TORE_CORS_ORIGINS`)
- `TORE_QR_SIGNING_KEYS`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
- `ADMIN_API_KEY`
- `RUN_MIGRATIONS=1`
- `MIGRATIONS_FATAL=1`
