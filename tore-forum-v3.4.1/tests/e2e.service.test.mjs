import assert from 'node:assert/strict';
global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)}};
global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)}};
global.document={createElement(){return {click(){},set href(v){},set download(v){}}}};global.URL.createObjectURL=()=> 'blob:test';global.URL.revokeObjectURL=()=>{};
const {LocalRepository}=await import('../src/core/storage.js');const {AuthorizationService,AuthorizationError}=await import('../src/core/authorization.js');const {auditService}=await import('../src/services/audit.js');const {createServices}=await import('../src/services/services.js');
const repo=new LocalRepository(),auth=new AuthorizationService(repo),audit=auditService(repo),blobs={m:new Map(),async put(k,v){this.m.set(k,v)},async get(k){return this.m.get(k)},async remove(k){this.m.delete(k)}},s=createServices(repo,blobs,audit,auth);
const use=u=>{repo.state.currentUserId=u;repo.state.activeStructureId='s_lembuscade';repo.save()};

// E2E service 1 — owner creates/publishes event and public side receives it.
use('u_owner');const e=s.events.create({title:'E2E Public Event',place:'Liège',startAt:'2026-11-01T20:00:00+01:00',endAt:'2026-11-02T01:00:00+01:00',visibility:'Public'});s.events.publish(e.id);assert.equal(s.publicData.events('s_lembuscade','Public').some(x=>x.id===e.id),true);

// E2E service 2 — Bureau salon invisible/unreadable/unpostable to member.
const c=s.channels.create({name:'bureau-e2e',visibility:'Bureau'});s.channels.post(c.id,'Confidentiel bureau');use('u_emma');assert.equal(s.channels.list().some(x=>x.id===c.id),false);assert.throws(()=>s.channels.messages(c.id),AuthorizationError);assert.throws(()=>s.channels.post(c.id,'intrusion'),AuthorizationError);

// E2E service 3 — treasury document visible to treasurer, invisible/search/download denied to member.
use('u_owner');const d=await s.documents.upload(new File(['secret'],'treasury-secret.txt',{type:'text/plain'}),{visibility:'Trésorerie'});s.documents.update(d.id,{tags:['e2e-secret-budget']});use('u_marie');assert.equal(s.documents.list().some(x=>x.id===d.id),true);use('u_emma');assert.equal(s.documents.list().some(x=>x.id===d.id),false);assert.equal(s.search.all('e2e-secret-budget').length,0);await assert.rejects(()=>s.documents.download(d.id),AuthorizationError);

// E2E service 4 — album draft absent public, then published visible.
use('u_owner');const a=s.albums.create({title:'E2E Album',visibility:'Public'});assert.equal(s.publicData.albums('s_lembuscade','Public').some(x=>x.id===a.id),false);await s.albums.uploadMedia(a.id,new File(['x'],'e2e.jpg',{type:'image/jpeg'}));s.albums.publish(a.id);assert.equal(s.publicData.albums('s_lembuscade','Public').some(x=>x.id===a.id),true);

// E2E service 5 — accounting edit then lock then deny mutation.
const x=s.accounting.create({label:'E2E facture',type:'EXPENSE',planned:10,actual:9});s.accounting.update(x.id,{actual:10});s.accounting.lock(x.id);assert.throws(()=>s.accounting.update(x.id,{actual:11}),AuthorizationError);

console.log('TORÈ Forum v3.4 service E2E flows: PASS');
