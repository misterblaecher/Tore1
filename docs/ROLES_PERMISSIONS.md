# TORÈ — Roles & Permissions

## Identity types
- App user
- Partner/staff
- Global admin

## Membership roles (examples)
- OrganizationMembership: OWNER | MANAGER | MEMBER
- PartnerMembership: OWNER | MANAGER | BARTENDER
- CommitteeMembership: OWNER | ADMIN | MOD | MEMBER

## Capabilities (preferred for clients)
Clients should rely on capabilities like:
- `can.event.manage`
- `can.orders.view`
- `can.orders.manage`
- `can.wallet.admin`
- `can.entry.scan`
- `can.broadcast.send`

Backend remains the source of truth for:
- event-state gating
- module gating
