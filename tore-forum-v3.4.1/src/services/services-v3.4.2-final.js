import { createServices as createHardenedServices } from './services-v3.4.2.js?v=1';
import { AuthorizationError } from '../core/authorization.js';
import { attachForumBackendBridge } from './forum_backend_bridge.js';

const STRICT_NON_DELEGABLE=new Set(['structure.admin','ownership.transfer','accounting.unlock']);

export function createServices(repo, blobRepo, audit, permissionsOrAuth){
  const services = createHardenedServices(repo, blobRepo, audit, permissionsOrAuth);
  const sid = () => repo.state.activeStructureId;

  const assertCustomRoleDelegable = permissions => {
    for(const permission of permissions || []){
      if(STRICT_NON_DELEGABLE.has(permission)){
        throw new AuthorizationError(`Permission système non délégable : ${permission}`);
      }
    }
    return services.roles.assertGrantablePermissions(permissions || []);
  };

  const inheritedCreate=services.roles.create.bind(services.roles);
  services.roles.create=data=>inheritedCreate({...data,permissions:assertCustomRoleDelegable(data?.permissions||[])});
  const inheritedUpdate=services.roles.update.bind(services.roles);
  services.roles.update=(id,patch={})=>{
    const next={...patch};
    if(Object.prototype.hasOwnProperty.call(next,'permissions'))next.permissions=assertCustomRoleDelegable(next.permissions);
    return inheritedUpdate(id,next);
  };

  const inheritedMemberUpdate=services.members.update.bind(services.members);
  services.members.update=(id,patch={})=>{
    if(patch.roleId){
      const role=repo.getForStructure('roles',sid(),patch.roleId);
      if(!role)throw new AuthorizationError('Rôle absent ou hors structure');
      if(role.systemRole)throw new AuthorizationError('Un rôle système ne peut être assigné que par son workflow dédié');
      assertCustomRoleDelegable(role.permissions||[]);
    }
    return inheritedMemberUpdate(id,patch);
  };

  const baseInvite = services.members.invite.bind(services.members);
  services.members.invite = data => {
    const role = repo.getForStructure('roles', sid(), data?.roleId);
    if(!role) throw new AuthorizationError('Rôle absent ou hors structure');
    if(role.systemRole) throw new AuthorizationError('Un rôle système ne peut pas être attribué par invitation');
    assertCustomRoleDelegable(role.permissions || []);
    return baseInvite(data);
  };

  services.roles.canManageRole = role => {
    if(!role || role.systemRole) return false;
    try { assertCustomRoleDelegable(role.permissions || []); return true; }
    catch { return false; }
  };

  const inheritedDocumentReplace=services.documents.replace.bind(services.documents);
  services.documents.replace=async(id,file)=>{
    const before=services.documents.get(id);
    const previousVersion=before.version;
    const previousBlobKey=before.blobKey;
    const previousBlob=previousBlobKey?await blobRepo.get(previousBlobKey):null;
    const next=await inheritedDocumentReplace(id,file);
    if(previousBlob){
      const historicalKey=`doc:${id}:v${previousVersion}`;
      const versions=[...(next.versions||[])];
      const index=versions.findIndex(v=>Number(v.version)===Number(previousVersion));
      if(index>=0)versions[index]={...versions[index],blobKey:historicalKey};
      repo.updateForStructure('documents',sid(),id,{versions});
      next.versions=versions;
    }
    return next;
  };

  const baseDocumentRemove = services.documents.remove.bind(services.documents);
  services.documents.remove = async id => {
    const doc = services.documents.get(id);
    const historicalKeys = (doc.versions || []).map(v=>v.blobKey).filter(Boolean);
    const result = await baseDocumentRemove(id);
    for(const key of historicalKeys){try{await blobRepo.remove(key)}catch{}}
    return result;
  };

  services.roles.strictNonDelegablePermissions=[...STRICT_NON_DELEGABLE];
  attachForumBackendBridge(repo,services);
  return services;
}
