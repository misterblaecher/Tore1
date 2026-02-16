# Runbook Chapi-ready (Release / Deploy kit)

## Prérequis
- Docker + Docker Compose (déploiement local/prod-like).
- Python 3.11+ pour les scripts `scripts/seed_demo.py` et `scripts/smoke_backend.py`.
- Node.js 20+ pour le portal (`tore-portal`).
- Flutter SDK (Android toolchain) pour l’app mobile (`tore/app`).
- Variables d’environnement initialisées depuis `.env.example`.

## Déployer backend (local + prod)

### Local (SQLite ou Postgres)
1. Copier la configuration:
   ```bash
   cp .env.example .env
   ```
2. Option A SQLite rapide (dev):
   ```bash
   export DATABASE_URL=sqlite:///./tore.db
   cd tore-backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. Option B Postgres local:
   ```bash
   docker compose --profile prod-like up -d db
   cd tore-backend
   alembic upgrade head
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### Prod-like (Docker Compose)
```bash
cp .env.example .env
docker compose --profile prod-like up -d --build
docker compose --profile prod-like exec backend-prodlike alembic upgrade head
```

### Sanity backend
```bash
python scripts/smoke_backend.py
```

## Déployer portal (build + serve) + config API base URL
1. Vérifier `VITE_API_BASE_URL` (prioritaire) dans `.env` ou `tore-portal/.env.local`.
2. Build:
   ```bash
   cd tore-portal
   npm ci
   npm run build
   ```
3. Serve statique:
   ```bash
   npm run preview -- --host 0.0.0.0 --port 4173
   ```

> Note: le portal lit `VITE_API_BASE_URL` (avec fallback legacy `VITE_API_BASE`).

## Config app Flutter (API base, deep links, signing)
- API base: `TORE_API_BASE_URL` (ex: `http://10.0.2.2:8000` sur émulateur Android).
- Deep links: schéma `tore://` (QR pack JOIN/ENTRY/BAR/MANAGER/WIFI/HUNT/BATTLES).
- Signing QR: backend doit avoir `TORE_QR_SIGNING_KEYS` configuré (rotation via key ring CSV).

### Android debug
```bash
cd tore/app
flutter pub get
flutter run -d android
```

### Android release
```bash
cd tore/app
flutter build apk --release
```

## Setup event en 60s (portal ORGA OU seed script)

### Option Portal ORGA
1. Login manager.
2. Créer un event via wizard ORGA.
3. Activer les modules requis (entry/bar/menu/wifi/safety/hunt/battles...).
4. Générer le QR pack depuis la page event (JOIN + staff + wifi).
5. Exporter/imprimer les QR.

### Option script seed (dev)
```bash
python scripts/seed_demo.py
```
Le script crée/réutilise:
- Demo bar
- Event LIVE + modulesOn complet
- Menu items
- Committee + year + membership admin
- Staff assignments ENTRY/BAR/MANAGER
- QR pack deep links (JOIN/ENTRY/BAR/MANAGER/WIFI/HUNT/BATTLES)

## QR Pack printing (JOIN/ENTRY/BAR/MANAGER/WIFI/HUNT/BATTLES)
- Générer les deep links via portal ORGA ou `scripts/seed_demo.py`.
- Imprimer 1 QR par feuille A5 minimum (lisibilité scanner).
- Séparer physiquement:
  - `JOIN` pour public
  - `ENTRY` pour équipe entrée
  - `BAR` pour bar staff
  - `MANAGER` pour backup ops
  - `WIFI` derrière bar/orga uniquement
  - `HUNT` / `BATTLES` en zones animation
- Vérifier scanner app sur 2 devices avant ouverture portes.

## Flow staff entry rush mode (offline queue)
1. Basculer staff sur écran Entry Staff.
2. Scanner QR user même si API lente/offline.
3. En mode offline: mettre en queue locale les scans (token + horodatage + décision locale).
4. Dès retour réseau: rejouer la queue dans l’ordre FIFO, conserver idempotency côté client.
5. Contrôler les rejets dans audit/checkins admin.

### Procédure de test offline entry queue
1. Ouvrir l’écran Entry Staff avec token staff valide.
2. Couper le réseau (mode avion / DevTools offline).
3. Scanner au moins 3 QR (dont 1 invalide).
4. Vérifier que les scans apparaissent en pending local.
5. Réactiver le réseau.
6. Vérifier replay automatique et convergence des compteurs entrée.

## Flow bar mode (dashboard / orders / menu)
1. Ouvrir Bar Dashboard.
2. Vérifier queue NEW/IN_PROGRESS.
3. Vérifier Menu Admin (stock/disponibilité des items démo).
4. Simuler quelques commandes et transitions de statut.
5. Vérifier analytics bar + exports fin de soirée.

## Monitoring rapide (audit viewer, flags, freeze)
- Santé API: `/healthz`.
- Modules actifs globaux: `/modules`.
- Admin flags (token global admin): `/admin/flags`.
- Audit viewer global: `/admin/audit`.
- Freeze d’event en incident majeur: `/admin/events/{event_id}/freeze`.

## Incident plan (OFFLINE, DEGRADED, FROZEN, sanctions, purge)
- **OFFLINE**: continuer scans/commandes en queue locale, limiter opérations critiques.
- **DEGRADED**: réduire modules non essentiels (battles/hunt/ticker) via flags/modules.
- **FROZEN**: global admin fige l’event, stop des mutations sensibles.
- **Sanctions**: utiliser endpoints admin sanctions pour abus utilisateurs.
- **Purge**: lancer purge RGPD via `/admin/purge/run` selon fenêtre de rétention.

## Checklist “T-30min” avant soirée
- [ ] `/healthz` OK (db_ok=true).
- [ ] `python scripts/smoke_backend.py` = PASS.
- [ ] Event LIVE correct, modules activés.
- [ ] Staff tokens ENTRY/BAR/MANAGER testés sur 1 scan réel.
- [ ] QR JOIN/WIFI/HUNT/BATTLES imprimés.
- [ ] Menu items bar disponibles + prix vérifiés.
- [ ] Admin flags revus (aucun flag d’urgence actif).
- [ ] Plan incident connu de l’équipe (offline/degraded/frozen).

## Post-event (exports + clôture)
- Exporter données bar (orders / analytics / menu snapshots si nécessaire).
- Exporter audit/incidents/safety pour archivage ops.
- Exécuter les opérations de purge rétention selon politique.
- Désactiver/révoquer tokens staff temporaires et conserver uniquement comptes permanents.
