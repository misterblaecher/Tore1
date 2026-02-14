# TORÈ — Release Checklist

Checklist minimale avant release (sans ajout de feature produit).

## 1) Versioning
- [ ] Bump de version (si applicable: backend, portal, app mobile, ou release tag).
- [ ] Vérifier changelog / notes de release associées.

## 2) Quality gates locaux
- [ ] Backend: `cd tore-backend && pytest -q`
- [ ] Portal: `cd tore-portal && npm ci && npm run build`

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
