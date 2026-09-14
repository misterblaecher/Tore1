# TORÈ Forum — Backend Security

## Trust boundary

The browser is not an authorization authority. Forum v2 authenticates through the existing TORÈ `AppUser` bearer token and resolves structure scope, membership, role, permissions and visibility in the backend for every private request.

A client-provided structure slug or resource id is only a lookup key. It never proves ownership or membership. DTOs whose structure scope comes from the URL do not define a trusted `structure_id` input; unexpected client fields cannot redirect a write into another tenant.

## Tenant isolation

Private resources are resolved against the current `Organization` before use. Cross-structure direct identifiers are rejected, generally with `404` where hiding resource existence is preferable. Event relations, documents, channels, albums, pages, accounting records, media and search results all remain structure-scoped.

Isolation is required for both reads and writes. Negative tests verify that an actor from Structure A cannot mutate Structure B documents, events, accounting entries or channels/messages even when direct resource IDs are known, and that the target rows remain unchanged.

## RBAC

Forum roles are structure-local. An authorization context contains:

- authenticated `AppUser`;
- current `Organization`;
- active `OrganizationMembership`;
- assigned `StructureRole`;
- server-derived permission set.

Revoked, ended or inactive memberships are not valid authorization contexts.

## Permission Grant Ceiling

A caller with `roles.manage` cannot grant permissions they do not themselves possess. `AuthorizationService.assert_grantable` is enforced on role creation, role changes and role assignment.

The following system-sensitive permissions are additionally non-delegable to custom roles, even if legacy data happens to place one of them on the actor:

- `structure.admin`;
- `ownership.transfer`;
- `accounting.unlock`.

System roles are immutable through normal custom-role endpoints. Separate regression tests cover each sensitive permission and a contaminated legacy-role fixture to ensure historical bad data cannot propagate `ownership.transfer`.

## Ownership

Ownership transfer is a dedicated workflow. Only the current owner may transfer ownership and the target must already be an active member of the same structure. The canonical Forum ownership field is `StructureGovernance.owner_user_id`; ownership extends the existing `Organization` rather than introducing a second Structure model.

The service updates the old/new owner role assignments and governance owner in one database transaction, verifies that exactly one active Owner assignment remains before commit, and appends an audit record. Tests cover non-owner denial, active same-structure transfer, non-member, revoked-member and cross-structure target rejection.

Creating a Claim does not mutate the current owner or structure lifecycle. Rejecting a Claim also leaves governance unchanged. Approval only transfers ownership when the explicit `transfer_ownership` review option invokes the dedicated ownership business service.

## Visibility

Visibility is enforced before serialization. Levels are normalized to:

`PUBLIC`, `TORE`, `MEMBERS`, `STAFF`, `BUREAU`, `TREASURY`, `PRIVATE`.

Public endpoints use explicit public DTO construction and do not serialize a private ORM record and then rely on the frontend to hide fields.

A public Structure requires both an `ACTIVE` structure lifecycle and a `PUBLISHED` public page. DRAFT/HIDDEN/SUSPENDED/ARCHIVED public-page states are not public, and public query parameters do not grant a higher audience.

## Stats and finance

Operational stats are intentionally separate from accounting. The operational stats endpoint exposes only operational metrics such as entries, scans, capacity and occupancy.

It does not return revenue, cost, estimated profit, actual profit, margin or turnover keys at all for a stats-only reader. Financial data requires the independent `accounting.view` permission and the accounting API.

Public event stats require an explicit `EventPublicSummary` publication; raw accounting data is never used as a public DTO.

## Channels and search

Channel listing, message reads and message writes all verify channel visibility in the resolved authorization context. Direct channel ids are not a bypass.

Permission-aware search filters documents, folklore and discussion messages through the same authorization/visibility checks before returning results. Negative tests use unique Treasury-document and Bureau-message terms and require exactly an empty result set for a Member, so title/type/snippet/id/count do not reveal existence.

## Documents and media

Document and media database records store opaque private storage keys. The local development adapter stores bytes outside the public web root. A download request must first pass structure and resource authorization before the backend returns the file.

Document metadata uses an explicit safe DTO that contains version number, original name, MIME type, size, checksum and timestamp but not `storage_key`, filesystem path or an internal bucket key. Direct metadata/download attempts by an unauthorized user remain unavailable even if the document ID, version number or internal storage key is already known.

No permanent public URL is generated for private documents/media. A future S3/R2 adapter must preserve this contract by using private objects and short-lived authorized delivery rather than public buckets.

## Accounting locking

A locked accounting record cannot be modified or deleted through normal CRUD. Unlock is a separate action requiring `accounting.unlock` and is audited.

## Audit

Forum high-risk writes append to the existing `AuditLog`, with structure-scoped before/after/context details stored in `StructureAuditContext`. Audit rows are not updated by the Forum write paths.

Audited actions include role changes, ownership transfer, visibility, event lifecycle, accounting lock/unlock, document lifecycle/version changes, public summary publication and other administrative writes.

## Negative tests

`tests/test_forum_backend_security.py` covers the initial server boundary and `tests/test_forum_backend_final_hardening.py` adds the final release-gate matrix: three explicit non-delegable permissions, contaminated legacy roles, ownership-transfer invariants, cross-tenant writes, client scope injection, serialized finance-key absence, search non-existence leakage, direct document/storage-key resistance, Claim review semantics, public-page lifecycle/audience behavior, OpenAPI request-body typing and storage-field schema checks.

The complete backend test suite plus the fresh-PostgreSQL Alembic job are required on the final PR HEAD before the PR can leave Draft.
