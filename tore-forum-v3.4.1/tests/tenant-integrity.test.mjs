import assert from 'node:assert/strict';
global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
global.document={createElement(){return {click(){},set href(v){},set download(v){}}}};global.URL.createObjectURL=()=> 'blob:test';global.URL.revokeObjectURL=()=>{};
const {LocalRepository}=await import('../src/core/storage.js');const {AuthorizationService}=await import('../src/core/authorization.js');const {auditService}=await import('../src/services/audit.js');const {createServices}=await import('../src/services/services.js');
const repo=new LocalRepository(),auth=new AuthorizationService(repo),audit=auditService(repo),blobs={m:new Map(),async put(k,v){this.m.set(k,v)},async get(k){return this.m.get(k)},async remove(k){this.m.delete(k)}},s=createServices(repo,blobs,audit,auth);
repo.state.currentUserId='u_owner';repo.state.activeStructureId='s_lembuscade';repo.save();
const denied=/immutable|structureId|interdit|DENIED|scope|hors structure|introuvable/i;
assert.throws(()=>repo.getGlobal('events','e_other'),/global|tenant|scope|interdit/i,'raw global tenant lookup forbidden');
assert.throws(()=>repo.insert('events',{id:'raw_inject',structureId:'s_autre'}),/insertForStructure|tenant|scope|interdit/i,'raw tenant insert forbidden');
assert.throws(()=>s.members.invite({email:'x@example.be',roleId:'r_member',structureId:'s_autre'}),denied,'invitation payload tenant injection denied');

// Fixtures in the foreign tenant, deliberately created through the repository as test setup.
const foreignFixtures={
 folklorePages:{id:'fp_foreign',structureId:'s_autre',title:'Foreign folklore',body:'secret',visibility:'Privé',status:'DRAFT',category:'Guide',version:1,versions:[],updatedAt:new Date().toISOString()},
 planningItems:{id:'plan_foreign',structureId:'s_autre',title:'Foreign plan',type:'task',team:'Bureau',startAt:'2026-12-01T18:00:00.000Z',endAt:'2026-12-01T19:00:00.000Z',assigneeMemberIds:[],status:'TODO',deadline:null,eventId:null},
 accountingEntries:{id:'acc_foreign',structureId:'s_autre',eventId:null,type:'EXPENSE',category:'Secret',supplier:null,label:'Foreign accounting',planned:1,actual:1,paid:false,status:'DRAFT',note:'',receiptDocumentId:null,createdAt:new Date().toISOString()},
 publicPosts:{id:'post_foreign',structureId:'s_autre',title:'Foreign post',body:'secret',status:'DRAFT',publishAt:new Date().toISOString(),eventId:null,authorUserId:'u_other',image:null,visibility:'Privé'},
 roles:{id:'role_foreign',structureId:'s_autre',name:'Foreign role',systemRole:false,audienceLevel:'Membres',permissions:[]}
};
for(const [entity,item] of Object.entries(foreignFixtures))if(!repo.getForStructure(entity,'s_autre',item.id))repo.insertForStructure(entity,'s_autre',item);

