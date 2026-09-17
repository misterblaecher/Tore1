# TORÈ — Release Checklist

État de validation de cette intervention : voir `ASTRA_PROGRESS.md`. Ne pas déployer tant que les points ouverts de ce checkpoint ne sont pas résolus. Les anciennes notes « prod-ready » ne sont pas une certification de la release actuelle.

## Gate de consolidation du 11 septembre 2026

- [ ] Backend : créer un environnement Python propre, `python -m pip install -r requirements.txt`, puis `python -m pytest -q --disable-warnings`.
- [ ] Migrations : sauvegarder la base ; exécuter `python -m alembic upgrade head` et `python -m alembic current`. Head attendu : `0012_discussion_workspace`. Tester une copie restaurée avant production PostgreSQL.
- [ ] Site : `npm ci`, `npm test`, `npm run lint`, `npx tsc --noEmit -p tsconfig.app.json`, `npm run build`.
- [ ] Portail : `npm ci`, `npm test`, `npm run build`.
- [ ] Flutter : `flutter pub get`, `flutter analyze`, `flutter test`, `flutter build apk --debug --flavor dev --dart-define=TORE_ENV=dev --dart-define=TORE_API_BASE_URL=http://10.0.2.2:8000`.
- [ ] Production mobile : fournir une API HTTPS explicite via `--dart-define=TORE_API_BASE_URL=https://votre-api`, flavor prod ; signer avec les credentials de distribution. Build iOS sur macOS/Xcode.
- [ ] Smoke réel : connexion partenaire → liste de ses événements → création ; compte TORÈ sur le site → structure → publication événement → discovery App → join. Vérifier refus inter-structures et compte révoqué.

### Démarrage local sans Docker

Depuis `tore-backend`, activer le venv installé puis :
```powershell
$env:DATABASE_URL='sqlite:///./local-dev.db'
$env:TORE_ENV='dev'
$env:TORE_EMAIL_OTP_DEV_MODE='1'
python -m alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Le venv disponible dans cette session est `.venv-release` (ancien `.venv` cassé) : utiliser `.\.venv-release\Scripts\python.exe` à la place de `python` si non activé.

Dans deux terminaux, depuis `tore_site` : `npm run dev -- --port 8080` ; depuis `tore-portal` : `npm run dev -- --port 5173`. Configurer `VITE_API_URL` sur le site et `VITE_API_BASE_URL` sur le portail vers `http://localhost:8000`, et autoriser ces origines dans `TORE_CORS_ORIGINS`.

### Configuration externe et limites de release

- `TORE_VALUE_PREDICTIONS_ENABLED=0` : nouvelles participations avec valeur désactivées par défaut. Ne pas activer avant validation des règles et prérequis externes. Aucun cash-out réel certifié.
- SMTP réel requis pour les emails de production ; une simple `EMAIL_PROVIDER_API_KEY` n'est pas un service d'envoi implémenté. Désactiver tous les modes OTP de développement.
- Proxy admin optionnel : `ADMIN_API_KEY`, `ADMIN_BASIC_USER`, `ADMIN_BASIC_PASS` obligatoires ensemble ; `ADMIN_ALLOWED_ORIGINS` contient l'origine exacte du portail. `npm run admin-server`, derrière un reverse proxy HTTPS sur `/admin-api`. Aucun de ces secrets ne doit être une variable `VITE_*`.
- Le Docker Compose historique reste un outil local/prod-like : il doit être adapté avec secrets, origines et sauvegardes avant déploiement réel. Le `.dockerignore` exclut désormais secrets, bases et environnements Python de l'image.
- Restaurer une sauvegarde testée pour revenir en arrière ; éviter les downgrades destructifs sur les discussions/documents réels.

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
