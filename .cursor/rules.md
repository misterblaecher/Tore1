---
description: Règles TORÈ non négociables pour le repo et le comportement des agents Cursor
---

## Contrat TORÈ – règles de base

- **Sécurité et intégrité des données**
  - Ne jamais introduire de changement qui risque une **double écriture** (double débit, double ticket, double entrée).
  - Préserver à tout moment la **cohérence entre backend, app Flutter et portal** (même sémantique métiers, mêmes codes d’erreur).

- **Tests obligatoires**
  - Toute évolution **non triviale** (logique métier, endpoints backend, state management Flutter, pages portal) doit être couverte par des **tests automatiques**.
    - Backend : tests `pytest` sous `tore-backend/tests/` pour les nouveaux endpoints / cas métiers importants, y compris les branches d’erreur (ex. `MODULE_OFF`, 403, 404).
    - Portal : ajouter/adapter des tests si le projet en contient déjà, sinon au minimum documenter les scénarios à tester manuellement.
    - Flutter : privilégier des tests de logique (providers, services) et/ou des tests d’intégration lorsque pertinent.
  - Ne jamais supprimer ou affaiblir des tests existants sans **raison explicite** documentée dans le diff (commit/PR).

- **Idempotence des écritures**
  - Le backend contient déjà plusieurs tables d’**idempotence** (ex. `EventCreateIdempotency`, `EventStaffAssignmentIdempotency`, `EventQrPackIdempotency`, `EventAppWriteIdempotency`, …).
  - **Règles** :
    - Toute nouvelle écriture exposée à des **retries clients** (mobile, portal) doit être **idempotente** via la combinaison `(actor, action, idempotency_key)` ou un équivalent adapté.
    - Une même requête (même clé d’idempotence) ne doit jamais générer :
      - de double débit / double crédit de wallet,
      - de double création d’entité métier,
      - de duplication de side-effects externes (ex. notifications).
    - Lorsqu’on étend un flux déjà idempotent, on **réutilise** la clé d’idempotence existante plutôt que d’en inventer une nouvelle incohérente.
  - Ne jamais casser la garantie fournie par les tables d’idempotence existantes (éviter les migrations destructrices, renoms non justifiés, ou changements de sémantique silencieux).

- **Offline et mode lecture seule**
  - L’app Flutter supporte des scénarios **offline / réseau dégradé** (cf. `isWriteBlocked`, `isWriteBlockedByEventState`, bannières `ServiceLimitedBanner`, etc.).
  - **Principe** : en mode offline ou réseau dégradé, un écran doit être **au minimum lisible**, et les écritures doivent :
    - être **clairement bloquées** (désactivation boutons + message explicite), ou
    - être explicitement **queue-ées / synchronisées** avec une logique fiable (à implémenter consciemment, jamais implicitement).
  - Toute nouvelle feature qui écrit côté backend doit :
    - respecter les mêmes helpers UI de blocage/feedback si elle est utilisée en mobile,
    - tolérer le fait que le client puisse être en lecture seule (et donc ne pas nécessiter de “hack” côté backend pour contourner les checks).

- **Modules ON/OFF**
  - Les événements disposent d’un champ `modules_on` (JSON) et le portal d’un mapping `DEFAULT_MODULES_ON` / `WIZARD_MODULE_MAP` pour activer/désactiver chaque module (`menu`, `wallet`, `ticker`, `entry`, `broadcast`, `music`, `vote`, `polymarket`, `hunt`, `battles`, `wifi`, `safety`, `map`, …).
  - Il existe aussi des flags d’environnement (`TORE_MODULE_*`) qui peuvent couper certains modules globalement (tests existants autour de `MODULE_OFF`).
  - **Règles** :
    - Tout nouveau endpoint ou nouvelle logique backend **doit vérifier** que le module correspondant est ON pour l’événement et non désactivé globalement.
    - En cas de module désactivé :
      - retourner un code d’erreur cohérent (`404` ou `403`) avec un payload structuré (`reason` ou `code` = `"MODULE_OFF"`), aligné sur les routes existantes,
      - ne jamais faire “comme si de rien n’était” (pas d’actions silencieuses lorsqu’un module est OFF).
    - Côté clients (Flutter, portal), gérer proprement cette erreur comme **“fonctionnalité désactivée”**, pas comme un bug réseau.

- **États d’événement (event_state / publication_status)**
  - Les événements ont plusieurs dimensions d’état, dont au minimum :
    - `event_state` (ex. `LIVE`, `PAUSE`, `READ_ONLY`, `MENU_ONLY`, `DEGRADED`, `FROZEN`, `CLOSED`, `OFF`, …) côté runtime.
    - `publication_status` (ex. `DRAFT`, autres statuts de publication) côté visibilité / lifecycle.
  - **Règles** :
    - Toute écriture liée à un événement doit respecter la politique de blocage associée à son `event_state` (ex. pas de nouvelles commandes si l’état courant équivaut à une pause).
    - Côté Flutter, réutiliser les helpers existants (`isWriteBlockedByEventState`, `isWriteBlocked`, `writeBlockedMessage`, badges d’état) pour toute nouvelle feature au lieu de réinventer une logique parallèle.
    - Côté backend, **ne pas autoriser** une écriture incompatible avec l’état d’événement, même si le client ne fait pas correctement son check.
    - Ne jamais changer la signification métier d’un état existant sans migration cohérente et mise à jour synchronisée des trois piliers : backend, app Flutter, portal.

- **Style d’API et conventions**
  - Conserver les conventions existantes :
    - REST simple, verbes HTTP standards (`GET` lecture, `POST` création/action, `PATCH`/`PUT` mise à jour, `DELETE` suppression).
    - Identifiants numériques/chaînes stables dans les URLs (`/events/{eventId}`, `/bars/{barId}`, etc.).
    - Codes d’erreur structurés (`reason`, `code`, `message`) réutilisant les constantes déjà en place (`MODULE_OFF`, etc.).
  - Toute nouvelle route doit être cohérente avec les routers existants du même domaine (regroupement dans `app/routers/…`, préfixes `/partner/…` ou `/app/…` adaptés).

- **Scope de ces règles pour les agents Cursor**
  - Ces règles s’appliquent à **toute modification** proposée ou effectuée par un agent dans ce repo.
  - Interdictions explicites pour les agents :
    - ne pas désactiver ou contourner les mécanismes d’idempotence,
    - ne pas supprimer les checks de modules ON/OFF ou d’état d’événement,
    - ne pas ajouter de chemins écriture offline qui by-passeraient les garde-fous existants,
    - ne pas modifier `models.py` ou les migrations Alembic sans plan de migration clair validable par tests.

# TORÈ — Cursor rules

Repo: monorepo (backend FastAPI, Flutter app, Portal React)

## Architecture
- Backend: tore-backend/ (FastAPI + SQLAlchemy + Alembic + pytest)
- App: tore/app/ (Flutter + Riverpod + Dio + offline cache)
- Portal: tore-portal/ (React + TS + Vite)

## Non-negotiables
- Ne jamais casser les tests existants.
- Toute nouvelle feature backend => tests pytest.
- Toute nouvelle action write => idempotency key + audit log.
- Offline-first: prévoir READ_ONLY quand réseau down.
- Modules ON/OFF: UI ne montre que les modules ON.
- Event state: respecter PAUSE / DEGRADED / FROZEN partout.

## Conventions API
- Prefer /me snapshot for identity+roles+capabilities
- Prefer capability checks (can.*) over role-string checks in clients
- Keep endpoints stable; document changes.

## Output style
- Small, focused commits
- Explicit naming, minimal magic
- Comment business rules