// CREATE injection: payload-controlled tenant fields must be rejected, never ignored.
const before={};for(const e of ['events','channels','albums','folklorePages','planningItems','accountingEntries','publicPosts','roles','documents'])before[e]=repo.listForStructure(e,'s_autre').length;
const createCases=[
 ['event',()=>s.events.create({title:'Cross tenant',startAt:'2026-12-01T20:00:00+01:00',endAt:'2026-12-01T21:00:00+01:00',structureId:'s_autre'})],
 ['channel',()=>s.channels.create({name:'cross',visibility:'Membres',structureId:'s_autre'})],
 ['album',()=>s.albums.create({title:'Cross',structureId:'s_autre'})],
 ['folklore',()=>s.folklore.create({title:'Cross',structureId:'s_autre'})],
 ['planning',()=>s.planning.create({title:'Cross',startAt:'2026-12-01T20:00:00+01:00',endAt:'2026-12-01T21:00:00+01:00',structureId:'s_autre'})],
 ['accounting',()=>s.accounting.create({label:'Cross',planned:1,actual:1,structureId:'s_autre'})],
 ['post',()=>s.posts.create({title:'Cross',structureId:'s_autre'})],
 ['role',()=>s.roles.create({name:'Injected role',audienceLevel:'Membres',permissions:[],structureId:'s_autre'})]
];
for(const [name,fn] of createCases)assert.throws(fn,denied,`${name} create must reject injected structureId`);
await assert.rejects(()=>s.documents.upload(new File(['x'],'x.txt',{type:'text/plain'}),{visibility:'Bureau',structureId:'s_autre'}),denied,'document upload must reject injected structureId');
for(const e of Object.keys(before))assert.equal(repo.listForStructure(e,'s_autre').length,before[e],`${e}: foreign tenant unchanged after create injection`);

// UPDATE injection: immutable id/structureId must be rejected across service boundaries.
const local={event:'e2',channel:'c1',album:'a1',folklore:'fp1',planning:'p1',accounting:'acc1',post:'post1',role:'r_bureau',document:'doc1'};
const updates=[
 ['event',(patch)=>s.events.update(local.event,patch)],['channel',(patch)=>s.channels.update(local.channel,patch)],['album',(patch)=>s.albums.update(local.album,patch)],['folklore',(patch)=>s.folklore.save(local.folklore,patch)],['planning',(patch)=>s.planning.update(local.planning,patch)],['accounting',(patch)=>s.accounting.update(local.accounting,patch)],['post',(patch)=>s.posts.update(local.post,patch)],['role',(patch)=>s.roles.update(local.role,patch)],['document',(patch)=>s.documents.update(local.document,patch)]
];
for(const [name,fn] of updates){assert.throws(()=>fn({structureId:'s_autre'}),denied,`${name}: structureId immutable`);assert.throws(()=>fn({id:'new-id'}),denied,`${name}: id immutable`)}
assert.equal(repo.getForStructure('events','s_lembuscade','e2').structureId,'s_lembuscade');

// Exact known foreign IDs must not distinguish or expose the resource through service CRUD/action paths.
const foreignCases=[
 ['event',()=>s.events.update('e_other',{title:'pwn'}),()=>s.events.archive('e_other')],
 ['channel',()=>s.channels.update('c_other',{name:'pwn'}),()=>s.channels.archive('c_other')],
 ['document',()=>s.documents.update('doc_other',{name:'pwn.pdf'}),()=>s.documents.remove('doc_other')],
 ['album',()=>s.albums.update('a_other',{title:'pwn'}),()=>s.albums.remove('a_other')],
 ['folklore',()=>s.folklore.save('fp_foreign',{title:'pwn'}),()=>s.folklore.archive('fp_foreign')],
 ['planning',()=>s.planning.update('plan_foreign',{title:'pwn'}),()=>s.planning.remove('plan_foreign')],
 ['accounting',()=>s.accounting.update('acc_foreign',{actual:2}),()=>s.accounting.remove('acc_foreign')],
 ['post',()=>s.posts.update('post_foreign',{title:'pwn'}),()=>s.posts.archive('post_foreign')],
 ['role',()=>s.roles.update('role_foreign',{name:'pwn'}),()=>s.roles.delete('role_foreign')]
];
for(const [name,...ops] of foreignCases)for(const op of ops)await assert.rejects(async()=>op(),denied,`${name}: foreign action denied`)
await assert.rejects(()=>s.documents.download('doc_other'),denied,'known foreign document download denied');
assert.equal(s.queries.get('events','e_other'),null,'known foreign event read returns no data');
assert.equal(s.queries.get('documents','doc_other'),null,'known foreign document read returns no data');

console.log('tenant integrity v3.4 regression/attack tests: PASS');
