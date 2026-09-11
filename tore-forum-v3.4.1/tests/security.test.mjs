import assert from 'node:assert/strict';

function browserMocks(){
  global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
  global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
  global.location={pathname:'/structures/lembuscade/admin/dashboard',search:'',href:'http://localhost/structures/lembuscade/admin/dashboard'};
  global.history={pushState(){},replaceState(){}};
  global.window={addEventListener(){}};
  global.document={createElement(){return {click(){},set href(v){},set download(v){}}}};
  global.URL.createObjectURL=()=> 'blob:test'; global.URL.revokeObjectURL=()=>{};
}
browserMocks();
const {LocalRepository}=await import('../src/core/storage.js');
const {AuthorizationService,AuthorizationError}=await import('../src/core/authorization.js');
const {auditService}=await import('../src/services/audit.js');
const {createServices}=await import('../src/services/services.js');

const repo=new LocalRepository();
const auth=new AuthorizationService(repo);
const audit=auditService(repo);
const blobs={m:new Map(),async put(k,v){this.m.set(k,v)},async get(k){return this.m.get(k)},async remove(k){this.m.delete(k)}};
const services=createServices(repo,blobs,audit,auth);
const as=(userId,structureId='s_lembuscade')=>{repo.state.currentUserId=userId;repo.state.activeStructureId=structureId;repo.save()};
const denied=async(fn,label)=>{let ok=false;try{await fn()}catch(e){ok=e instanceof AuthorizationError||e?.code==='DENIED'||/refus|permission|autorisé|verrouill/i.test(e?.message||'')}assert.equal(ok,true,label)};

// TEST A — cross tenant by known ID
as('u_owner');
assert.equal(repo.getForStructure('documents','s_lembuscade','doc_other'),null,'raw scoped repository must not return foreign document');
await denied(()=>services.documents.get('doc_other'),'cross-tenant document must be denied');
assert.equal(repo.get('events','e_other'),null,'active-tenant get must not leak foreign event');

// TEST B — member direct admin/accounting access
as('u_emma');
assert.equal(auth.canAccessAdmin('u_emma','s_lembuscade'),true,'member may access intranet shell');
assert.equal(auth.hasPermission('accounting.view','u_emma','s_lembuscade'),false,'member has no accounting permission');
assert.equal(auth.routePermission('accounting'),'accounting.view');
await denied(()=>services.summary.accounting(),'accounting route/service must deny member');

// TEST C — direct public URL cannot bypass section visibility
as('u_owner'); services.visibility.set('albums','Membres');
as(null);
const publicAudience=services.publicData.audience('s_lembuscade',null);
assert.equal(publicAudience,'Public');
assert.deepEqual(services.publicData.albums('s_lembuscade',publicAudience),[],'public visitor must not receive member-only albums');

// TEST D — preview query is not identity
assert.equal(services.publicData.audience('s_lembuscade','tresorerie'),'Public','anonymous preview query must not elevate audience');
assert.equal(auth.canPreviewVisibility(null,'s_lembuscade','Trésorerie'),false);

// TEST E — search must not leak treasury document/message/accounting title
as('u_emma');
const budgetResults=services.search.all('budget');
assert.equal(budgetResults.some(x=>x.id==='doc2'),false,'treasury document must not leak in search');
assert.equal(budgetResults.some(x=>String(x.label).includes('confidentiel')),false,'confidential label must not leak');
assert.equal(budgetResults.some(x=>x.type==='Comptabilité'),false,'accounting must not leak');
const justificatifResults=services.search.all('justificatifs');
assert.equal(justificatifResults.some(x=>x.type==='Message'),false,'treasury channel message must not leak');

// TEST F — channel read
await denied(()=>services.channels.messages('c4'),'standard member must not read treasury channel');
assert.equal(services.channels.list().some(c=>c.id==='c4'),false,'treasury channel name must be absent from list');

// TEST G — channel post
await denied(()=>services.channels.post('c4','tentative'),'standard member must not post in treasury channel');

// TEST H — document download by known ID
await denied(()=>services.documents.download('doc2'),'download must enforce document permission');

// TEST I — role creation
await denied(()=>services.roles.create({name:'Escalade',audienceLevel:'Privé',permissions:['structure.admin']}),'role creation must require roles.manage');

// TEST J — settings mutation
await denied(()=>services.structure.updateSettings({name:'Nom piraté'}),'settings mutation must require structure.manage');
assert.equal(repo.getGlobal('structures','s_lembuscade').name,'L’Embuscade');

// TEST K — locked accounting cannot be edited/deleted
as('u_owner');
await denied(()=>services.accounting.update('acc5',{actual:1}),'locked accounting update must be denied');
await denied(()=>services.accounting.remove('acc5'),'locked accounting delete must be denied');
assert.equal(repo.getForStructure('accountingEntries','s_lembuscade','acc5').actual,900);

// TEST L — public member privacy
as(null);
const visibleMembers=services.publicData.members('s_lembuscade','Public');
assert.equal(visibleMembers.some(m=>m.id==='m3'),false,'publicProfile=false staff must be absent');
assert.equal(visibleMembers.some(m=>m.id==='m6'),false,'publicProfile=false member must be absent');
assert.equal(visibleMembers.some(m=>m.id==='m1'),true,'publicProfile=true owner may be public');

// Extra: audit entries never cross tenant, and private public event is not exposed.
as('u_owner');
assert.equal(audit.list('s_lembuscade').every(x=>x.structureId==='s_lembuscade'),true);
as(null);
assert.equal(services.publicData.events('s_autre','Public').some(e=>e.id==='e_other'),false);

console.log('TORÈ Forum v3.4 security tests: PASS');
