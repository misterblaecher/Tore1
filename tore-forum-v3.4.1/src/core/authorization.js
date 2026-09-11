export const VISIBILITY_LEVELS=['Public','Utilisateurs TORÈ','Membres','Staff','Bureau','Trésorerie','Privé'];
const rank=new Map(VISIBILITY_LEVELS.map((x,i)=>[x,i]));
const tenantEntities=new Set(['roles','members','invitations','events','channels','messages','threads','folders','documents','albums','media','folklorePages','planningItems','accountingEntries','eventStats','visibilityPolicies','publicPosts','auditLogs','notifications','archives','publicPages','structureClaims']);

export class AuthorizationError extends Error{
  constructor(message='Accès refusé'){super(message);this.name='AuthorizationError';this.code='DENIED'}
}

export class AuthorizationService{
  constructor(repo){this.repo=repo}
  user(userId=this.repo.state.currentUserId){return this.repo.state.users.find(u=>u.id===userId)||null}
  structure(structureId=this.repo.state.activeStructureId){return this.repo.state.structures.find(s=>s.id===structureId)||null}
  membership(userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId){return (this.repo.state.members||[]).find(m=>m.userId===userId&&m.structureId===structureId&&m.status==='ACTIVE')||null}
  role(userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId){const m=this.membership(userId,structureId);return (this.repo.state.roles||[]).find(r=>r.id===m?.roleId&&r.structureId===structureId)||null}
  context(userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId){const user=this.user(userId),member=this.membership(userId,structureId),role=this.role(userId,structureId);return {user,member,role,structureId,permissions:new Set(role?.permissions||[]),audienceLevel:role?.audienceLevel||(member?'Membres':user?'Utilisateurs TORÈ':'Public'),isAdmin:!!role?.permissions?.includes('structure.admin')}}
  hasPermission(permission,userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId){return this.context(userId,structureId).permissions.has(permission)}
  require(permission,userId,structureId){if(!this.hasPermission(permission,userId,structureId))throw new AuthorizationError(`Permission requise : ${permission}`);return true}
  canAccessStructure(userId,structureId){return !!this.structure(structureId) && (!!this.membership(userId,structureId)||this.structure(structureId).status==='ACTIVE')}
  canAccessAdmin(userId,structureId){return !!this.membership(userId,structureId)}
  canViewLevel(level,userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId,{audienceOverride=null}={}){
    const target=rank.get(level)??rank.get('Privé');
    if(audienceOverride){const overrideRank=rank.get(audienceOverride)??0;return overrideRank>=target}
    if(level==='Public')return true;
    const ctx=this.context(userId,structureId);
    if(level==='Utilisateurs TORÈ')return !!ctx.user;
    if(!ctx.member)return false;
    if(level==='Privé')return ctx.isAdmin;
    return (rank.get(ctx.audienceLevel)??2)>=target;
  }
  canPreviewVisibility(userId,structureId,level){if(!this.hasPermission('visibility.manage',userId,structureId))return false;const ctx=this.context(userId,structureId);return (rank.get(ctx.audienceLevel)??0)>=(rank.get(level)??99)}
  resolvePublicAudience({userId=this.repo.state.currentUserId,structureId=this.repo.state.activeStructureId,preview=null}={}){
    if(preview){const map={public:'Public',tore:'Utilisateurs TORÈ',member:'Membres',staff:'Staff',bureau:'Bureau',tresorerie:'Trésorerie',private:'Privé'};const level=map[String(preview).toLowerCase()];if(level&&this.canPreviewVisibility(userId,structureId,level))return level}
    const ctx=this.context(userId,structureId);return ctx.user?(ctx.member?ctx.audienceLevel:'Utilisateurs TORÈ'):'Public';
  }
  belongs(resource,structureId){return !!resource&&(!('structureId' in resource)||resource.structureId===structureId)}
  canReadEvent(userId,event){return !!event&&this.hasPermission('events.view',userId,event.structureId)&&this.canViewLevel(event.visibility||'Membres',userId,event.structureId)}
  canManageEvent(userId,eventOrStructure){const sid=typeof eventOrStructure==='string'?eventOrStructure:eventOrStructure?.structureId;return !!sid&&this.hasPermission('events.manage',userId,sid)}
  canReadChannel(userId,channel){return !!channel&&this.canViewLevel(channel.visibility||'Membres',userId,channel.structureId)}
  canPostChannel(userId,channel){return this.canReadChannel(userId,channel)&&this.hasPermission('channels.post',userId,channel.structureId)}
  canManageChannel(userId,structureId){return this.hasPermission('channels.manage',userId,structureId)}
  canReadDocument(userId,doc){return !!doc&&this.hasPermission('documents.view',userId,doc.structureId)&&this.canViewLevel(doc.visibility||'Membres',userId,doc.structureId)}
  canDownloadDocument(userId,doc){return this.canReadDocument(userId,doc)&&this.hasPermission('documents.download',userId,doc.structureId)}
  canReadAlbum(userId,album){return !!album&&this.hasPermission('albums.view',userId,album.structureId)&&this.canViewLevel(album.visibility||'Membres',userId,album.structureId)}
  canReadMedia(userId,media){if(!media)return false;const a=this.repo.getForStructure('albums',media.structureId,media.albumId);return this.canReadAlbum(userId,a)}
  canReadFolklore(userId,page){return !!page&&this.hasPermission('folklore.view',userId,page.structureId)&&this.canViewLevel(page.visibility||'Membres',userId,page.structureId)}
  canReadStats(userId,stats){return !!stats&&this.hasPermission('stats.view',userId,stats.structureId)}
  canReadAccounting(userId,structureId){return this.hasPermission('accounting.view',userId,structureId)}
  canManageMembers(userId,structureId){return this.hasPermission('members.manage',userId,structureId)}
  canManageRoles(userId,structureId){return this.hasPermission('roles.manage',userId,structureId)}
  canReadResource(userId,resource,type){
    if(!resource)return false;const sid=resource.structureId||this.repo.state.activeStructureId;
    if(type&&tenantEntities.has(type)&&resource.structureId!==sid)return false;
    if(type==='events')return this.canReadEvent(userId,resource);
    if(type==='channels')return this.canReadChannel(userId,resource);
    if(type==='messages'){const ch=this.repo.getForStructure('channels',sid,resource.channelId);return this.canReadChannel(userId,ch)}
    if(type==='documents')return this.canReadDocument(userId,resource);
    if(type==='albums')return this.canReadAlbum(userId,resource);
    if(type==='media')return this.canReadMedia(userId,resource);
    if(type==='folklorePages')return this.canReadFolklore(userId,resource);
    if(type==='eventStats')return this.canReadStats(userId,resource);
    if(type==='accountingEntries')return this.canReadAccounting(userId,sid);
    if(type==='auditLogs')return this.hasPermission('audit.view',userId,sid);
    if(type==='invitations')return this.canManageMembers(userId,sid);
    if(type==='roles')return !!this.membership(userId,sid);
    if(type==='planningItems')return this.hasPermission('planning.view',userId,sid);
    if(type==='folders')return this.hasPermission('documents.view',userId,sid);
    if(type==='members')return this.hasPermission('members.view',userId,sid);
    if(type==='publicPosts')return !!this.membership(userId,sid);
    if(type==='notifications')return resource.userId===userId;
    if(type==='publicPages')return this.hasPermission('structure.manage',userId,sid)||this.hasPermission('visibility.manage',userId,sid);
    if(type==='structureClaims')return this.hasPermission('structure.admin',userId,sid);
    return !resource.structureId||!!this.membership(userId,sid);
  }
  canWriteResource(userId,resource,type){const sid=resource?.structureId||this.repo.state.activeStructureId;if(type==='events')return this.hasPermission('events.manage',userId,sid);if(type==='documents')return this.hasPermission('documents.manage',userId,sid);if(type==='albums')return this.hasPermission('albums.manage',userId,sid);if(type==='folklorePages')return this.hasPermission('folklore.manage',userId,sid);if(type==='planningItems')return this.hasPermission('planning.manage',userId,sid);if(type==='accountingEntries')return this.hasPermission('accounting.manage',userId,sid);return this.hasPermission('structure.manage',userId,sid)}
  canReadPublicPage(resource,visibility,audience='Public'){return !!resource&&this.canViewLevel(visibility,null,resource.structureId,{audienceOverride:audience})}
  routePermission(page){return ({members:'members.view',documents:'documents.view',albums:'albums.view',folklore:'folklore.view',planning:'planning.view',stats:'stats.view',accounting:'accounting.view',visibility:'visibility.manage',audit:'audit.view',publications:'publications.manage',settings:'structure.manage'})[page]||null}
}

