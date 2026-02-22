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
- `CORS_ALLOWED_ORIGINS` : liste d'origines autorisées (séparées par virgule).
- `RATE_LIMIT_WINDOW` *(optionnel)* : fenêtre anti-spam en minutes (défaut 10).
- `RATE_LIMIT_MAX` *(optionnel)* : nombre max de requêtes par empreinte ip+user-agent (défaut 3).
- `ACCOUNT_EMAIL_COOLDOWN_MIN` *(optionnel)* : anti doublon email+phone (défaut 2 minutes).

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
