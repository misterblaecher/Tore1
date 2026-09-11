# TORÈ Forum — Backend / IndexedDB migration status

This file records what is authoritative on the server and what the v3.4.2 browser UI still keeps locally. "Backend" means a persisted `/forum/v2` contract exists. "Frontend connected" means the current UI actually uses that contract; the existence of an adapter alone is not counted as migrated.

| Feature | Local / IndexedDB today | Backend | Frontend connected |
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
| Claims | no full server flow | yes | no |
| Ownership transfer | no local authority | yes | no |

## Current frontend adapter

`tore-forum-v3.4.1/src/services/forum_api_repository.js` is the migration boundary. It uses the existing TORÈ bearer token and exposes Forum v2 calls for structure/context, members, roles, visibility, events, stats, accounting, channels/messages and search.

The adapter is gated by `FORUM_BACKEND_ENABLED`-equivalent browser configuration (`window.__TORE_FORUM_BACKEND_ENABLED__` or the documented local flag). This allows incremental screen migration without creating a second identity/session system.

## What is not yet considered migrated

The following remain local until their views are explicitly switched to `ForumApiRepository` and persistence is verified after reload against PostgreSQL:

- discussions/messages UI state;
- documents UI, uploads, downloads and versions;
- albums/media UI and image ordering;
- folklore editor/version restore UI;
- publication scheduling UI;
- accounting UI;
- audit UI;
- search UI;
- onboarding/local workflow state;
- remaining prototype fixtures and IndexedDB-only presentation state.

A feature must not be changed to "yes" in the `Frontend connected` column solely because a backend endpoint or adapter method exists.

## Production dependencies still external

- invitation email delivery provider;
- S3/R2-compatible private object-storage adapter;
- production storage credentials and retention/backup policy;
- rollout/feature-flag decision for making `/forum/v2` the only Forum authority.
