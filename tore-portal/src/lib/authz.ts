import { getSession } from './auth'

export const ORGA_ROLES = new Set(['manager', 'bartender'])

export function hasOrgaHubAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return ORGA_ROLES.has(role)
}

export function hasManagerAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return role === 'manager'
}
