# SOIREE RUNBOOK — TORÈ

## 1) Checklist pré-soirée
- [ ] `APP_ENV=prod` (ou `ENV=PROD`) configuré côté backend.
- [ ] `DATABASE_URL` pointe vers **Postgres** (pas SQLite) en production.
- [ ] `RUN_MIGRATIONS=1` et `MIGRATIONS_FATAL=1` activés.
- [ ] `ADMIN_API_KEY` défini pour la page staff account-requests.
- [ ] SMTP configuré (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`).
- [ ] CORS prod configuré sur **une seule variable**: `TORE_CORS_ORIGINS` (sans `*`, sans slash final).
- [ ] `TORE_CORS_ORIGINS` contient au minimum:
  - `https://tore-site.onrender.com`
  - `https://tore1.onrender.com`
- [ ] QR signing keys présentes (`TORE_QR_SIGNING_KEYS`).

## 2) Vérifier la santé backend
```bash
curl -sS https://<backend>/healthz
curl -sS https://<backend>/api/healthz
```
Résultat attendu: HTTP 200 + payload JSON OK.

## 3) Forcer / vérifier un mode de compte
Modes supportés: `user` | `organizer` | `team`.

```bash
curl -X PATCH https://<backend>/auth/me \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"account_mode":"organizer"}'
```

Validation:
```bash
curl -sS https://<backend>/auth/me -H "Authorization: Bearer <access_token>"
```
Le JSON doit contenir `account_mode`.

## 4) Test création event (app-first)
1. Dans l'app, passer en mode **Organisateur**.
2. Ouvrir Home → bloc Organisateur → créer un event (nom/date/lieu).
3. Vérifier l'event dans les listes/events déjà existantes.

## 5) Test scan / check-in (mode Équipe)
1. Dans l'app, passer en mode **Équipe**.
2. Ouvrir scanner QR.
3. Scanner un QR valide event/check-in.
4. Vérifier la réponse serveur (accepté / déjà scanné).

## 6) Account requests (staff)
- Portal: `/staff/account-requests`
- Pré-requis: token portal + variable `VITE_ADMIN_API_KEY` (même valeur que `ADMIN_API_KEY` backend).

## 7) Procédure incident
1. Vérifier `/healthz`.
2. Si KO backend:
   - activer maintenance sur frontend (bannière déjà affichée en app si health down)
   - basculer en mode offline app (cache local profil/events)
3. Rollback Render:
   - Backend: redeploy last known good commit
   - Site/App: rollback vers dernier deploy stable
4. Après rollback:
   - re-check `/healthz`
   - test OTP email
   - test `/auth/me` GET/PATCH (incluant `account_mode`)

## 8) Variables d'env prod indispensables
- `DATABASE_URL`
- `APP_ENV=prod` (ou `ENV=PROD`)
- `PUBLIC_URL` / `BASE_URL`
- `TORE_CORS_ORIGINS`
- `TORE_QR_SIGNING_KEYS`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
- `ADMIN_API_KEY`
- `RUN_MIGRATIONS=1`
- `MIGRATIONS_FATAL=1`
