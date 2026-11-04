# TORÈ — Release Pack (prod-ready)

## Variables d'environnement

### Backend (`tore-backend`)
- `DATABASE_URL` (Postgres recommandé en prod)
- `TORE_JWT_SECRET`
- `TORE_SECRET`
- `ORDER_QR_SECRET`
- `TORE_CORS_ORIGINS` (CSV, ex: `https://portal.example,https://admin.example`)
- `TORE_RATE_LIMIT_MAX`
- `TORE_RATE_LIMIT_WINDOW_S`
- `TORE_AUTO_DB_BOOTSTRAP` (mettre `0` en prod)

### Portal (`tore-portal`)
- `VITE_API_BASE_URL`

### Flutter (`tore/app`)
- `TORE_API_BASE_URL`

## Procédure deploy (prod-like)

1. Copier le template env:
   ```bash
   cp .env.example .env
   ```
2. Pour le profil `prod-like`, renseigner dans `.env` de vrais secrets (`TORE_JWT_SECRET`, `ADMIN_API_KEY`, `TORE_QR_SIGNING_KEYS`), des origines HTTPS exactes (`TORE_CORS_ORIGINS`), SMTP et `TORE_EMAIL_OTP_DEV_MODE=false`. Ce profil force `TORE_ENV=PROD` et refuse les valeurs de développement. Il reste destiné au **test local** : ni les identifiants PostgreSQL Docker ni le seed ci-dessous ne conviennent à une production publique.
3. Démarrer Postgres + backend en profil prod-like:
   ```bash
   docker compose --profile prod-like up -d --build
   ```
4. Appliquer les migrations Alembic:
   ```bash
   docker compose --profile prod-like exec backend-prodlike alembic upgrade head
   ```
5. Seed minimal (uniquement en test/démo, jamais sur une vraie production) :
   ```bash
   ./scripts/dev_bootstrap.sh
   ```
6. Lancer le portal (local):
   ```bash
   cd tore-portal && npm ci && npm run dev
   ```
7. Vérifier les flux santé + e2e smoke:
   ```bash
   ./scripts/sanity_check.sh
   ```

## Développement local

### Démarrage rapide (profil dev)
```bash
docker compose --profile dev up -d --build
./scripts/dev_bootstrap.sh
./scripts/sanity_check.sh
```

## Migrations

- Nouvelle stack Alembic dans `tore-backend/alembic`.
- Migration baseline: `0001_initial_schema`.
- Commandes:
  ```bash
  cd tore-backend
  alembic upgrade head
  alembic downgrade -1
  ```
