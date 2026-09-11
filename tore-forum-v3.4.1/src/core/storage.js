import { seed } from '../data/seed.js';
import { clone, uid } from './utils.js';
import { assertNoImmutable, IntegrityError } from './integrity.js';

const KEY='tore-forum-v3-state';
const TENANT=new Set(['roles','members','invitations','events','channels','messages','threads','folders','documents','albums','media','folklorePages','planningItems','accountingEntries','eventStats','visibilityPolicies','publicPosts','auditLogs','notifications','archives','publicPages','structureClaims']);
const OWNER_CRITICAL=['structure.admin','structure.manage','members.view','members.manage','roles.manage','ownership.transfer','events.view','events.manage','events.publish','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','folklore.manage','planning.view','planning.manage','stats.view','accounting.view','accounting.manage','accounting.unlock','visibility.manage','audit.view','channels.post','channels.manage','publications.manage','archives.view'];
const roleDefaults={
 Owner:{audienceLevel:'Privé',systemRole:true,add:OWNER_CRITICAL},
 Bureau:{audienceLevel:'Bureau',systemRole:false,add:['members.view','members.manage','events.view','events.manage','events.publish','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','folklore.manage','planning.view','planning.manage','stats.view','accounting.view','visibility.manage','channels.post','channels.manage','publications.manage','archives.view']},
 'Trésorerie':{audienceLevel:'Trésorerie',systemRole:false,add:['members.view','events.view','events.manage','documents.view','documents.download','documents.manage','albums.view','folklore.view','planning.view','planning.manage','stats.view','accounting.view','accounting.manage','channels.post','archives.view']},
 Staff:{audienceLevel:'Staff',systemRole:false,add:['members.view','events.view','events.manage','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','planning.view','planning.manage','stats.view','channels.post','archives.view']},
 Membre:{audienceLevel:'Membres',systemRole:false,add:['members.view','events.view','documents.view','documents.download','albums.view','folklore.view','planning.view','channels.post','archives.view']}
};

