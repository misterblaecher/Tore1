# PERMISSIONS v3.4

## Structure / governance
- `structure.admin`
- `structure.manage`
- `ownership.transfer`

## Members / roles
- `members.view`
- `members.manage`
- `roles.manage`

## Events
- `events.view`
- `events.manage`
- `events.publish`

## Documents
- `documents.view`
- `documents.download`
- `documents.manage`

## Albums
- `albums.view`
- `albums.manage`

## Folklore
- `folklore.view`
- `folklore.manage`

## Planning
- `planning.view`
- `planning.manage`

## Stats / finance
- `stats.view` — données opérationnelles uniquement
- `accounting.view` — données financières
- `accounting.manage`
- `accounting.unlock`

## Governance / content
- `visibility.manage`
- `audit.view`
- `channels.post`
- `channels.manage`
- `publications.manage`
- `archives.view`

Permissions internes et niveaux de visibilité sont indépendants. `stats.view` n’implique jamais `accounting.view`.
