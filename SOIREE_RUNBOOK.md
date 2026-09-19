# SOIREE RUNBOOK — TORÈ / PartyOut

## 1) Variables d'environnement obligatoires

### Backend (Render)
- `TORE_ENV=prod` (`APP_ENV=prod` reste accepté comme alias de compatibilité)
- `DATABASE_URL`
- `TORE_CORS_ORIGINS`
- `ORGA_CODE`
- `TEAM_CODE`
- `ADMIN_API_KEY`
- `RUN_MIGRATIONS=1`
- `MIGRATIONS_FATAL=1`

### Portal admin (Render)
- `API_BASE_URL` (URL du backend)
- `ADMIN_API_KEY` (uniquement côté serveur portal, jamais côté frontend public)
- `ADMIN_BASIC_USER`
- `ADMIN_BASIC_PASS`

## 2) Santé backend
```bash
curl -sS https://<backend>/healthz
curl -sS https://<backend>/api/healthz
```
Attendu: HTTP 200.

## 3) Procédure PartyOut (3 modes)
Modes supportés: `user` | `organizer` | `team`.

### 3.1 Demande de montée de rôle (utilisateur)
```bash
curl -X POST https://<backend>/auth/role/request-upgrade \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"requested_mode":"organizer","code":"<ORGA_CODE>"}'
```
Attendu: status `pending`.

### 3.2 Vérification côté profil
```bash
curl -sS https://<backend>/auth/me \
  -H "Authorization: Bearer <access_token>"
```
Attendu: présence de `account_mode` et `role_request_pending` si une demande est en attente.

### 3.3 Retour direct en mode user
```bash
curl -X PATCH https://<backend>/auth/me \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"account_mode":"user"}'
```
Attendu: autorisé. Les passages directs vers `organizer`/`team` sont refusés.

## 4) Validation admin des demandes

### 4.1 Lister les demandes pending
```bash
curl -sS "https://<backend>/admin/role-requests?status=pending&limit=50" \
  -H "X-Admin-Api-Key: <ADMIN_API_KEY>"
```

### 4.2 Approuver / rejeter
```bash
curl -X PATCH https://<backend>/admin/role-requests/<id> \
  -H "X-Admin-Api-Key: <ADMIN_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"action":"approve","note":"Validation soirée"}'
```
Ou:
```bash
-d '{"action":"reject","note":"Code invalide"}'
```

## 5) Sécurité portal admin (Basic Auth)
- Toutes les routes du service proxy admin sont protégées par Basic Auth (`ADMIN_BASIC_USER`/`ADMIN_BASIC_PASS`).
- Ne jamais exposer `ADMIN_API_KEY` via une variable `VITE_*`.
- Le frontend portal consomme `/admin-api/*`; c'est le serveur portal qui injecte `X-Admin-Api-Key`.

## 6) Tests manuels (Go/No-Go)
- [ ] Login OTP OK sur app + site.
- [ ] `/profile` (site) affiche mode actuel + état pending.
- [ ] Demande organizer avec code valide => pending visible.
- [ ] Admin voit la demande en pending dans le portal.
- [ ] Admin approve => `account_mode` mis à jour après refresh `/auth/me`.
- [ ] Passage manuel en mode `user` fonctionne via profil.
- [ ] Aucune clé admin visible côté frontend public.
