# TORÈ Forum v3.4.2 — Final Frontend Hardening

v3.4.2 ferme la phase principale de hardening du prototype frontend avant le chantier backend.
Elle conserve l’architecture v3.4.1 et corrige les derniers écarts de permissions, visibilité,
branding, versioning local et QA navigateur.

> L’app TORÈ sert à vivre la soirée. Le Forum TORÈ sert à faire vivre la structure.

## Lancer

```bash
npm run dev
```

- Public : `http://localhost:8080/structures/lembuscade`
- Admin : `http://localhost:8080/structures/lembuscade/admin/dashboard`
- Onboarding : `http://localhost:8080/onboarding`

## Garanties du prototype v3.4.2

- isolation locale `structureId` et champs tenant immuables ;
- RBAC central + Permission Grant Ceiling ;
- `structure.admin`, `ownership.transfer` et `accounting.unlock` non délégables aux rôles personnalisés ;
- transfert de propriété réservé au véritable Owner principal ;
- permissions secondaires optionnelles : une fiche Event reste lisible sans `stats.view` ;
- Stats Summary soumis au Visibility Center ;
- Contact et Publications soumis au Visibility Center ;
- publications multi-audience : Public / TORÈ / Membres / Staff / Bureau / Trésorerie / Privé ;
- finance filtrée indépendamment de `stats.view` ;
- logo et bannière modifiables après onboarding ;
- `bannerBlobKey` rendu dans le hero public ;
- onboarding avec visibilité Presentation, Events, Membres, Albums, Folklore, Sponsors, Contact, Publications et Stats ;
- document versioning local avec blob distinct pour chaque ancienne version créée après v3.4.2 ;
- Browser QA avec cleanup d’arbre de processus et statuts PASS / FAIL / INCONCLUSIVE / SKIPPED.

## Architecture

```text
UI / Views
    ↓
AuthorizationService + v3.4.2 hardening layer
    ↓
Domain / Services
    ↓
Scoped repositories
    ↓
localStorage metadata + IndexedDB blobs
```

La v3.4.2 ajoute des couches de hardening ciblées sans réécrire la v3.4.1 :

- `src/services/services-v3.4.2.js`
- `src/services/services-v3.4.2-final.js`
- `src/views/views-v3.4.2.js`
- `src/v3.4.2/runtime.js`

L’application les charge via l’import map de `index.html`. Les modules v3.4.1 restent disponibles comme base stable.

## Tests

```bash
npm test
npm run test:security
npm run test:integrity
npm run test:hardening
npm run test:e2e
npm run test:qa
npm run test:browser
```

La suite v3.4.2 ajoute `tests/final-hardening-v3.4.2.test.mjs` aux 10 suites existantes.
Une GitHub Action dédiée (`Forum v3.4.2 QA`) exécute la suite complète, les syntax checks et le Browser QA.

### Browser QA

Le runner détecte Chrome, Edge ou Chromium sous Windows/macOS/Linux.

```powershell
npm run test:browser
```

Forçage Windows si nécessaire :

```powershell
$env:CHROMIUM="C:\Program Files\Google\Chrome\Application\chrome.exe"
npm run test:browser
```

Statuts :

- `PASS` : navigateur lancé et toutes les captures réussissent ;
- `FAIL` : navigateur fonctionnel mais scénario/application en échec ;
- `INCONCLUSIVE` : navigateur trouvé mais environnement incompatible (sandbox, D-Bus, permissions OS, crash infra) ;
- `SKIPPED` : aucun navigateur compatible trouvé.

Les captures sont écrites dans `tests/artifacts/browser/`.

## Documentation

- `CHANGELOG_v3.4.2.md`
- `SECURITY.md`
- `PERMISSIONS.md`
- `OWNERSHIP.md`
- `CLAIM_LIFECYCLE.md`
- `PUBLIC_PAGE_LIFECYCLE.md`
- `MIGRATIONS_v3.4.md`
- `VISIBILITY_MATRIX_v3.4.2.md`
- `TEST_RESULTS_v3.4.2.md`
- `LIMITATIONS.md`

## Important : sécurité production

Cette version impose les invariants métier dans le prototype frontend mais **IndexedDB/localStorage ne sont pas une frontière de sécurité de production**.

Le backend TORÈ devra obligatoirement :
- authentifier les sessions côté serveur ;
- dériver/imposer `structureId` depuis un contexte serveur autorisé ;
- réappliquer le Permission Grant Ceiling côté serveur ;
- revérifier RBAC + Visibility sur chaque lecture/écriture ;
- ne jamais sérialiser les données financières vers un utilisateur non autorisé ;
- protéger les fichiers privés par URLs signées ;
- filtrer recherche et exports côté serveur ;
- stocker les AuditLogs sensibles côté serveur, idéalement append-only ;
- ajouter monitoring, rate limiting et mécanismes RGPD.
