# PUBLIC PAGE LIFECYCLE — v3.4

```text
DRAFT → PUBLISHED ↔ HIDDEN
          ↓
      SUSPENDED
          ↓
       ARCHIVED
```

- DRAFT : jamais publiée.
- PUBLISHED : page officielle visible selon Visibility Center.
- HIDDEN : anciennement publiée, volontairement masquée.
- SUSPENDED : suspension de gouvernance.
- ARCHIVED : retirée du fonctionnement courant.

Nouvelle structure : `Structure.status = SETUP`, `PublicPage.status = DRAFT`.

La dernière étape onboarding permet explicitement « garder en brouillon » ou « publier maintenant ».

Structure LOCKED : page publique non rendue ; admin réservé aux memberships autorisés.

Les previews exigent une vraie permission ; le query param seul n’accorde rien.
