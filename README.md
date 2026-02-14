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
2. Démarrer Postgres + backend en profil prod-like:
   ```bash
   docker compose --profile prod-like up -d --build
   ```
3. Appliquer les migrations Alembic:
   ```bash
   docker compose --profile prod-like exec backend-prodlike alembic upgrade head
   ```
4. Seed minimal (bar/event/zone/item/user/staff):
   ```bash
   ./scripts/dev_bootstrap.sh
   ```
5. Lancer le portal (local):
   ```bash
   cd tore-portal && npm ci && npm run dev
   ```
6. Vérifier les flux santé + e2e smoke:
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
