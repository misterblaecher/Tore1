# TEST RESULTS — TORÈ Forum v3.3

Date : 11 septembre 2026

## Suites automatisées

`npm test`

- Product tests: PASS
- Static tests: PASS
- Security negative tests: PASS
- Service E2E flows: PASS
- Role / visibility QA matrix: PASS

## Sécurité couverte

- cross-tenant document/event denial ;
- admin accounting denial for standard member ;
- direct public URL visibility bypass ;
- preview query bypass ;
- search leak on Treasury content ;
- channel read denial ;
- channel post denial ;
- direct document download denial ;
- unauthorized role creation ;
- unauthorized settings mutation ;
- accounting LOCKED mutation denial ;
- public member `publicProfile=false` privacy ;
- audit tenant isolation.

## Deep links / HTTP

Testés avec le serveur SPA sur un port isolé :

- `/`
- `/structures/lembuscade`
- `/structures/lembuscade/albums`
- `/structures/lembuscade/admin/dashboard`
- `/structures/lembuscade/admin/documents`
- `/structures/lembuscade/admin/accounting`
- `/onboarding`
- `/src/core/authorization.js`
- `/styles.css`

Résultat : HTTP 200 pour chaque route/asset.

## Vérification syntaxique

`node --check` : PASS sur :
- `src/app.js`
- `src/services/services.js`
- `src/core/authorization.js`
- `src/views/views.js`

## Browser QA

Le runner `tests/browser-smoke.mjs` tente de lancer le Chromium système sur :
- public desktop 1440×1000 ;
- admin desktop 1440×1000 ;
- discussions mobile 390×844 ;
- documents tablette 768×900.

Dans le sandbox actuel, Chromium est installé mais reste bloqué sur D-Bus et dépasse le timeout,
y compris sur `about:blank`. Le résultat navigateur est donc **INCONCLUSIVE**, pas PASS.

Le script est conservé dans le projet pour être exécuté dans une CI/machine où Chromium peut démarrer.
