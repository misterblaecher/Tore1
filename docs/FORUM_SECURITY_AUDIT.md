# Forum security audit

This audit is enforced by the Playwright journeys in `tore_site/e2e/forum-security.spec.ts`
and focused backend tests. A passing row means both the expected success path and the
relevant denial path are asserted.

| Area | Security invariant | Automated evidence |
| --- | --- | --- |
| IDOR | A resource id cannot bypass its structure scope; mismatches return 404. | `test_secure_storage_uploads.py`, `test_forum_structure_mvp.py` |
| Cross-structure | Membership, roles, events, documents, files, and search remain tenant-scoped. | `test_forum_search_security.py`, `test_structure_capability_rbac.py`, Playwright 06/17 |
| Permissions | Sensitive actions require explicit capabilities, not UI visibility. | `test_structure_capability_rbac.py`, Playwright 05/12/13/19/20 |
| Channel ACL | Feed, direct post access, and global search apply the same ACL. | `test_forum_channel_acl_current.py`, Playwright 06/17 |
| Uploads | Content is signature-checked, private by default, and publication is confirmed. | `test_secure_storage_uploads.py`, Playwright 10/23 |
| Ownership | Transfers require the target; recovery requires a configured secondary owner. | `test_forum_ownership_security.py`, Playwright 14/15 |
| Claims | Claim review and mutation remain restricted to the review authority. | `test_structure_claim_workflow.py` |
| Finance | Members are denied; treasurers get finance capabilities without ownership. | `test_forum_accounting_access.py`, Playwright 12/13 |
| Exports | CSV export requires `finance.export`. | `test_forum_accounting_access.py`, Playwright 19/20 |
| Search | Queries are structure-scoped and ACL-filtered before result serialization. | `test_forum_search_security.py`, Playwright 06/17 |

## Finding fixed

The page-content branch of global search referenced the previous discussion-loop variable
instead of `StructurePage.content`. This could produce a server error when no discussion
matched and made page indexing dependent on unrelated rows. The query now uses the scoped
page column directly, with a regression test covering content search and tenant isolation.
