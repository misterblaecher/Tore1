import assert from 'node:assert/strict';

global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};
global.document={createElement(){return {click(){},set href(v){},set download(v){}}}};
global.location={search:'',href:'http://localhost/structures/lembuscade'};
global.URL={createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}};

const {LocalRepository}=await import('../src/core/storage.js');
const {AuthorizationService,AuthorizedRepository}=await import('../src/core/authorization.js');
const {auditService}=await import('../src/services/audit.js');
const {createServices}=await import('../src/services/services-v3.4.2-final.js');
const Views=await import('../src/views/views-v3.4.2.js');

const repo=new LocalRepository();
const auth=new AuthorizationService(repo);
const audit=auditService(repo);
const blobMap=new Map();
const blobs={async put(k,v){blobMap.set(k,v)},async get(k){return blobMap.get(k)||null},async remove(k){blobMap.delete(k)}};
const services=createServices(repo,blobs,audit,auth);
const authorizedRepo=new AuthorizedRepository(repo,auth);
const ctx={repo:authorizedRepo,rawRepo:repo,auth,permissions:{auth},audit,services,blobRepo:blobs};
const use=(userId)=>{repo.state.currentUserId=userId;repo.state.activeStructureId='s_lembuscade';repo.save()};

// Build a delegated role manager without privileged system permissions.
use('u_owner');
const managerRole=services.roles.create({name:'Role Manager',audienceLevel:'Staff',permissions:['members.view','members.manage','roles.manage','events.view']});
const thomas=repo.listForStructure('members','s_lembuscade').find(m=>m.userId==='u_thomas');
services.members.update(thomas.id,{roleId:managerRole.id});

use('u_thomas');
assert.throws(()=>services.roles.create({name:'Escalated admin',permissions:['structure.admin']}),/déléguer|permission|refus/i,'cannot grant structure.admin');
assert.throws(()=>services.roles.create({name:'Escalated owner transfer',permissions:['ownership.transfer']}),/déléguer|permission|refus/i,'cannot grant ownership.transfer');
assert.throws(()=>services.roles.create({name:'Escalated unlock',permissions:['accounting.unlock']}),/déléguer|permission|refus/i,'cannot grant accounting.unlock');

// Update path is protected too.
use('u_owner');
const ordinaryRole=services.roles.create({name:'Ordinary custom',audienceLevel:'Membres',permissions:['members.view']});
const privilegedRole=services.roles.create({name:'Privileged custom',audienceLevel:'Privé',permissions:['members.view','members.manage','roles.manage','ownership.transfer','accounting.unlock']});
use('u_thomas');
assert.throws(()=>services.roles.update(ordinaryRole.id,{permissions:['members.view','structure.admin']}),/déléguer|permission|refus/i,'role update cannot escalate');
assert.throws(()=>services.members.update(repo.listForStructure('members','s_lembuscade').find(m=>m.userId==='u_emma').id,{roleId:privilegedRole.id}),/déléguer|non délégable|permission/i,'role assignment cannot bypass ceiling');
assert.throws(()=>services.members.invite({email:'ceiling@example.be',roleId:privilegedRole.id}),/déléguer|non délégable|permission/i,'invitation cannot bypass ceiling');
assert.throws(()=>services.structure.transferOwnership('u_emma'),/propriétaire principal|refus/i,'non-owner cannot transfer ownership');

// Even an actor who somehow already has a non-delegable permission cannot re-delegate it.
use('u_owner');
const contaminated=services.roles.create({name:'Legacy privileged manager',audienceLevel:'Staff',permissions:['members.view','members.manage','roles.manage','ownership.transfer','accounting.unlock','events.view']});
services.members.update(thomas.id,{roleId:contaminated.id});
use('u_thomas');
assert.throws(()=>services.roles.create({name:'Copy ownership transfer',permissions:['ownership.transfer']}),/non délégable|Owner/i,'ownership.transfer is non-delegable');
assert.throws(()=>services.roles.create({name:'Copy accounting unlock',permissions:['accounting.unlock']}),/non délégable|Owner/i,'accounting.unlock is non-delegable');

