import { createForumApiRepository, forumBackendEnabled } from './forum_api_repository.js';

const visibilityFromApi = value => ({
  PUBLIC:'Public', TORE:'Utilisateurs TORÈ', MEMBERS:'Membres', STAFF:'Staff',
  BUREAU:'Bureau', TREASURY:'Trésorerie', PRIVATE:'Privé'
})[String(value||'PRIVATE').toUpperCase()] || 'Privé';
const visibilityToApi = value => ({
  'Public':'PUBLIC','Utilisateurs TORÈ':'TORE','Membres':'MEMBERS','Staff':'STAFF',
  'Bureau':'BUREAU','Trésorerie':'TREASURY','Privé':'PRIVATE'
})[value] || 'PRIVATE';
// Server PRIVATE means "internal to the structure" for event list responses.
// The local repository still applies events.view, so hydrate it as Membres
// instead of Privé (which is reserved locally for structure.admin only).
const eventVisibilityFromApi = value => String(value||'PRIVATE').toUpperCase()==='PUBLIC'?'Public':'Membres';
const eventVisibilityToApi = value => value==='Public'?'PUBLIC':'PRIVATE';
const dateOnly = value => value ? String(value).slice(0,10) : null;
const safeSlug = value => String(value||'event').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'') || 'event';

function emit(name,detail){
  if(typeof window!=='undefined' && typeof window.dispatchEvent==='function' && typeof CustomEvent!=='undefined'){
    window.dispatchEvent(new CustomEvent(name,{detail}));
  }
}

function replaceTenantRows(repo,entity,structureId,rows){
  repo.state[entity]=(repo.state[entity]||[]).filter(row=>row.structureId!==structureId).concat(rows);
}

function ensureUser(repo,{id,name,avatarUrl=null}){
  if(!id)return;
  const users=repo.state.users||=[];
  const current=users.find(user=>user.id===id);
  if(current){Object.assign(current,{name:name||current.name,avatarUrl:avatarUrl??current.avatarUrl});return}
  users.push({id,name:name||'Membre TORÈ',email:'',initials:String(name||'T').split(/\s+/).map(x=>x[0]).join('').slice(0,2).toUpperCase(),avatarUrl});
}

export function mapServerSnapshot(repo,{context,roles,members,visibility,events}){
  const serverStructure=context.structure;
  let localStructure=(repo.state.structures||[]).find(item=>item.slug===serverStructure.slug);
  if(!localStructure){
    localStructure={id:`server-structure-${serverStructure.id}`,slug:serverStructure.slug,name:serverStructure.name,type:serverStructure.type||'OTHER',status:serverStructure.status||'SETUP',ownerUserId:serverStructure.owner_user_id||null,description:serverStructure.description||'',shortDescription:serverStructure.description||'',logo:'assets/app_icon.png',banner:null,accent:serverStructure.primary_color||'#f6a800',secondaryAccent:'#20252a',contact:{email:'',phone:'',address:'',instagram:'',website:''},sponsors:[],seo:{index:false,title:`${serverStructure.name} — TORÈ Forum`,description:serverStructure.description||''},toreIntegration:{structureKey:`SERVER-${serverStructure.id}`,appSyncEnabled:true}};
    repo.state.structures.push(localStructure);
  }
  Object.assign(localStructure,{
    backendId:serverStructure.id,
    slug:serverStructure.slug,
    name:serverStructure.name,
    type:serverStructure.type||localStructure.type,
    status:serverStructure.status||localStructure.status,
    ownerUserId:serverStructure.owner_user_id||localStructure.ownerUserId,
    description:serverStructure.description??localStructure.description,
    accent:serverStructure.primary_color||localStructure.accent,
  });
  const sid=localStructure.id;
  repo.state.activeStructureId=sid;

  const roleRows=(roles||[]).map(role=>({
    id:`server-role-${role.id}`,backendId:role.id,structureId:sid,name:role.name,
    systemRole:!!role.system_role,audienceLevel:visibilityFromApi(role.audience_level),permissions:[...(role.permissions||[])]
  }));
  const roleIdByBackend=new Map(roleRows.map(role=>[role.backendId,role.id]));
  replaceTenantRows(repo,'roles',sid,roleRows);

  const memberRows=(members||[]).map(member=>{
    ensureUser(repo,{id:member.userId,name:member.displayName,avatarUrl:member.avatarUrl});
    return {
      id:`server-member-${member.id}`,backendId:member.id,structureId:sid,userId:member.userId,
      roleId:roleIdByBackend.get(member.role?.id)||null,title:member.title||member.role?.name||'Membre',
      team:member.team||'',startDate:dateOnly(member.mandateStart),endDate:dateOnly(member.mandateEnd),
      status:member.status==='LEFT'?'ALUMNI':member.status,publicProfile:!!member.publicProfile,
      publicAlumni:false,responsibilities:[],notes:''
    };
  });
  replaceTenantRows(repo,'members',sid,memberRows);

  const actor=memberRows.find(member=>member.backendId===context.membership?.id) || memberRows.find(member=>member.userId===context.membership?.userId);
  if(actor) repo.state.currentUserId=actor.userId;
  if(context.membership?.userId) ensureUser(repo,{id:context.membership.userId,name:context.membership.displayName,avatarUrl:context.membership.avatarUrl});

  const visibilityRows=(visibility||[]).map((policy,index)=>({
    id:`server-vis-${index}-${policy.resourceType}-${policy.resourceId}`,structureId:sid,
    resourceType:policy.resourceType,resourceId:policy.resourceId,level:visibilityFromApi(policy.level),backend:true
  }));
  replaceTenantRows(repo,'visibilityPolicies',sid,visibilityRows);

  const eventRows=(events||[]).map(event=>({
    id:`server-event-${event.id}`,backendId:event.id,structureId:sid,slug:safeSlug(event.name),title:event.name,
    description:event.description||'',cover:null,organizer:serverStructure.name,coOrganizers:[],place:event.venue||event.city||'',
    barId:null,startAt:event.startsAt,endAt:event.endsAt,capacity:event.capacity||0,price:Number(event.entryPriceCents||0)/100,
    conditions:'',visibility:eventVisibilityFromApi(event.visibility),modules:[],status:event.lifecycle||event.publicationStatus||'DRAFT',
    appSyncStatus:event.lifecycle||event.publicationStatus||'DRAFT',staffMemberIds:[],albumId:null,recap:null,publicSummary:false,documents:[]
  }));
  replaceTenantRows(repo,'events',sid,eventRows);
  repo.save();
  return {structureId:sid,slug:localStructure.slug};
}

