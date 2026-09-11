# TEST RESULTS — TORÈ Forum v3.4.2

Date : 11 septembre 2026

## Résultat global

La suite de hardening frontend v3.4.2 passe sur GitHub Actions.

### Unit + security + regression

**PASS**

Commande :

```bash
npm test
```

Suites exécutées :

1. `product.test.mjs`
2. `static.test.mjs`
3. `security.test.mjs`
4. `tenant-integrity.test.mjs`
5. `governance-v3.4.test.mjs`
6. `privacy-lifecycle-v3.4.test.mjs`
7. `migration-v3.4.test.mjs`
8. `validation-v3.4.test.mjs`
9. `e2e.service.test.mjs`
10. `qa-matrix.test.mjs`
11. `final-hardening-v3.4.2.test.mjs`

Les syntax checks `node --check` des nouveaux modules et du Browser QA runner passent également.

## Régressions v3.4.2 couvertes

- Permission Grant Ceiling sur création de rôle.
- Permission Grant Ceiling sur modification de rôle.
- Blocage de `structure.admin` dans les rôles personnalisés.
- Blocage de `ownership.transfer` dans les rôles personnalisés.
- Blocage de `accounting.unlock` dans les rôles personnalisés.
- Blocage du contournement par changement de rôle membre.
- Blocage du contournement par invitation.
- Blocage d’un rôle legacy contaminé lors d’une nouvelle assignation/redélégation.
- `transferOwnership()` refusé si l’acteur n’est pas le véritable Owner principal.
- Fiche Event lisible avec `events.view=true` et `stats.view=false`.
- Stats Summary soumis à la politique Visibility `stats`.
- Résumé Stats sans revenue/cost/profit/margin/turnover.
- Publications PUBLISHED + Membres/Bureau correctement filtrées par audience.
- Politique de section Publications prioritaire sur la visibilité individuelle du post.
- Contact Privé inaccessible par route publique directe.
- `bannerBlobKey` réellement utilisé dans le rendu public.
- Ancien binaire Document conservé lors d’un remplacement de version.

## Browser QA

**PASS — 7/7 captures réelles**

GitHub Actions a utilisé Google Chrome en headless et vérifié :

- `/structures/lembuscade` — 1440 × 900
- `/structures/lembuscade/admin/dashboard` — 1440 × 900
- `/structures/lembuscade/admin/events/e1` — 1024 × 900
- `/structures/lembuscade/admin/visibility` — 768 × 1024
- `/structures/lembuscade/admin/settings` — 1440 × 900
- `/structures/lembuscade/admin/publications` — 390 × 844
- `/onboarding` — 390 × 844

Artifact GitHub Actions : `forum-v3.4.2-browser-screenshots`.

Le runner détecte automatiquement Chrome/Edge/Chromium, tue l’arbre de processus au timeout et produit des statuts distincts : `PASS`, `FAIL`, `INCONCLUSIVE`, `SKIPPED`.

## Incidents détectés pendant le hardening

Deux défauts ont été détectés par la CI et corrigés avant ce rapport :

1. le premier vrai test de versioning Document a montré que le `blobKey` historique n’était pas persisté après mutation du document ; le wrapper final capture désormais explicitement la version précédente et attache sa clé binaire à l’historique ;
2. le Browser QA Linux sélectionnait d’abord un wrapper Chromium inutilisable malgré la présence de Google Chrome ; l’ordre de détection privilégie maintenant Chrome stable et le Browser QA réel passe 7/7.

## Conclusion QA

Les suites fonctionnelles/sécurité existantes et les nouveaux tests v3.4.2 passent. Le Browser QA exécute réellement le site dans Chrome et termine proprement.

Cela valide le hardening du prototype frontend, mais ne transforme pas le stockage local et le RBAC client en frontière de sécurité de production. Voir `SECURITY.md` et `LIMITATIONS.md`.
