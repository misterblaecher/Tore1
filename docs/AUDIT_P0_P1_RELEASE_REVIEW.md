# TORÈ — Revue P0/P1 avant déploiement

Les correctifs techniques proposés ne constituent ni un pentest ni un avis juridique.

## Changements inclus
- Profil Docker prod-like : PROD forcé, secrets requis via `.env`, rate limiting partagé et PostgreSQL lié à l'interface locale.
- CORS : seulement les origines explicites ; suppression du wildcard `*.onrender.com`.
- Partenaires : limitations de débit, rollback atomique des inscriptions et réponses sans détail interne.
- Comptabilité : vérification de l'événement hôte et export CSV échappé / neutralisé contre les formules.
- Tests de régression dédiés aux routes, aux refus et aux transactions.

## Validation manuelle bloquante
- [ ] Configurer les secrets réels et les domaines HTTPS exacts sur l'environnement hébergé, jamais dans Git.
- [ ] Valider les tests de régression sur PostgreSQL en plus de SQLite ; simuler deux demandes simultanées sur la dernière invitation staff.
- [ ] Confirmer la politique de preuve d'appartenance lors de l'inscription d'un nouveau bar. La limitation de débit ne remplace pas la vérification du propriétaire.
- [ ] Valider les règles pour les événements coorganisés : les écritures comptables n'acceptent actuellement que les événements dont la structure est l'hôte principal.
- [ ] Réviser les documents `Privacy.tsx`, `Terms.tsx` et `Cookies.tsx` avec le DPO/juriste : traitements réels, durées de rétention, cookies effectifs, droits RGPD et vocabulaire de la roadmap V2. Ne pas publier des changements juridiques non validés.
- [ ] Tester le CSV avec l'outil de comptabilité effectivement utilisé.
- [ ] Tester une soirée complète, réseau instable, révocation staff et export comptable.

Garder la PR en **draft** jusqu'aux validations.
