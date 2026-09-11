# TORÈ Forum v2.1 — Audit bugs & correctifs

Date : 11 septembre 2026

## Résumé

Audit complet du front-end livré en v2. La priorité a été donnée aux bugs reproductibles, aux contrôles visibles mais inactifs, aux régressions de mise en page et aux risques de persistance/sécurité côté navigateur.

## Correctifs appliqués

| Sévérité | Problème | Correctif |
|---|---|---|
| Critique UI | Les SVG n'avaient pas de taille générique. Hors sidebar, certains icônes pouvaient prendre leur taille intrinsèque SVG et devenir énormes. | Taille explicite globale pour `.ico`, puis tailles spécifiques boutons, recherche, KPI, titre et pièces jointes. |
| Majeure | Les réactions aux messages étaient des `<span>` statiques. Impossible de liker. | Réactions transformées en boutons interactifs. Toggle like + cœur, compteur, `aria-pressed`, persistance `localStorage`. |
| Majeure | `document.addEventListener('keydown', shortcut)` était ré-enregistré à chaque rendu SPA. | Remplacé par `document.onkeydown = shortcut` afin d'éviter l'accumulation de listeners. |
| Majeure PWA | Le service worker conservait l'ancien cache sans nettoyage ni activation forcée. | Cache versionné `v2.1.0`, `skipWaiting`, `clients.claim`, suppression des vieux caches, navigation network-first. |
| Majeure | Un `localStorage` corrompu pouvait empêcher tout le site de démarrer. | Chargement défensif avec `try/catch`, migration douce et valeurs par défaut. |
| Sécurité | Les textes saisis (messages, événements, tâches, albums, membres, fichiers) pouvaient être réinjectés dans `innerHTML`. | Échappement HTML centralisé via `h()` sur les données utilisateur affichées. |
| UX | La recherche globale affichait seulement un toast. | Recherche réelle dans navigation, événements et messages avec résultats navigables. |
| UX | Plusieurs boutons visibles n'avaient aucune action. | Tous les boutons visibles ont maintenant une action, un filtre, une navigation, un dialogue ou un export. |
| Events | Les boutons « Gérer » ne faisaient rien. | Dialogue d'édition de l'événement, modification du titre/lieu/statut et persistance locale. |
| Events | Les onglets Brouillons/Terminés/Archives étaient décoratifs. | Filtrage fonctionnel de la table. |
| Planning | Flèches de semaine et « Aujourd'hui » inactifs. | Navigation de semaine fonctionnelle et libellé recalculé. |
| Planning | Bouton « Ajouter » ouvrait le mauvais type d'action. | Dialogue « Ajouter au planning » séparé de l'ajout de tâche. |
| Discussions | Filtre de salons inactif. | Filtrage instantané des salons. |
| Discussions | Sélection de salon inerte. | Sélection visuelle + titre et placeholder du salon mis à jour. |
| Discussions | Téléchargement de pièce jointe inactif. | Téléchargement local de démonstration branché. |
| Discussions | Zone de chat pouvait dépasser verticalement au lieu de scroller. | Hauteur contrainte + `min-height:0` + scroll interne. |
| Documents | Import inactif. | Sélecteur de fichiers réel, métadonnées ajoutées à la table et persistées localement. |
| Documents | Sélection de dossier/ligne inerte. | Filtre par dossier et surbrillance de sélection. |
| Albums | « Nouvel album » et suppression inactifs. | Création locale persistante, suppression persistante et compteurs d'onglets recalculés. |
| Albums | Le panneau détail restait figé sur « Bal 2026 ». | Le détail se synchronise avec la carte sélectionnée et le premier album disponible. |
| Archives | Années, export et création sans action. | Navigation vers l'année, export CSV, création via dialogue. |
| Folklore | Navigation de sommaire et édition inactives. | Sélection des sections + dialogue d'édition/version locale. |
| Comptabilité | Export inactif. | Export CSV. |
| Membres | Invitation inerte. | Formulaire d'invitation avec validation et ajout local persistant. |
| Visibilité | Aperçus Public/Membre/Bureau inactifs. | Sélection fonctionnelle de l'aperçu et sauvegarde persistante. |
| Audit logs | Export, refresh et sélection des lignes inactifs. | Export CSV, refresh, sélection d'une ligne et mise à jour du panneau détail. |
| Accessibilité | Peu de feedback clavier sur les contrôles. | `:focus-visible`, libellés ARIA sur réactions/téléchargements et états pressés. |

## Tests de régression ajoutés

Le fichier `tests/audit.mjs` vérifie automatiquement :

- rendu de toutes les routes principales ;
- échappement des entrées utilisateur ;
- fonctionnement du like et du retrait du like ;
- présence des tailles SVG correctes ;
- absence d'accumulation du listener clavier ;
- invalidation du cache PWA ;
- présence des actions sur les contrôles principaux ;
- existence du wiring recherche/filtres/sélections.

Commande :

```bash
node tests/audit.mjs
```

Résultat actuel : **PASS**.

## Limite volontaire

Cette version reste un front-end autonome : les données sont persistées dans `localStorage`. L'authentification, les permissions serveur, la base de données, les uploads réels et la synchronisation avec l'app TORÈ nécessitent toujours le backend de production.