// Event detail must remain readable when stats.view is absent.
assert.equal(auth.hasPermission('events.view','u_thomas','s_lembuscade'),true);
assert.equal(auth.hasPermission('stats.view','u_thomas','s_lembuscade'),false);
const event=repo.getForStructure('events','s_lembuscade','e1');
assert.equal(auth.canReadEvent('u_thomas',event),true);
assert.equal(services.stats.optionalByEvent('e1'),null,'optional stats return null without stats.view');
const eventHtml=Views.eventsView(ctx,'e1');
assert.match(eventHtml,/Tournoi de fléchettes/,'event renders without stats permission');

// Stats public summary obeys Visibility Center and remains operational-only.
use('u_owner');
const stats=repo.listForStructure('eventStats','s_lembuscade').find(x=>x.eventId==='e1');
assert.ok(stats,'seed contains stats for e1');
services.stats.publishPublicSummary(stats.id);
services.visibility.set('stats','Privé');
assert.equal(services.publicData.statsSummary('s_lembuscade','e1','Public'),null,'private stats summary hidden from public');
services.visibility.set('stats','Membres');
assert.equal(services.publicData.statsSummary('s_lembuscade','e1','Public'),null,'members stats hidden from public');
const memberSummary=services.publicData.statsSummary('s_lembuscade','e1','Membres');
assert.ok(memberSummary,'members audience can read members stats summary');
for(const key of ['revenue','cost','estimatedProfit','actualProfit','margin','turnover'])assert.equal(key in memberSummary,false,`public summary omits ${key}`);

// Publications separate publication state from audience visibility.
services.visibility.set('publications','Public');
const memberPost=services.posts.create({title:'Annonce membres',body:'Interne membres',status:'PUBLISHED',publishAt:new Date().toISOString(),visibility:'Membres'});
const bureauPost=services.posts.create({title:'Annonce bureau',body:'Interne bureau',status:'PUBLISHED',publishAt:new Date().toISOString(),visibility:'Bureau'});
assert.equal(services.publicData.posts('s_lembuscade','Public').some(p=>p.id===memberPost.id),false,'members post hidden from public');
assert.equal(services.publicData.posts('s_lembuscade','Membres').some(p=>p.id===memberPost.id),true,'members post visible to members');
assert.equal(services.publicData.posts('s_lembuscade','Membres').some(p=>p.id===bureauPost.id),false,'bureau post hidden from members');
assert.equal(services.publicData.posts('s_lembuscade','Bureau').some(p=>p.id===bureauPost.id),true,'bureau post visible to bureau');

services.visibility.set('publications','Privé');
assert.equal(services.publicData.posts('s_lembuscade','Public').length,0,'publications section policy overrides public post visibility');

// Contact is controlled by section visibility, including direct public route rendering.
services.visibility.set('contact','Privé');
assert.equal(services.publicData.contact('s_lembuscade','Public'),null,'private contact data not returned');
repo.state.currentUserId=null;repo.save();
global.location.search='';
const contactHtml=Views.publicView(ctx,'contact');
assert.doesNotMatch(contactHtml,/contact@lembuscade\.be/,'direct contact route does not leak private contact');

// Banner blob key has a real effect on public structure rendering.
use('u_owner');
services.structure.updateSettings({bannerBlobKey:'banner:test:v342'});
repo.state.currentUserId=null;repo.save();
const publicHtml=Views.publicView(ctx,'home');
assert.match(publicHtml,/public-hero-banner/,'public hero contains banner element');
assert.match(publicHtml,/data-blob-key="banner:test:v342"/,'public hero uses bannerBlobKey');

// Real local document binary versioning preserves the previous blob.
use('u_owner');
const fakeV1={name:'guide-v1.pdf',type:'application/pdf',size:100};
const fakeV2={name:'guide-v2.pdf',type:'application/pdf',size:120};
const uploaded=await services.documents.upload(fakeV1,{visibility:'Bureau'});
assert.equal(blobMap.has(uploaded.blobKey),true);
await services.documents.replace(uploaded.id,fakeV2);
const versioned=services.documents.get(uploaded.id);
const v1=versioned.versions.find(v=>v.version===1);
assert.ok(v1?.blobKey,'previous document version has its own blobKey');
assert.equal(blobMap.has(v1.blobKey),true,'previous binary remains available');

console.log('final hardening v3.4.2 tests: PASS');
