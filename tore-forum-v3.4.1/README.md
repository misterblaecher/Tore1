# TORÈ Forum v3.4 — Tenant Integrity & Governance

v3.4 est une passe de hardening de la v3.3. Elle ne refond pas le Forum : elle consolide
les invariants multi-tenant, la gouvernance Owner, la confidentialité financière,
le workflow de revendication et le lifecycle de la page publique.

> L’app TORÈ sert à vivre la soirée. Le Forum TORÈ sert à faire vivre la structure.

## Lancer

```bash
npm run dev
```

Puis ouvrir :

- Public : `http://localhost:8080/structures/lembuscade`
- Admin : `http://localhost:8080/structures/lembuscade/admin/dashboard`
- Onboarding : `http://localhost:8080/onboarding`

Le serveur local fournit le fallback SPA pour les deep-links History API.

## Architecture

```text
UI / Views
    ↓
AuthorizationService
    ↓
Domain / Services
    ↓
Scoped repositories
    ↓
localStorage metadata + IndexedDB blobs
```

### Invariants v3.4

- `id`, `structureId` et `createdAt` ne sont pas mutables via les updates.
- Les services utilisent des whitelists de champs.
- Le tenant des créations provient du contexte actif, jamais d’un payload normal.
- Les accès cross-tenant par ID connu échouent.
- `stats.view` n’accorde aucune donnée financière.
- Le rôle Owner est un rôle système.
- Une structure possède exactement un owner principal actif.
- Le changement d’owner passe uniquement par `transferOwnership()`.
- L’onboarding et les claims exigent un utilisateur authentifié.
- Une revendication est une `StructureClaim` séparée.
- Une `PublicPage` possède son propre lifecycle.
- Le centre Archives est une vue agrégée, pas une duplication de ressources.

## Tests

```bash
npm test
npm run test:security
npm run test:integrity
npm run test:e2e
npm run test:qa
npm run test:browser
```

La suite principale contient 10 fichiers de tests et 201 appels d’assertion statiques,
auxquels s’ajoutent des scénarios générés dans des boucles d’attaque multi-tenant.


### Browser QA sous Windows

`test:browser` détecte maintenant automatiquement Google Chrome, Microsoft Edge ou Chromium.

```powershell
npm run test:browser
```

Si l’auto-détection échoue, indique explicitement l’exécutable :

```powershell
$env:CHROMIUM="C:\Program Files\Google\Chrome\Application\chrome.exe"
npm run test:browser
```

Pour Edge, selon l’installation :

```powershell
$env:CHROMIUM="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
npm run test:browser
```

Les captures sont écrites dans `tests/artifacts/browser/`.

## Documents

- `CHANGELOG_v3.4.md`
- `SECURITY.md`
- `PERMISSIONS.md`
- `OWNERSHIP.md`
- `CLAIM_LIFECYCLE.md`
- `PUBLIC_PAGE_LIFECYCLE.md`
- `MIGRATIONS_v3.4.md`
- `VISIBILITY_MATRIX.md`
- `TEST_RESULTS_v3.4.md`
- `LIMITATIONS.md`

## Important : sécurité production

Cette version impose les invariants métier dans le prototype frontend mais
**IndexedDB/localStorage ne sont pas une frontière de sécurité de production**.

Le backend futur devra notamment :
- authentifier les sessions côté serveur ;
- dériver/imposer le tenant depuis une session/autorisation serveur ;
- revérifier toutes les permissions ;
- ne jamais faire confiance à un `structureId` reçu dans un body client ;
- ne jamais envoyer la finance aux utilisateurs non autorisés ;
- fournir des URLs signées pour les fichiers privés ;
- filtrer la recherche côté serveur ;
- autoriser les exports côté serveur ;
- stocker les audit logs sensibles côté serveur, idéalement append-only.
