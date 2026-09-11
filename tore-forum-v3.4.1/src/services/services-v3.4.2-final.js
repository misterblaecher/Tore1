import { createServices as createHardenedServices } from './services-v3.4.2.js?v=1';
import { AuthorizationError } from '../core/authorization.js';

export function createServices(repo, blobRepo, audit, permissionsOrAuth){
  const services = createHardenedServices(repo, blobRepo, audit, permissionsOrAuth);
  const sid = () => repo.state.activeStructureId;

  const baseInvite = services.members.invite.bind(services.members);
  services.members.invite = data => {
    const role = repo.getForStructure('roles', sid(), data?.roleId);
    if(!role) throw new AuthorizationError('Rôle absent ou hors structure');
    if(role.systemRole) throw new AuthorizationError('Un rôle système ne peut pas être attribué par invitation');
    services.roles.assertGrantablePermissions(role.permissions || []);
    return baseInvite(data);
  };

  services.roles.canManageRole = role => {
    if(!role || role.systemRole) return false;
    try {
      services.roles.assertGrantablePermissions(role.permissions || []);
      return true;
    } catch {
      return false;
    }
  };

  return services;
}
