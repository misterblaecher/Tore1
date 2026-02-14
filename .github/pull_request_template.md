## Résumé
- [ ] Décrire brièvement les changements.

## Tests & checks exécutés
- [ ] `cd tore-backend && pytest -q`
- [ ] `cd tore-portal && npm ci && npm run build`
- [ ] `cd tore-backend && alembic upgrade head` (ou justification)
- [ ] `./scripts/sanity_check.sh`

## Impact release / exploitation
- [ ] Pas de dépendance lourde ajoutée
- [ ] Migrations DB traitées / non applicables
- [ ] Variables d'environnement revues

## Gouvernance (si applicable)
- [ ] Reason codes vérifiés
- [ ] Idempotence vérifiée
- [ ] Audit trail / logs vérifiés

## Notes complémentaires
- Risques connus:
- Rollback plan:
