# TORÈ Forum — Backend Foundation

## Purpose

The Forum backend is the server-authoritative organizational surface for TORÈ structures. It is additive to the existing mobile/event APIs and deliberately reuses the existing TORÈ identity and domain models instead of creating a second account, structure, membership, or event system.

The v2 contract is exposed under `/forum/v2`.

## Existing TORÈ models reused

- `AppUser` is the only Forum user identity.
- `Organization` is the TORÈ Structure identity.
- `OrganizationMembership` is the membership/mandate identity.
- `Event` is the shared event record used by the app and Forum.
- `AuditLog` remains the append-only global audit record.

Forum-specific tables extend those records with governance, authorization, lifecycle, content, storage metadata and audit context.

## Forum extension models

`app/forum_models.py` contains the additive models:

- `StructureGovernance` — owner and structure lifecycle.
- `StructurePublicPage` — draft/published/hidden public-page lifecycle.
- `StructureRole` / `StructureRoleAssignment` — per-structure RBAC.
- `StructureInvitation` — hashed one-time invitation tokens.
- `StructureClaim` — claim requests that never mutate ownership merely by being created.
- `VisibilityPolicy` — per-section/resource visibility.
- `EventStructure` / `ForumEventLifecycle` — structure/event relation and Forum lifecycle.
- `AccountingEntry` — structure/event scoped accounting with immutable locked state.
- `EventPublicSummary` — explicitly published non-financial event summary.
- `StructureDocumentVersion` — private document version metadata.
- `StructureMediaAsset` / `StructureAlbumMedia` — private media storage metadata and album links.
- `StructurePageVersion` — folklore/history page history.
- `OrgaPostPublication` — publication/scheduling metadata for existing organization posts.
- `StructureAuditContext` — structure-scoped before/after audit context attached to `AuditLog`.

## Services

### Authorization

`app/services/forum_authorization.py` resolves authorization from the authenticated `AppUser`, the requested `Organization`, the active `OrganizationMembership`, and the assigned `StructureRole`.

The client never supplies an authoritative structure scope or permission set. Every private endpoint resolves and checks the scope server-side.

### Domain services

`app/services/forum_domain.py` owns high-risk transitions:

- role creation/update and Permission Grant Ceiling;
- role assignment;
- transactional ownership transfer;
- event lifecycle transitions;
- accounting lock/unlock semantics.

### Visibility

`VisibilityService` normalizes the Forum levels `PUBLIC`, `TORE`, `MEMBERS`, `STAFF`, `BUREAU`, `TREASURY`, `PRIVATE` and is used before private/public resources are serialized.

### Storage

`app/services/forum_storage.py` provides a private storage abstraction. Development uses a local filesystem root. Documents and album media are represented in the database by opaque storage keys and are served only after an authorization check through the Forum API.

The local adapter intentionally does not expose a permanent public file URL. The interface is designed so a production S3/R2 adapter can replace the storage implementation without changing Forum domain models.

## API composition

`app/main.py` installs `/forum/v2` while keeping legacy `/forum/*` available during the development migration. When `FORUM_BACKEND_ENABLED` is enabled for server authority, legacy Forum routes are removed from the composed application while `/forum/v2` remains installed.

The v2 surface covers:

- structures and context;
- members and roles;
- invitations, claims and ownership transfer;
- visibility policies and public-page lifecycle;
- events, lifecycle, operational stats and public summary;
- accounting;
- channels and messages;
- documents and versions;
- albums and media;
- folklore pages and versions;
- public posts and scheduling;
- scoped audit and permission-aware search;
- explicit public structure/event/album/folklore/post/stat endpoints.

## Authentication

Forum v2 exclusively reuses the existing TORÈ bearer-token authentication through `get_current_user`. There is no Forum account, Forum token, alternate session or fake login.

## Migration

Alembic revision `0013_forum_backend_foundation` extends the existing schema and backfills existing organizations/events/pages/posts. It is written to be idempotent with test/development databases where SQLAlchemy metadata may already have created additive Forum tables/indexes.

See `FORUM_BACKEND_SECURITY.md` for the security model and `FORUM_BACKEND_MIGRATION_STATUS.md` for the frontend migration state.
