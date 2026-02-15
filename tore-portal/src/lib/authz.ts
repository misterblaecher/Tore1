import { getSession } from './auth'

export const ORGA_ROLES = new Set(['manager', 'bartender'])
export const ORGA_MANAGER_ROLES = new Set(['manager', 'owner'])

export function hasOrgaHubAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return ORGA_ROLES.has(role)
}

export function hasManagerAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return ORGA_MANAGER_ROLES.has(role)
}

export function hasOrgaManagerAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return ORGA_MANAGER_ROLES.has(role)
}


export const BAR_MODE_ROLES = new Set(['bartender', 'manager', 'owner'])

export function hasBarModeAccess(): boolean {
  const role = (getSession()?.role || '').toLowerCase()
  return BAR_MODE_ROLES.has(role)
}
