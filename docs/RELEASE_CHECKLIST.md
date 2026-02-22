# TORÈ — Release Checklist

Checklist minimale avant release (sans ajout de feature produit).

## 0) Variables d’environnement requises (minimum local CI)

- Backend (`tore-backend`):
  - `DATABASE_URL`
  - `TORE_JWT_SECRET`
  - `TORE_SECRET`
  - `TORE_QR_SIGNING_KEYS` **ou** `TORE_QR_SIGNING_SECRET`
  - `TORE_CORS_ORIGINS`
- Portal (`tore-portal`):
  - `VITE_API_BASE_URL` (ou fallback `VITE_API_BASE`)
- Flutter (`tore/app`):
  - `TORE_API_BASE_URL`

Référence: `.env.example` racine + `tore-portal/.env.example` + `tore/app/.env.example`.

## 1) Versioning
- [ ] Bump de version (si applicable: backend, portal, app mobile, ou release tag).
- [ ] Vérifier changelog / notes de release associées.

## 2) Quality gates locaux (commandes exactes)
- [ ] Backend:
  - `cd tore-backend`
  - `pytest -q`
- [ ] Portal:
  - `cd tore-portal`
  - `npm ci`
  - `npm run build`
- [ ] Flutter:
  - `cd tore/app`
  - `flutter pub get`
  - `flutter analyze`
  - `flutter build apk --debug`

## 3) Scripts d'exploitation
- [ ] Seed minimal: `python scripts/seed_minimal.py`
- [ ] Sanity script: `./scripts/sanity_check.sh`

## 4) Base de données / migrations
- [ ] Vérifier les variables d'environnement Postgres.
- [ ] Appliquer les migrations: `cd tore-backend && alembic upgrade head`
- [ ] Confirmer qu'aucune migration manquante/incohérente n'est détectée.

## 5) Validation opérationnelle
- [ ] Vérifier l'endpoint healthz de l'API.
- [ ] Vérifier les snapshots OPS / journaux d'audit pertinents.
- [ ] Confirmer que les reason codes, l'idempotence et l'audit trail sont conformes (si le périmètre les impacte).
