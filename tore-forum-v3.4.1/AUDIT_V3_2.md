# Audit TORÈ Forum v3.2

Date : 11 septembre 2026

## Audit de l’existant v2.1

La v2.1 corrigeait plusieurs bugs de démo, mais restait structurellement limitée : navigation pilotée par état local, données monolithiques, pages publiques absentes, actions souvent locales sans abstraction métier, permissions peu structurées, documents/médias non persistés en binaire et audit principalement démonstratif.

## Correctifs structurels réalisés

| Domaine | Problème v2.1 | Correction v3.2 |
|---|---|---|
| Routing | fausse SPA pilotée par état | History API + deep-links + `popstate` + serveur fallback |
| Architecture | gros fichier JS | séparation `core`, `data`, `services`, `views` |
| Structure active | implicite | `activeStructureId` + contexte structure + sélecteur seulement si multi-structure |
| Public / privé | page publique incomplète | site public distinct, events, albums, folklore, comité, contact |
| Events | édition partielle | lifecycle, détail, CRUD, publication et mock App TORÈ |
| App TORÈ | simple état visuel | service `syncApp()` remplaçable par API |
| Membres | liste + invitation simple | fiche, rôle, mandat, équipe, révocation, invitations |
| RBAC | logique surtout UI | guard dans la couche service mock |
| Visibilité | paramètres isolés | policies réelles utilisées par la page publique + previews |
| Discussions | sélection de salon limitée | chaque salon possède ses propres messages ; réactions + threads |
| Documents | métadonnées localStorage | métadonnées + blobs IndexedDB pour uploads réels |
| Albums | albums factices | albums + médias IndexedDB + publication + page publique détail |
| Folklore | contenu quasi statique | contenu propre par page + versions |
| Archives | listes codées en dur | génération depuis events, documents et albums |
| Planning | semaine factice | dates calculées mathématiquement + navigation semaine + CRUD |
| Comptabilité | tableau peu interactif | CRUD, validation/verrouillage, calculs dérivés, export CSV |
| Stats | chiffres fixes | stats liées à l’event sélectionné + export + résumé public OFF |
| Audit | seed statique | journal généré par les actions sensibles |
| Publications | absent | annonces officielles légères |
| Recherche | partielle | recherche transversale multi-entités |
| Onboarding | absent | création/revendication + owner + structure SETUP |
| PWA | cache générique | cache du shell uniquement, navigation fallback, pas de données privées |
| Responsive | éléments masqués | drawer salons mobile + grilles/tables adaptatives |
| Accessibilité | partielle | labels, aria icon buttons, focus visible, modales `role=dialog`, clavier |

## Contrôles réalisés

- syntaxe Node de tous les modules ;
- tests fonctionnels de services ;
- tests de routing profond ;
- vérification des actions `data-action` : **0 action déclarée sans handler** ;
- vérification des URLs profondes par serveur HTTP : HTTP 200 ;
- service worker versionné ;
- vérification de l’absence de cache explicite de données privées.

## Limites de l’environnement d’audit

Chromium headless est installé dans le conteneur, mais la politique du navigateur de l’environnement bloque l’accès HTTP local (`organization doesn’t allow you to view this site`). Les tests navigateur visuels automatisés n’ont donc pas pu être exécutés ici. Les tests fonctionnels et statiques passent, et le serveur répond correctement aux deep-links.

## Priorités backend restantes

1. Auth réelle.
2. Base multi-tenant avec contraintes `structure_id`.
3. RBAC serveur.
4. Document/Media Service cloud.
5. App Sync Service réel.
6. Search Service indexé.
7. Audit append-only serveur.
8. Email/QR invitations.
9. SSR/SSG SEO public.
10. RGPD et rétention.