function reportFailure(error,hydrate){
  console.error('[TORÈ Forum backend]',error);
  emit('tore:forum-backend-error',{message:error?.message||String(error)});
  if(hydrate) queueMicrotask(()=>hydrate().catch(()=>{}));
}

export function attachForumBackendBridge(repo,services,{api=createForumApiRepository(),enabled=forumBackendEnabled()}={}){
  if(!enabled){services.backend={enabled:false,ready:Promise.resolve(null),api:null,hydrate:async()=>null};return services.backend}

  let activeSlug=null;
  let hydrating=null;
  const hydrate=async()=>{
    if(hydrating)return hydrating;
    hydrating=(async()=>{
      const owned=await api.meStructures();
      const local=repo.state.structures?.find(item=>item.id===repo.state.activeStructureId);
      const selected=(owned.items||[]).find(item=>item.slug===local?.slug)||(owned.items||[])[0];
      if(!selected)throw new Error('Aucune structure TORÈ accessible avec cette session.');
      activeSlug=selected.slug;
      const [context,roles,members,visibility,events]=await Promise.all([
        api.context(activeSlug),api.roles(activeSlug),api.members(activeSlug),api.visibility(activeSlug),api.events(activeSlug)
      ]);
      const snapshot=mapServerSnapshot(repo,{context,roles,members:members.items||[],visibility:visibility.items||[],events:events.items||[]});
      emit('tore:forum-backend-hydrated',snapshot);
      return snapshot;
    })();
    try{return await hydrating}finally{hydrating=null}
  };

  const afterReady=task=>{
    Promise.resolve(services.backend.ready).then(task).catch(error=>reportFailure(error,hydrate));
  };
  const serverId=(entity,id)=>repo.getForStructure(entity,repo.state.activeStructureId,id)?.backendId;
  const currentSlug=()=>activeSlug||repo.state.structures?.find(item=>item.id===repo.state.activeStructureId)?.slug;

  const baseStructureUpdate=services.structure.updateSettings.bind(services.structure);
  services.structure.updateSettings=patch=>{
    const result=baseStructureUpdate(patch);
    afterReady(async()=>{
      const body={};
      if(patch.name!==undefined)body.name=patch.name;
      if(patch.description!==undefined)body.description=patch.description;
      if(patch.type!==undefined)body.org_type=patch.type;
      if(patch.accent!==undefined)body.primary_color=patch.accent;
      if(patch.contact?.email!==undefined)body.contact_email=patch.contact.email;
      if(patch.contact?.phone!==undefined)body.contact_phone=patch.contact.phone;
      if(Object.keys(body).length)await api.updateStructure(currentSlug(),body);
    });
    return result;
  };

  const baseRoleCreate=services.roles.create.bind(services.roles);
  services.roles.create=data=>{
    const local=baseRoleCreate(data);
    afterReady(async()=>{const remote=await api.createRole(currentSlug(),{name:data.name,audience_level:visibilityToApi(data.audienceLevel||'Membres'),permissions:data.permissions||[]});repo.updateForStructure('roles',repo.state.activeStructureId,local.id,{backendId:remote.id})});
    return local;
  };
  const baseRoleUpdate=services.roles.update.bind(services.roles);
  services.roles.update=(id,patch)=>{
    const local=baseRoleUpdate(id,patch);
    afterReady(async()=>{const rid=serverId('roles',id);if(!rid)return;const body={};if(patch.name!==undefined)body.name=patch.name;if(patch.audienceLevel!==undefined)body.audience_level=visibilityToApi(patch.audienceLevel);if(patch.permissions!==undefined)body.permissions=patch.permissions;await api.updateRole(currentSlug(),rid,body)});
    return local;
  };

  const baseMemberUpdate=services.members.update.bind(services.members);
  services.members.update=(id,patch)=>{
    const local=baseMemberUpdate(id,patch);
    afterReady(async()=>{
      const mid=serverId('members',id);if(!mid)return;const body={};
      if(patch.roleId!==undefined){const rid=serverId('roles',patch.roleId);if(rid)body.role_id=rid}
      if(patch.status!==undefined)body.status=patch.status==='ALUMNI'?'FORMER':patch.status;
      if(patch.title!==undefined)body.title=patch.title;if(patch.team!==undefined)body.team=patch.team;
      if(patch.publicProfile!==undefined)body.public_profile=patch.publicProfile;
      if(patch.startDate!==undefined)body.mandate_start=patch.startDate||null;if(patch.endDate!==undefined)body.mandate_end=patch.endDate||null;
      if(Object.keys(body).length)await api.updateMember(currentSlug(),mid,body);
    });
    return local;
  };

  const baseVisibilitySet=services.visibility.set.bind(services.visibility);
  services.visibility.set=(resourceId,level)=>{
    const local=baseVisibilitySet(resourceId,level);
    afterReady(()=>api.setVisibility(currentSlug(),{resource_type:resourceId,resource_id:'__section__',level:visibilityToApi(level)}));
    return local;
  };

  const baseEventCreate=services.events.create.bind(services.events);
  services.events.create=data=>{
    const local=baseEventCreate(data);
    afterReady(async()=>{const remote=await api.createEvent(currentSlug(),{name:data.title,starts_at:data.startAt,ends_at:data.endAt,venue:data.place||null,description:data.description||null,visibility:eventVisibilityToApi(data.visibility),capacity:Number(data.capacity||0)||null,entry_price_cents:Math.round(Number(data.price||0)*100)});repo.updateForStructure('events',repo.state.activeStructureId,local.id,{backendId:remote.id})});
    return local;
  };
  const baseEventUpdate=services.events.update.bind(services.events);
  services.events.update=(id,patch)=>{
    const local=baseEventUpdate(id,patch);
    afterReady(async()=>{const eid=serverId('events',id);if(!eid)return;const body={};if(patch.title!==undefined)body.name=patch.title;if(patch.startAt!==undefined)body.starts_at=patch.startAt;if(patch.endAt!==undefined)body.ends_at=patch.endAt;if(patch.place!==undefined)body.venue=patch.place;if(patch.description!==undefined)body.description=patch.description;if(patch.visibility!==undefined)body.visibility=eventVisibilityToApi(patch.visibility);if(patch.capacity!==undefined)body.capacity=Number(patch.capacity||0);if(patch.price!==undefined)body.entry_price_cents=Math.round(Number(patch.price||0)*100);if(Object.keys(body).length)await api.updateEvent(currentSlug(),eid,body)});
    return local;
  };
  const baseTransition=services.events.transition.bind(services.events);
  services.events.transition=(id,target)=>{
    const local=baseTransition(id,target);
    afterReady(async()=>{const eid=serverId('events',id);if(eid)await api.transitionEvent(currentSlug(),eid,target)});
    return local;
  };

  if(services.publicPages){
    const basePublish=services.publicPages.publish.bind(services.publicPages);
    services.publicPages.publish=()=>{const local=basePublish();afterReady(()=>api.setPublicPage(currentSlug(),{status:'PUBLISHED'}));return local};
    const baseHide=services.publicPages.hide.bind(services.publicPages);
    services.publicPages.hide=()=>{const local=baseHide();afterReady(()=>api.setPublicPage(currentSlug(),{status:'HIDDEN'}));return local};
  }

  services.backend={enabled:true,api,hydrate,ready:null};
  services.backend.ready=hydrate();
  return services.backend;
}

export { visibilityFromApi, visibilityToApi, eventVisibilityFromApi };
