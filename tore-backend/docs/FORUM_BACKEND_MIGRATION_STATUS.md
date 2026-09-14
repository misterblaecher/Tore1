# TORÈ Forum — Backend / IndexedDB migration status

This file separates two facts that must not be conflated:

- **Backend model/API available** means a persisted, server-authoritative `/forum/v2` contract exists.
- **Frontend consuming backend** means the current Forum browser UI actually hydrates and/or writes that feature through the backend bridge.

The existence of an endpoint or of a `ForumApiRepository` method alone does **not** make a feature frontend-migrated.

| Feature | Local / IndexedDB today | Backend model/API available | Frontend consuming backend |
|---|---:|---:|---:|
| Structure identity/settings | yes | yes | partial |
| Members / mandates | yes | yes | partial |
| Roles / permissions | yes | yes | partial |
| Visibility policies | yes | yes | partial |
| Events / lifecycle | yes | yes | partial |
| Operational stats | yes/demo | yes | no |
| Accounting | yes | yes | no |
| Channels | yes | yes | no |
| Messages / threads | yes | yes | no |
| Documents metadata | yes | yes | no |
| Document bytes / versions | local/demo | yes | no |
| Albums | yes | yes | no |
| Media bytes / ordering | local/demo | yes | no |
| Folklore pages | yes | yes | no |
| Folklore version history | local/demo | yes | no |
| Public posts / schedule | yes | yes | no |
| Audit log | local/static | yes | no |
| Permission-aware search | local | yes | no |
| Public page lifecycle | local | yes | partial |
| Public stats summary | no/derived demo | yes | no |
| Invitations | local/demo | yes | no |
| Claims | no full browser flow | yes | no |
| Ownership transfer | no local authority | yes | no |

## Current frontend bridge

`tore-forum-v3.4.1/src/services/forum_api_repository.js` is the HTTP boundary and `src/services/forum_backend_bridge.js` is the current incremental migration bridge. Both reuse the existing TORÈ bearer token; no second Forum identity/session exists.

When enabled, the bridge currently hydrates server state for:

- structure context;
- roles;
- members;
- visibility policies;
- events.

It currently mirrors mutations for:

- Structure settings;
- Members;
- Roles;
- Visibility;
- Events and event lifecycle transitions;
- Public Page publish/hide.

Those surfaces are therefore marked **partial**, not fully migrated: the v3.4.2 UI still keeps local/IndexedDB state and the bridge performs incremental synchronization rather than making every view server-only.

The bridge can be enabled with one of the supported browser controls:

- `<meta name="tore-forum-backend" content="true">`;
- `window.TORE_FORUM_BACKEND_ENABLED = true`;
- `window.FORUM_BACKEND_ENABLED = true`;
- local development flag `localStorage['tore-forum-backend-enabled'] = '1'`.

Feature detection is DOM-safe: importing/calling it in Node or SSR-like environments without `document.querySelector` falls back to disabled instead of throwing.

## What is not yet considered frontend-migrated

The following remain local until their views are explicitly switched to the server contract and persistence is verified after reload against PostgreSQL:

- discussions/messages UI state;
- documents UI, uploads, downloads and versions;
- albums/media UI and image ordering;
- folklore editor/version restore UI;
- publication scheduling UI;
- accounting UI;
- audit UI;
- search UI;
- onboarding/local workflow state;
- invitations/claims browser workflows;
- ownership-transfer browser workflow;
- remaining prototype fixtures and IndexedDB-only presentation state.

The backend already exposes contracts for these features, including authorization-safe document metadata/version delivery, but they remain **Frontend consuming backend = no** until the UI actually uses them.

## Production dependencies still external

- invitation email delivery provider;
- S3/R2-compatible private object-storage adapter;
- production storage credentials and retention/backup policy;
- rollout/feature-flag decision for making `/forum/v2` the only Forum authority.