export class LocalRepository{
  constructor(){this.state=this.load()}
  load(){try{const raw=localStorage.getItem(KEY);if(!raw)return clone(seed);return this.migrate(JSON.parse(raw))}catch(e){console.warn('State reset',e);return clone(seed)}}
  migrate(s){
    if(!s||typeof s!=='object')return clone(seed);if((s.version||0)>seed.version)return clone(seed);
    const out=s;
    for(const [k,v] of Object.entries(seed)){if(!(k in out))out[k]=clone(v)}
    out.roles=(out.roles||[]).map(r=>{const d=roleDefaults[r.name]||{audienceLevel:r.audienceLevel||'Membres',systemRole:false,add:[]};return {...r,systemRole:r.systemRole??d.systemRole,audienceLevel:r.audienceLevel||d.audienceLevel,permissions:[...new Set([...(r.permissions||[]),...d.add])]} });
    out.members=(out.members||[]).map(m=>({...m,publicProfile:m.publicProfile??['m1','m2','m4','m5'].includes(m.id),publicAlumni:m.publicAlumni??false,notes:m.notes||''}));
    out.documents=(out.documents||[]).map(d=>({...d,description:d.description||'',versions:d.versions||[]}));
    out.media=(out.media||[]).map(m=>({...m,visibility:m.visibility||null}));
    out.publicPosts=(out.publicPosts||[]).map(p=>({...p,visibility:p.visibility||'Public'}));
    out.structureClaims=out.structureClaims||[];
    out.publicPages=out.publicPages||[];
    for(const st of out.structures||[]){
      let page=out.publicPages.find(p=>p.structureId===st.id);
      if(!page){page={id:uid('page'),structureId:st.id,status:st.status==='ACTIVE'?'PUBLISHED':'DRAFT',publishedAt:st.status==='ACTIVE'?new Date().toISOString():null,hiddenAt:null,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};out.publicPages.push(page)}
      let ownerRole=out.roles.find(r=>r.structureId===st.id&&(r.systemRole||r.name==='Owner'));
      if(!ownerRole&&st.ownerUserId){ownerRole={id:uid('r'),structureId:st.id,name:'Owner',systemRole:true,audienceLevel:'Privé',permissions:[...OWNER_CRITICAL]};out.roles.push(ownerRole)}
      if(ownerRole){
        ownerRole.systemRole=true;ownerRole.name='Owner';ownerRole.audienceLevel='Privé';ownerRole.permissions=[...new Set([...(ownerRole.permissions||[]),...OWNER_CRITICAL])];
        let fallback=out.roles.find(r=>r.structureId===st.id&&!r.systemRole&&r.name==='Bureau')||out.roles.find(r=>r.structureId===st.id&&!r.systemRole);
        if(!fallback){fallback={id:uid('r'),structureId:st.id,name:'Bureau',systemRole:false,audienceLevel:'Bureau',permissions:[...roleDefaults.Bureau.add]};out.roles.push(fallback)}
        let ownerMember=out.members.find(m=>m.structureId===st.id&&m.userId===st.ownerUserId);
        if(!ownerMember&&out.users?.some(u=>u.id===st.ownerUserId)){ownerMember={id:uid('m'),structureId:st.id,userId:st.ownerUserId,roleId:ownerRole.id,title:'Owner',team:'Bureau',startDate:new Date().toISOString().slice(0,10),endDate:null,status:'ACTIVE',responsibilities:['Administration'],publicProfile:false,publicAlumni:false,notes:''};out.members.push(ownerMember)}
        if(ownerMember){ownerMember.roleId=ownerRole.id;ownerMember.status='ACTIVE';ownerMember.endDate=null}
        for(const m of out.members.filter(m=>m.structureId===st.id&&m.roleId===ownerRole.id&&m.userId!==st.ownerUserId&&m.status==='ACTIVE'))m.roleId=fallback.id;
      }
    }
    out.version=seed.version;return out;
  }
  save(){localStorage.setItem(KEY,JSON.stringify(this.state));return this.state}
  reset(){this.state=clone(seed);this.save()}
  list(entity,structureId=this.state.activeStructureId){return this.listForStructure(entity,structureId)}
  listForStructure(entity,structureId=this.state.activeStructureId){const arr=this.state[entity]||[];if(!TENANT.has(entity))return arr.slice();return arr.filter(x=>x.structureId===structureId)}
  get(entity,id){const x=(this.state[entity]||[]).find(v=>v.id===id)||null;if(!x)return null;if(TENANT.has(entity)&&x.structureId!==this.state.activeStructureId)return null;return x}
  getGlobal(entity,id){if(TENANT.has(entity))throw new IntegrityError(`Accès global interdit pour l’entité tenant-scoped : ${entity}`,'TENANT_SCOPE');return (this.state[entity]||[]).find(x=>x.id===id)||null}
  getForStructure(entity,structureId,id){const x=(this.state[entity]||[]).find(v=>v.id===id)||null;if(!x)return null;if(TENANT.has(entity)&&x.structureId!==structureId)return null;return x}
  insert(entity,item){if(TENANT.has(entity))throw new IntegrityError(`Insertion tenant-scoped interdite via insert(): utilisez insertForStructure(${entity})`,'TENANT_SCOPE');if((this.state[entity]||[]).some(x=>x.id===item.id))throw new IntegrityError(`${entity}:${item.id} existe déjà`,'DUPLICATE_ID');(this.state[entity]??=[]).push(item);this.save();return item}
  insertForStructure(entity,structureId,item){if(!TENANT.has(entity))throw new IntegrityError(`${entity} n’est pas une entité tenant-scoped`,'TENANT_SCOPE');if(!structureId||item?.structureId!==structureId)throw new IntegrityError('structureId incompatible avec le scope','TENANT_SCOPE');if((this.state[entity]||[]).some(x=>x.id===item.id))throw new IntegrityError(`${entity}:${item.id} existe déjà`,'DUPLICATE_ID');(this.state[entity]??=[]).push(item);this.save();return item}
  update(entity,id,patch){const item=this.get(entity,id);if(!item)throw new Error(`${entity}:${id} introuvable dans la structure active`);assertNoImmutable(patch);Object.assign(item,patch);this.save();return item}
  updateForStructure(entity,structureId,id,patch){assertNoImmutable(patch);const item=this.getForStructure(entity,structureId,id);if(!item)throw new Error(`${entity}:${id} introuvable pour la structure`);if(TENANT.has(entity)&&item.structureId!==structureId)throw new IntegrityError('Scope tenant invalide','TENANT_SCOPE');Object.assign(item,patch);this.save();return item}
  remove(entity,id){const item=this.get(entity,id);if(!item)throw new Error(`${entity}:${id} introuvable dans la structure active`);this.state[entity]=(this.state[entity]||[]).filter(x=>x.id!==id);this.save();return item}
  removeForStructure(entity,structureId,id){const item=this.getForStructure(entity,structureId,id);if(!item)throw new Error(`${entity}:${id} introuvable pour la structure`);if(TENANT.has(entity)&&item.structureId!==structureId)throw new IntegrityError('Scope tenant invalide','TENANT_SCOPE');this.state[entity]=(this.state[entity]||[]).filter(x=>x.id!==id);this.save();return item}
}

export class BlobRepository{
  constructor(){this.dbp=null}
  db(){if(this.dbp)return this.dbp;this.dbp=new Promise((resolve,reject)=>{const req=indexedDB.open('tore-forum-blobs',1);req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('blobs'))req.result.createObjectStore('blobs')};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});return this.dbp}
  async put(key,blob){const db=await this.db();return new Promise((res,rej)=>{const tx=db.transaction('blobs','readwrite');tx.objectStore('blobs').put(blob,key);tx.oncomplete=res;tx.onerror=()=>rej(tx.error)})}
  async get(key){const db=await this.db();return new Promise((res,rej)=>{const req=db.transaction('blobs').objectStore('blobs').get(key);req.onsuccess=()=>res(req.result||null);req.onerror=()=>rej(req.error)})}
  async remove(key){const db=await this.db();return new Promise((res,rej)=>{const tx=db.transaction('blobs','readwrite');tx.objectStore('blobs').delete(key);tx.oncomplete=res;tx.onerror=()=>rej(tx.error)})}
}
