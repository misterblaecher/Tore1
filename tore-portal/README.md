# TORÈ — Portail Web (MVP)

Petit backoffice web (React/Vite) pour gérer un bar :

- Login partenaire (PIN)
- Dashboard (bar + liste des events)
- Détail event (liste + ajout + suppression des drinks)

## Lancer en local

### 1) Backend

Dans `tore-backend/` :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) Frontend

Dans `tore-portal/` :

```bash
npm install
npm run dev
```

Par défaut, l'app appelle `http://localhost:8000`.
Tu peux surcharger via `VITE_API_BASE`.

## Auth

L'endpoint utilisé : `POST /partner/auth/login`.
Ensuite, le portail consomme :

- `GET /partner/portal/bar`
- `GET /partner/portal/events`
- `GET /partner/portal/events/{id}`
- `GET/POST/DELETE /partner/portal/events/{id}/drinks`

## Deploy Render (Static Site)
- Root Directory: `tore-portal`
- Build Command: `npm ci && npm run build`
- Publish Directory: `dist`