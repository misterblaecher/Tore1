# VISIBILITY MATRIX — TORÈ Forum v3.4.2

## Hiérarchie d’audience

| Audience | Public | TORÈ | Membres | Staff | Bureau | Trésorerie | Privé |
|---|---:|---:|---:|---:|---:|---:|---:|
| Visiteur public | ✓ | — | — | — | — | — | — |
| Utilisateur TORÈ | ✓ | ✓ | — | — | — | — | — |
| Membre | ✓ | ✓ | ✓ | — | — | — | — |
| Staff | ✓ | ✓ | ✓ | ✓ | — | — | — |
| Bureau | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Trésorerie | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Owner/admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Matrice ressources

La visibilité de section ne remplace jamais une permission interne. Les deux conditions sont cumulatives dans l’espace privé.

| Ressource | Public | TORÈ | Membre | Staff | Bureau | Trésorerie | Owner | Garde supplémentaire |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Page structure PUBLISHED | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | PublicPage lifecycle |
| Events publics | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | `events` + event.visibility |
| Albums | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | `albums` + album.visibility |
| Folklore | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | `folklore` + page.visibility |
| Contact | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | section `contact` |
| Publications | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | section `publications` + status + post.visibility |
| Stats summary | selon policy | selon policy | selon policy | selon policy | selon policy | selon policy | ✓ | section `stats` + event.visibility + publicSummary |
| Documents admin | — | — | permission | permission | permission | permission | ✓ | `documents.view` + document.visibility |
| Channels admin | — | — | selon channel | selon channel | selon channel | selon channel | ✓ | channel.visibility + `channels.post` pour écrire |
| Accounting | — | — | — par défaut | — par défaut | selon rôle | ✓ | ✓ | `accounting.view` |
| Role management | — | — | — | selon rôle | selon rôle | selon rôle | ✓ | `roles.manage` + Permission Grant Ceiling |
| Ownership transfer | — | — | — | — | — | — | ✓ | `structure.ownerUserId === actor` |

## Publications

Une publication est rendue seulement si :

```text
section publications autorisée
AND isPublishedNow(post)
AND audience >= post.visibility
```

Le statut PUBLISHED n’implique donc jamais une visibilité Public.

## Stats

Un résumé d’Event est rendu seulement si :

```text
section stats autorisée
AND event visible
AND publicSummary présent
```

Le résumé ne contient jamais revenue, cost, profit, margin ou turnover.

## Contact

Le bloc homepage et la route `/contact` partagent la même politique de section. Une route directe ne contourne pas la règle.

## Permission ceiling

La matrice de visibilité ne permet pas d’accorder des permissions internes. Un gestionnaire de rôles ne peut déléguer que ses propres permissions, et jamais les permissions système non délégables.
