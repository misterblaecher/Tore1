# APP Convergence Map — historique

Date de mise à jour : 11 septembre 2026

> **Statut : document historique, ne plus utiliser comme architecture cible.**

Ce document décrivait une phase antérieure où `lib/rebuild/` devait devenir le runtime principal. Cette décision n'est plus valable.

## Architecture canonique actuelle

Le runtime Flutter public est désormais :

```text
lib/main.dart
  -> ToreMvpApp
  -> core/
  -> features/
  -> shared/
  -> theme/
  -> ui/
```

`lib/rebuild/` est une architecture historique en cours de retrait. Il ne doit pas être reconnecté à `main.dart`, ni recevoir de nouvelles fonctionnalités ou de nouveaux imports de production.

La source de vérité pour la convergence et le nettoyage est maintenant :

- `docs/REBUILD_RETIREMENT_INVENTORY.md`

Ce document contient la classification fichier par fichier :

- **MIGRER** : conserver uniquement le comportement utile dans l'architecture active ;
- **TEMPORAIRE** : garder pendant la migration puis supprimer ;
- **SUPPRIMER** : ancien shell, doublons et surfaces historiques à retirer après validation.

## État validé avant nettoyage

Le parcours Android local suivant a été testé avec succès sur le runtime actif :

```text
Découverte
  -> détail soirée
  -> rejoindre
  -> Event Hub
  -> classement
  -> profil
```

Le backend local PostgreSQL répond correctement sur les contrats principaux de ce parcours, notamment `/events/{id}/public`, `/events/{id}/join_public` et `/events/{id}/context`.

## Règles de nettoyage

1. Ne jamais rebrancher `ToreRebuildApp`.
2. Ne pas supprimer `lib/rebuild/` en un seul lot.
3. Migrer d'abord les quelques comportements encore utiles identifiés dans `REBUILD_RETIREMENT_INVENTORY.md`.
4. Exécuter `flutter analyze` et `flutter test` entre chaque lot de suppression.
5. Rejouer le smoke Android principal après les suppressions structurantes.
6. Ne merger dans `main` qu'après validation explicite de la stabilisation.

## Contrats backend

La source de vérité des contrats mobile reste :

- `docs/MOBILE_BACKEND_CONTRACTS.md`

Tout ancien tableau ou plan dans l'historique Git qui présente `main.dart -> ToreRebuildApp` comme architecture cible doit être considéré comme obsolète.
