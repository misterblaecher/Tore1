# TORÈ Forum — Backend Security

## Trust boundary

The browser is not an authorization authority. Forum v2 authenticates through the existing TORÈ `AppUser` bearer token and resolves structure scope, membership, role, permissions and visibility in the backend for every private request.

A client-provided structure slug or resource id is only a lookup key. It never proves ownership or membership.

## Tenant isolation

Private resources are resolved against the current `Organization` before use. Cross-structure direct identifiers are rejected, generally with `404` where hiding resource existence is preferable. Event relations, documents, channels, albums, pages, accounting records, media and search results all remain structure-scoped.

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

This prevents a manager from self-escalating or delegating high-risk permissions such as:

- `structure.admin`;
- `ownership.transfer`;
- `accounting.unlock`.

System roles are immutable through normal custom-role endpoints.

## Ownership

Ownership transfer is a dedicated workflow. Only the current owner may transfer ownership and the target must already be an active member of the same structure. The service updates the old/new owner role assignments and governance owner in one database transaction and verifies that exactly one active Owner assignment remains before commit.

Creating a Claim does not mutate the current owner or structure lifecycle. A claim requires an explicit authorized review before any membership/ownership change.

## Visibility

Visibility is enforced before serialization. Levels are normalized to:

`PUBLIC`, `TORE`, `MEMBERS`, `STAFF`, `BUREAU`, `TREASURY`, `PRIVATE`.

Public endpoints use explicit public DTO construction and do not serialize a private ORM record and then rely on the frontend to hide fields.

A public Structure requires both an eligible structure lifecycle and a published public page. DRAFT/HIDDEN/SUSPENDED/ARCHIVED public-page states are not public.

## Stats and finance

Operational stats are intentionally separate from accounting. The operational stats endpoint exposes only operational metrics such as entries, scans, capacity and occupancy.

It does not return revenue, costs, estimated profit or actual profit. Financial data requires the independent `accounting.view` permission and the accounting API.

Public event stats require an explicit `EventPublicSummary` publication; raw accounting data is never used as a public DTO.

## Channels and search

Channel listing, message reads and message writes all verify channel visibility in the resolved authorization context. Direct channel ids are not a bypass.

Permission-aware search filters documents, folklore and discussion messages through the same authorization/visibility checks before returning results. Private terms therefore must not leak through search results.

## Documents and media

Document and media database records store opaque private storage keys. The local development adapter stores bytes outside the public web root. A download request must first pass structure and resource authorization before the backend returns the file.

No permanent public URL is generated for private documents/media. A future S3/R2 adapter must preserve this contract by using private objects and short-lived authorized delivery (for example signed URLs) rather than public buckets.

## Accounting locking

A locked accounting record cannot be modified or deleted through normal CRUD. Unlock is a separate action requiring `accounting.unlock` and is audited.

## Audit

Forum high-risk writes append to the existing `AuditLog`, with structure-scoped before/after/context details stored in `StructureAuditContext`. Audit rows are not updated by the Forum write paths.

Audited actions include role changes, ownership transfer, visibility, event lifecycle, accounting lock/unlock, document lifecycle/version changes, public summary publication and other administrative writes.

## Negative tests

`tests/test_forum_backend_security.py` exercises cross-tenant isolation, Permission Grant Ceiling, owner transfer, finance separation, channel/document/search visibility, accounting lock behavior, claim safety, public-page lifecycle and OpenAPI typing. The full backend test suite is also required before the PR is considered ready.
