import assert from 'node:assert/strict';

global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)}};
global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)}};
global.location={pathname:'/structures/lembuscade/admin/dashboard',search:'',href:'http://localhost/structures/lembuscade/admin/dashboard'};
global.history={pushState(){},replaceState(){}};
global.window={addEventListener(){}};
global.document={createElement(){return {click(){},set href(v){},set download(v){}}}};
global.URL.createObjectURL=()=> 'blob:test'; global.URL.revokeObjectURL=()=>{};

const {LocalRepository}=await import('../src/core/storage.js');
const {AuthorizationService,AuthorizedRepository}=await import('../src/core/authorization.js');
const {permissionService}=await import('../src/core/permissions.js');
const {auditService}=await import('../src/services/audit.js');
const {createServices}=await import('../src/services/services.js');
const V=await import('../src/views/views.js');
const {Router}=await import('../src/core/router.js');

const rawRepo=new LocalRepository();
const auth=new AuthorizationService(rawRepo);
const repo=new AuthorizedRepository(rawRepo,auth);
const permissions=permissionService(rawRepo);
const audit=auditService(rawRepo);
const blobs={m:new Map(),async put(k,v){this.m.set(k,v)},async get(k){return this.m.get(k)},async remove(k){this.m.delete(k)}};
const services=createServices(rawRepo,blobs,audit,auth);
const ctx={repo,rawRepo,auth,permissions,audit,services,blobRepo:blobs};

assert.equal(rawRepo.getGlobal('structures','s_lembuscade').status,'ACTIVE');
assert.equal(rawRepo.state.version,5);
assert.equal(rawRepo.listForStructure('events','s_lembuscade').every(e=>e.structureId==='s_lembuscade'),true);

// Flow 2: event create -> publish -> app sync -> close -> recap -> archive.
const event=services.events.create({title:'Test Event',place:'Liège',startAt:'2026-10-10T20:00:00+02:00',endAt:'2026-10-11T02:00:00+02:00',capacity:120,price:0});
assert.equal(event.status,'DRAFT');
services.events.publish(event.id); assert.equal(rawRepo.get('events',event.id).status,'PUBLISHED');
services.events.syncApp(event.id); assert.equal(rawRepo.get('events',event.id).status,'SYNCED_TO_APP');
services.events.close(event.id); assert.equal(rawRepo.get('events',event.id).status,'CLOSED');
services.events.recap(event.id,'Recap test'); assert.equal(rawRepo.get('events',event.id).status,'RECAP_DRAFT');
services.events.publishRecap(event.id); assert.equal(rawRepo.get('events',event.id).status,'RECAP_PUBLISHED');
services.events.archive(event.id); assert.equal(rawRepo.get('events',event.id).status,'ARCHIVED');
assert.throws(()=>services.events.goLive(event.id),/interdite/);

// Flow 3: album -> real local blob -> publish.
const album=services.albums.create({title:'Album test',visibility:'Public'});
const media=await services.albums.uploadMedia(album.id,new File(['img'],'test.jpg',{type:'image/jpeg'}));
services.albums.publish(album.id); assert.equal(rawRepo.get('albums',album.id).status,'PUBLISHED');
assert.equal(rawRepo.list('media').filter(m=>m.albumId===album.id).length,1);
assert.equal(rawRepo.get('albums',album.id).coverMediaId,media.id);

// Flow 4: role CRUD through protected service, then access follows assignment.
const role=services.roles.create({name:'Test',audienceLevel:'Membres',permissions:['events.view','events.manage']});
const member=rawRepo.get('members','m6');services.members.update(member.id,{roleId:role.id});
rawRepo.state.currentUserId='u_emma';rawRepo.save();
assert.equal(auth.hasPermission('events.manage'),true);assert.equal(auth.hasPermission('accounting.view'),false);
rawRepo.state.currentUserId='u_owner';rawRepo.save();services.members.revoke(member.id);assert.equal(rawRepo.get('members',member.id).status,'REVOKED');

// Flow 5: document metadata + visibility/audit.
const doc=await services.documents.upload(new File(['hello'],'test.txt',{type:'text/plain'}),{visibility:'Bureau'});
assert.ok(doc.blobKey);services.documents.update(doc.id,{tags:['test'],description:'Document de test'});assert.equal(rawRepo.get('documents',doc.id).description,'Document de test');
services.visibility.set('documents','Membres');assert.equal(services.visibility.get('documents'),'Membres');

// Flow 6: accounting lock + exceptional unlock.
const acc=services.accounting.create({label:'Test coût',actual:100,planned:90,type:'EXPENSE'});services.accounting.lock(acc.id);assert.equal(rawRepo.get('accountingEntries',acc.id).status,'LOCKED');
assert.throws(()=>services.accounting.update(acc.id,{actual:101}),/verrouillée/);services.accounting.unlock(acc.id);assert.equal(rawRepo.get('accountingEntries',acc.id).status,'VALIDATED');

// Flow 7: visibility creates audit log.
const before=audit.list().length;services.visibility.set('albums','Membres');assert.ok(audit.list().length>before);

// Discussions are multi-channel and reactions are persistent.
const c=services.channels.create({name:'test-salon',visibility:'Membres'});const msg=services.channels.post(c.id,'Bonjour');services.channels.react(msg.id,'👍');assert.equal(rawRepo.get('messages',msg.id).reactions['👍'].includes('u_owner'),true);

// Folklore versions: restore creates a new version.
const fp=services.folklore.create({title:'Page test',body:'v1',visibility:'Membres'});services.folklore.save(fp.id,{body:'v2'});const versionBefore=rawRepo.get('folklorePages',fp.id).version;services.folklore.restore(fp.id,1);assert.equal(rawRepo.get('folklorePages',fp.id).version,versionBefore+1);

// Scheduled post remains non-public until due.
const future=new Date(Date.now()+86400000).toISOString();const post=services.posts.create({title:'Programmé',body:'Plus tard',status:'SCHEDULED',publishAt:future});assert.equal(services.posts.isPublic(post),false);

// Stats summary strips financial values.
const summary=services.stats.publishPublicSummary('st1');assert.equal('revenue' in summary,false);assert.equal('actualProfit' in summary,false);assert.equal(summary.entries,642);

// Router deep links.
const r=new Router(()=>{});assert.equal(r.match('/structures/lembuscade/admin/events/e1').name,'admin-events');assert.equal(r.match('/structures/lembuscade/albums').name,'public-albums');assert.equal(r.match('/onboarding').name,'onboarding');

// Render all important pages without throw.
for(const [name,fn,args=[]] of [
 ['dashboard',V.dashboardView],['events',V.eventsView],['members',V.membersView],['discussions',V.discussionsView],['documents',V.documentsView],['albums',V.albumsView],['folklore',V.folkloreView],['archives',V.archivesView],['planning',V.planningView],['accounting',V.accountingView],['stats',V.statsView],['visibility',V.visibilityView],['audit',V.auditView],['publications',V.publicationsView],['settings',V.settingsView],['public',V.publicView]
]){const html=fn(ctx,...args);assert.equal(typeof html,'string',name);assert.ok(html.length>100,name)}

console.log('TORÈ Forum v3.4 product tests: PASS');
