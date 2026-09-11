import assert from 'node:assert/strict';
global.localStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};global.sessionStorage={m:new Map(),getItem(k){return this.m.get(k)||null},setItem(k,v){this.m.set(k,String(v))},removeItem(k){this.m.delete(k)},clear(){this.m.clear()}};global.document={createElement(){return {click(){}}}};
const {LocalRepository}=await import('../src/core/storage.js');const {AuthorizationService}=await import('../src/core/authorization.js');const {auditService}=await import('../src/services/audit.js');const {createServices}=await import('../src/services/services.js');
const repo=new LocalRepository(),auth=new AuthorizationService(repo),audit=auditService(repo),blobs={async put(){},async get(){return null},async remove(){}},s=createServices(repo,blobs,audit,auth);const use=u=>{repo.state.currentUserId=u;repo.state.activeStructureId='s_lembuscade';repo.save()};
use('u_owner');
const ownerMember=repo.listForStructure('members','s_lembuscade').find(m=>m.userId==='u_owner');const ownerRole=repo.getForStructure('roles','s_lembuscade',ownerMember.roleId);
assert.ok(ownerRole.systemRole,'Owner role is system role');
assert.throws(()=>s.members.update(ownerMember.id,{roleId:'r_member'}),/owner|propri/i,'owner downgrade denied');
assert.throws(()=>s.members.revoke(ownerMember.id),/owner|propri/i,'owner revoke denied');
assert.throws(()=>s.members.alumnize(ownerMember.id),/owner|propri/i,'owner alumni denied');
assert.throws(()=>s.roles.update(ownerRole.id,{permissions:[]}),/owner|système|critique/i,'owner role critical permission removal denied');
assert.throws(()=>s.roles.update(ownerRole.id,{name:'Former Owner'}),/owner|système/i,'owner system role rename denied');
assert.throws(()=>s.roles.delete(ownerRole.id),/owner|système/i,'owner system role deletion denied');
const ordinaryMember=repo.listForStructure('members','s_lembuscade').find(m=>m.userId==='u_jules');
assert.throws(()=>s.members.update(ordinaryMember.id,{roleId:ownerRole.id}),/owner|transfert|propri/i,'owner role assignment outside transfer denied');
assert.equal(typeof s.structure.transferOwnership,'function');
const auditBefore=audit.list().length;s.structure.transferOwnership('u_jules');
assert.equal(repo.getGlobal('structures','s_lembuscade').ownerUserId,'u_jules');
const j=repo.listForStructure('members','s_lembuscade').find(m=>m.userId==='u_jules');assert.equal(repo.getForStructure('roles','s_lembuscade',j.roleId).name,'Owner');
const activeOwners=repo.listForStructure('members','s_lembuscade').filter(m=>m.status==='ACTIVE'&&repo.getForStructure('roles','s_lembuscade',m.roleId)?.systemRole);assert.equal(activeOwners.length,1);assert.equal(activeOwners[0].userId,'u_jules');
assert.ok(audit.list().slice(0,audit.list().length-auditBefore+1).some(x=>x.action==='OWNERSHIP_TRANSFERRED')||audit.list().some(x=>x.action==='OWNERSHIP_TRANSFERRED'),'ownership transfer audited');
assert.doesNotThrow(()=>s.structure.assertValidOwnership('s_lembuscade'));
// Former owner can no longer use the transfer endpoint just because it used to own the structure.
use('u_owner');assert.throws(()=>s.structure.transferOwnership('u_marie'),/propriétaire|permission|refus/i);
// Anonymous onboarding must be rejected before any partial write.
repo.state.currentUserId=null;repo.save();const counts={structures:repo.state.structures.length,members:repo.state.members.length,audit:repo.state.auditLogs.length};assert.throws(()=>s.onboarding.createDraft('create'),/AUTH_REQUIRED|authent/i,'anonymous onboarding denied');assert.throws(()=>s.claims.request('s_autre',{reason:'anonymous'}),/AUTH_REQUIRED|authent/i,'anonymous claim denied');assert.deepEqual({structures:repo.state.structures.length,members:repo.state.members.length,audit:repo.state.auditLogs.length},counts,'anonymous flows create no partial data');
console.log('governance v3.4 tests: PASS');
