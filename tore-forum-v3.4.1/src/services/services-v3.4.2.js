import { createServices as createBaseServices } from './services.js?v=3.4.1';
import { AuthorizationError } from '../core/authorization.js';
import { uid } from '../core/utils.js';

const NON_DELEGABLE = new Set(['structure.admin','ownership.transfer','accounting.unlock']);
const DEFAULT_PUBLIC_POLICIES = Object.freeze({ contact:'Public', publications:'Public' });
const ONBOARDING_VISIBILITY_DEFAULTS = Object.freeze({
  presentation:'Public', events:'Public', members:'Public', albums:'Public', folklore:'Public',
  sponsors:'Public', contact:'Public', publications:'Public', stats:'Privé'
});
const MAX_BRANDING_FILE = 25 * 1024 * 1024;

const unique = values => [...new Set(values || [])];

export function createServices(repo, blobRepo, audit, permissionsOrAuth){
  const auth = permissionsOrAuth?.auth || permissionsOrAuth;
  const services = createBaseServices(repo, blobRepo, audit, permissionsOrAuth);
  const sid = () => repo.state.activeStructureId;
  const uidNow = () => repo.state.currentUserId;
  const structure = structureId => repo.getGlobal('structures', structureId);
  const currentRole = () => auth.role(uidNow(), sid());
  const isOwner = () => structure(sid())?.ownerUserId === uidNow();

  const ensureLegacyVisibilityPolicies = () => {
    for(const st of repo.state.structures || []){
      const existing = new Set(repo.listForStructure('visibilityPolicies', st.id).map(p => p.resourceId));
      for(const [resourceId, level] of Object.entries(DEFAULT_PUBLIC_POLICIES)){
        if(existing.has(resourceId)) continue;
        repo.insertForStructure('visibilityPolicies', st.id, {
          id: uid('vp'), structureId: st.id, resourceType:'section', resourceId, level
        });
      }
    }
  };
  ensureLegacyVisibilityPolicies();

  const assertGrantablePermissions = requestedPermissions => {
    auth.require('roles.manage', uidNow(), sid());
    const requested = unique(requestedPermissions);
    const actorPermissions = new Set(currentRole()?.permissions || []);
    for(const permission of requested){
      if(!actorPermissions.has(permission)){
        throw new AuthorizationError(`Vous ne pouvez pas déléguer une permission que vous ne possédez pas : ${permission}`);
      }
      if(NON_DELEGABLE.has(permission) && !isOwner()){
        throw new AuthorizationError(`Permission non délégable hors Owner : ${permission}`);
      }
    }
    return requested;
  };

  services.roles.assertGrantablePermissions = assertGrantablePermissions;
  services.roles.grantablePermissions = () => {
    const actorPermissions = currentRole()?.permissions || [];
    return actorPermissions.filter(permission => !NON_DELEGABLE.has(permission) || isOwner());
  };

  const baseRoleCreate = services.roles.create.bind(services.roles);
  services.roles.create = data => baseRoleCreate({
    ...data,
    permissions: assertGrantablePermissions(data?.permissions || [])
  });

  const baseRoleUpdate = services.roles.update.bind(services.roles);
  services.roles.update = (id, patch = {}) => {
    const safePatch = {...patch};
    if(Object.prototype.hasOwnProperty.call(safePatch, 'permissions')){
      safePatch.permissions = assertGrantablePermissions(safePatch.permissions);
    }
    return baseRoleUpdate(id, safePatch);
  };

  const baseMemberUpdate = services.members.update.bind(services.members);
  services.members.update = (id, patch = {}) => {
    const currentMember = repo.getForStructure('members', sid(), id);
    const roleChanged = Boolean(patch.roleId && patch.roleId !== currentMember?.roleId);
    if(roleChanged){
      const role = repo.getForStructure('roles', sid(), patch.roleId);
      if(!role) throw new AuthorizationError('Rôle absent ou hors structure');
      if(role.systemRole) throw new AuthorizationError('Un rôle système ne peut être assigné que par son workflow dédié');
      assertGrantablePermissions(role.permissions || []);
    }
    return baseMemberUpdate(id, patch);
  };

  const baseTransferOwnership = services.structure.transferOwnership.bind(services.structure);
  services.structure.transferOwnership = newOwnerUserId => {
    const st = structure(sid());
    if(!st || st.ownerUserId !== uidNow()){
      throw new AuthorizationError('Seul le propriétaire principal actuel peut transférer la propriété');
    }
    return baseTransferOwnership(newOwnerUserId);
  };

  services.stats.optionalList = () => auth.hasPermission('stats.view', uidNow(), sid()) ? services.stats.list() : [];
  services.stats.optionalByEvent = eventId => {
    if(!auth.hasPermission('stats.view', uidNow(), sid())) return null;
    try { return services.stats.byEvent(eventId); } catch { return null; }
  };

  services.posts.isPublishedNow = (post, at = new Date()) => {
    if(!post) return false;
    if(post.status === 'PUBLISHED') return true;
    if(post.status !== 'SCHEDULED') return false;
    const publishAt = new Date(post.publishAt);
    return Number.isFinite(publishAt.getTime()) && publishAt <= at;
  };
  services.posts.canAudienceRead = (post, audience, structureId = sid(), at = new Date()) =>
    services.posts.isPublishedNow(post, at) &&
    auth.canViewLevel(post.visibility || 'Public', null, structureId, {audienceOverride: audience});
  services.posts.isPublic = (post, at = new Date()) =>
    services.posts.isPublishedNow(post, at) && (post.visibility || 'Public') === 'Public';

  const basePostCreate = services.posts.create.bind(services.posts);
  services.posts.create = data => {
    const pendingVisibility = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('tore-v342-post-visibility') : null;
    const next = {...data};
    if(next.visibility == null && pendingVisibility) next.visibility = pendingVisibility;
    const result = basePostCreate(next);
    if(typeof sessionStorage !== 'undefined') sessionStorage.removeItem('tore-v342-post-visibility');
    return result;
  };
  const basePostUpdate = services.posts.update.bind(services.posts);
  services.posts.update = (id, patch) => {
    const pendingVisibility = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('tore-v342-post-visibility') : null;
    const next = {...patch};
    if(next.visibility == null && pendingVisibility) next.visibility = pendingVisibility;
    const result = basePostUpdate(id, next);
    if(typeof sessionStorage !== 'undefined') sessionStorage.removeItem('tore-v342-post-visibility');
    return result;
  };

  services.publicData.posts = (structureId, audience) => {
    if(!services.publicData.canSection(structureId, 'publications', audience)) return [];
    return repo.listForStructure('publicPosts', structureId).filter(post =>
      services.posts.canAudienceRead(post, audience, structureId)
    );
  };

  services.publicData.statsSummary = (structureId, eventId, audience) => {
    if(!services.publicData.canSection(structureId, 'stats', audience)) return null;
    const event = repo.getForStructure('events', structureId, eventId);
    if(!event || !auth.canViewLevel(event.visibility || 'Public', null, structureId, {audienceOverride: audience})) return null;
    const stats = repo.listForStructure('eventStats', structureId).find(x => x.eventId === eventId);
    const summary = stats?.publicSummary;
    if(!summary) return null;
    return {
      publishedAt: summary.publishedAt || null,
      entries: summary.entries,
      scans: summary.scans,
      capacity: summary.capacity,
      occupancy: summary.occupancy,
      entryPoints: structuredClone(summary.entryPoints || [])
    };
  };

  services.publicData.contact = (structureId, audience) => {
    if(!services.publicData.canSection(structureId, 'contact', audience)) return null;
    const st = structure(structureId);
    return st?.contact ? structuredClone(st.contact) : null;
  };

  const checkBrandingFile = file => {
    if(!file || !Number.isFinite(Number(file.size)) || file.size < 0) throw new Error('Fichier invalide');
    if(file.size > MAX_BRANDING_FILE) throw new Error('Fichier trop grand (25 Mo maximum)');
    if(!String(file.type || '').startsWith('image/')) throw new Error('Le branding doit être une image');
  };

  services.structure.setBranding = async (kind, file) => {
    auth.require('structure.manage', uidNow(), sid());
    if(!['logo','banner'].includes(kind)) throw new Error('Type de branding invalide');
    checkBrandingFile(file);
    const st = structure(sid());
    const field = kind === 'logo' ? 'logoBlobKey' : 'bannerBlobKey';
    const previousKey = st?.[field] || null;
    const key = `structure-branding:${sid()}:${kind}:${Date.now()}`;
    await blobRepo.put(key, file);
    services.structure.updateSettings({[field]: key});
    if(previousKey && previousKey !== key){
      try { await blobRepo.remove(previousKey); } catch {}
    }
    audit.log('STRUCTURE_BRANDING_UPDATED', {type:'structure', id:sid()}, {kind, blobKey:previousKey}, {kind, blobKey:key});
    return key;
  };

  services.structure.removeBranding = async kind => {
    auth.require('structure.manage', uidNow(), sid());
    if(!['logo','banner'].includes(kind)) throw new Error('Type de branding invalide');
    const st = structure(sid());
    const field = kind === 'logo' ? 'logoBlobKey' : 'bannerBlobKey';
    const previousKey = st?.[field] || null;
    services.structure.updateSettings({[field]: null});
    if(previousKey){ try { await blobRepo.remove(previousKey); } catch {} }
    audit.log('STRUCTURE_BRANDING_REMOVED', {type:'structure', id:sid()}, {kind, blobKey:previousKey}, {kind, blobKey:null});
    return null;
  };

  const visibilityDefaults = () => ({...ONBOARDING_VISIBILITY_DEFAULTS});
  const baseCreateDraft = services.onboarding.createDraft.bind(services.onboarding);
  services.onboarding.createDraft = mode => {
    const draft = baseCreateDraft(mode);
    draft.visibility = {...visibilityDefaults(), ...(draft.visibility || {})};
    sessionStorage.setItem('tore-onboarding', JSON.stringify(draft));
    return draft;
  };
  const baseGetDraft = services.onboarding.getDraft.bind(services.onboarding);
  services.onboarding.getDraft = () => {
    const draft = baseGetDraft();
    const nextVisibility = {...visibilityDefaults(), ...(draft.visibility || {})};
    if(JSON.stringify(nextVisibility) !== JSON.stringify(draft.visibility || {})){
      draft.visibility = nextVisibility;
      sessionStorage.setItem('tore-onboarding', JSON.stringify(draft));
    }
    return draft;
  };

  const baseReplaceDocument = services.documents.replace.bind(services.documents);
  services.documents.replace = async (id, file) => {
    const current = services.documents.get(id);
    let historicalBlobKey = null;
    if(current.blobKey){
      const oldBlob = await blobRepo.get(current.blobKey);
      if(oldBlob){
        historicalBlobKey = `doc:${id}:v${current.version}`;
        await blobRepo.put(historicalBlobKey, oldBlob);
      }
    }
    const next = await baseReplaceDocument(id, file);
    if(historicalBlobKey){
      const versions = [...(next.versions || [])];
      const idx = versions.findIndex(v => v.version === current.version);
      if(idx >= 0) versions[idx] = {...versions[idx], blobKey: historicalBlobKey};
      repo.updateForStructure('documents', sid(), id, {versions});
      next.versions = versions;
    }
    return next;
  };

  services.documents.previewVersion = async (id, version) => {
    const doc = services.documents.get(id);
    const historical = (doc.versions || []).find(v => v.version === Number(version));
    if(!historical?.blobKey) throw new Error('Binaire de cette version indisponible');
    if(!auth.canReadDocument(uidNow(), doc)) throw new AuthorizationError();
    const blob = await blobRepo.get(historical.blobKey);
    if(!blob) throw new Error('Fichier de version introuvable');
    return URL.createObjectURL(blob);
  };

  services.documents.downloadVersion = async (id, version) => {
    const doc = services.documents.get(id);
    if(!auth.canDownloadDocument(uidNow(), doc)) throw new AuthorizationError();
    const historical = (doc.versions || []).find(v => v.version === Number(version));
    if(!historical?.blobKey) throw new Error('Binaire de cette version indisponible');
    const blob = await blobRepo.get(historical.blobKey);
    if(!blob) throw new Error('Fichier de version introuvable');
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = historical.name || doc.name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if(typeof window !== 'undefined'){
    window.__TORE_V342__ = {services, repo, auth, blobRepo, audit};
  }

  return services;
}

export { NON_DELEGABLE as NON_DELEGABLE_PERMISSIONS };
