# TEST RESULTS — TORÈ Forum v3.4

Date : 11 septembre 2026

## Reproduction avant correction
Les tests ajoutés avant les patches ont reproduit :
1. Event CREATE avec `structureId: s_autre` accepté.
2. Owner downgrade accepté.
3. Staff `stats.view` recevant `revenue`.

## Suite finale
`npm test` : PASS.

10 suites : product, static, security, tenant-integrity, governance-v3.4, privacy-lifecycle-v3.4, migration-v3.4, validation-v3.4, e2e.service, qa-matrix.

201 appels `assert.*` statiques, plus les scénarios répétés dans les boucles d’attaque.

### Couverture v3.4
- CREATE tenant injection : Event, Channel, Album, Folklore, Planning, Accounting, PublicPost, Role, Document.
- UPDATE id/structureId injection.
- IDs étrangers connus : read/update/delete/download/archive refusés.
- Staff : list/get/export opérationnel sans finance ; export financier refusé.
- Treasurer : finance autorisée.
- Owner downgrade/revoke/alumni/system-role mutation : refusés.
- Ownership transfer : PASS, un seul Owner, audit présent.
- Anonymous onboarding/claim : AUTH_REQUIRED.
- Claim duplicate/reject/approve : PASS.
- PublicPage DRAFT/publish/hide/republish : PASS.
- Validation dates/nombres/timezones : PASS.
- Migration v3.3 → v3.4 : PASS.

## Deep links HTTP
HTTP 200 vérifié sur `/`, public structure, admin dashboard/members/settings/event detail, onboarding et principaux assets JS/CSS/SW.

## Browser QA
`npm run test:browser` tente de vraies captures 1440×1000, 390×844 et 768×900. Dans ce sandbox, Chromium reste bloqué au démarrage sur D-Bus et dépasse le timeout. Statut : INCONCLUSIVE, pas PASS. Le runner reste fourni pour CI/machine locale.


## Patch browser QA Windows

Le runner détecte automatiquement Chrome, Edge ou Chromium sous Windows/macOS/Linux. Il utilise désormais un dossier d’artefacts portable et retourne une erreur explicite si aucun navigateur n’est installé, au lieu d’un `SKIP` silencieux.
