# tore-backend

## Public account request API

Endpoint public disponible pour le site `tore_site` :

- `POST /public/account-request`

Payload JSON attendu :

```json
{
  "name": "Alice Martin",
  "email": "alice@example.com",
  "phone": "+32495123456",
  "is_whatsapp": true,
  "role": "student",
  "committee_name": null,
  "source": "tore_site",
  "utm": {
    "utm_source": "landing"
  }
}
```

Réponse:

```json
{ "ok": true, "id": 123, "message": "Account request created" }
```

## Variables d'environnement

- `VITE_API_URL` (frontend `tore_site`) : URL du backend (ex: `https://tore-backend.onrender.com`).
- `TORE_CORS_ORIGINS` : liste d'origines autorisées (séparées par virgule, sans slash final).
- `RATE_LIMIT_WINDOW` *(optionnel)* : fenêtre anti-spam en minutes (défaut 10).
- `RATE_LIMIT_MAX` *(optionnel)* : nombre max de requêtes par empreinte ip+user-agent (défaut 3).
- `ACCOUNT_EMAIL_COOLDOWN_MIN` *(optionnel)* : anti doublon email+phone (défaut 2 minutes).
- `RUN_MIGRATIONS` *(optionnel, défaut `1`)* : exécute automatiquement `alembic upgrade head` au démarrage backend.
- `ORGA_CODE` : code requis pour demander le mode `organizer` via `POST /auth/role/request-upgrade`.
- `TEAM_CODE` : code requis pour demander le mode `team` via `POST /auth/role/request-upgrade`.
- `ADMIN_API_KEY` : clé serveur pour les endpoints admin de validation (`GET/PATCH /admin/role-requests`, header `X-Admin-Api-Key`).
- `MIGRATIONS_FATAL` *(optionnel, défaut `1`)* : si les migrations échouent, stoppe le process (`1`) ou continue avec warning (`0`).

### Render free : migrations auto au boot

Sur Render free, l'accès Shell et le **Pre-Deploy Command** sont payants. Le backend applique donc les migrations Alembic automatiquement au startup (avant de servir les requêtes) pour garantir que le schéma en production reste à jour (ex: création de `account_requests` via la migration `0003`).

## Curl de test

```bash
curl -X POST "${API_URL}/public/account-request" \
  -H "Content-Type: application/json" \
  -H "User-Agent: curl-test" \
  -d '{
    "name":"Alice Martin",
    "email":"alice@example.com",
    "phone":"+32495123456",
    "is_whatsapp":true,
    "role":"student",
    "committee_name":null,
    "source":"tore_site"
  }'
```
