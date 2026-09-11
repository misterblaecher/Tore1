import assert from 'node:assert/strict';
const memory=new Map();global.localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,String(v)),removeItem:k=>memory.delete(k)};
const {seed}=await import('../src/data/seed.js');
const old=structuredClone(seed);old.version=4;delete old.publicPages;delete old.structureClaims;old.roles=old.roles.map(r=>{const x={...r};delete x.systemRole;if(x.name==='Owner')x.permissions=(x.permissions||[]).filter(p=>p!=='ownership.transfer');return x});old.members.push({...old.members.find(m=>m.id==='m6'),id:'legacy_extra_owner',roleId:'r_owner',status:'ACTIVE'});
memory.set('tore-forum-v3-state',JSON.stringify(old));
const {LocalRepository}=await import('../src/core/storage.js');const repo=new LocalRepository();
assert.equal(repo.state.version,5);
assert.ok(Array.isArray(repo.state.publicPages)&&repo.state.publicPages.length>=repo.state.structures.length,'public pages migrated');
assert.ok(Array.isArray(repo.state.structureClaims),'claim collection migrated');
for(const st of repo.state.structures){const role=repo.listForStructure('roles',st.id).find(r=>r.name==='Owner');assert.ok(role?.systemRole);assert.ok(role.permissions.includes('ownership.transfer'));const owner=repo.listForStructure('members',st.id).filter(m=>m.roleId===role.id&&m.status==='ACTIVE');assert.equal(owner.length,1);assert.equal(owner[0].userId,st.ownerUserId);const pages=repo.listForStructure('publicPages',st.id);assert.equal(pages.length,1);assert.equal(pages[0].status,st.status==='ACTIVE'?'PUBLISHED':'DRAFT')}
const structureIds=new Set(repo.state.structures.map(x=>x.id));
for(const entity of ['roles','members','invitations','events','channels','messages','folders','documents','albums','media','folklorePages','planningItems','accountingEntries','eventStats','visibilityPolicies','publicPosts','auditLogs','notifications','publicPages','structureClaims'])for(const row of repo.state[entity]||[])assert.ok(structureIds.has(row.structureId),`${entity}:${row.id} has valid structureId`);
const eventIds=new Set(repo.state.events.map(x=>x.id)),channelIds=new Set(repo.state.channels.map(x=>x.id)),albumIds=new Set(repo.state.albums.map(x=>x.id));
for(const m of repo.state.messages)assert.ok(channelIds.has(m.channelId),`message ${m.id} channel exists`);
for(const m of repo.state.media)assert.ok(albumIds.has(m.albumId),`media ${m.id} album exists`);
for(const x of repo.state.eventStats)assert.ok(eventIds.has(x.eventId),`stats ${x.id} event exists`);
for(const x of repo.state.accountingEntries)if(x.eventId)assert.ok(eventIds.has(x.eventId),`accounting ${x.id} event exists`);
console.log('migration + seed integrity v3.3 -> v3.4: PASS');