const operationalStatsDto=x=>({id:x.id,structureId:x.structureId,eventId:x.eventId,entries:x.entries,scans:x.scans,capacity:x.capacity,hourly:structuredClone(x.hourly||[]),entryPoints:structuredClone(x.entryPoints||[]),publicSummary:structuredClone(x.publicSummary||null)});
export class AuthorizedRepository{
  constructor(repo,auth){this.repo=repo;this.auth=auth}
  get state(){return this.repo.state}
  list(entity,structureId=this.repo.state.activeStructureId){const rows=this.repo.listForStructure(entity,structureId).filter(x=>this.auth.canReadResource(this.repo.state.currentUserId,x,entity));if(entity==='eventStats'&&!this.auth.canReadAccounting(this.repo.state.currentUserId,structureId))return rows.map(operationalStatsDto);return rows}
  get(entity,id,structureId=this.repo.state.activeStructureId){
    if(entity==='users'||entity==='structures')return this.repo.get(entity,id);
    const x=this.repo.getForStructure(entity,structureId,id);if(!this.auth.canReadResource(this.repo.state.currentUserId,x,entity))return null;if(entity==='eventStats'&&!this.auth.canReadAccounting(this.repo.state.currentUserId,structureId))return operationalStatsDto(x);return x;
  }
}
