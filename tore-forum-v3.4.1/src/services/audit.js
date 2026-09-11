import { uid } from '../core/utils.js';
export const auditService=repo=>({
 log(action,resource,before=null,after=null,context={},structureId=repo.state.activeStructureId){
  const parsed=typeof resource==='string'&&resource.includes(':')?resource.split(':'):null;
  const row={id:uid('audit'),structureId,userId:repo.state.currentUserId,action,resource:typeof resource==='string'?resource:`${resource.type}:${resource.id}`,resourceType:typeof resource==='object'?resource.type:parsed?.[0]||'resource',resourceId:typeof resource==='object'?resource.id:parsed?.slice(1).join(':')||resource,before,after,context,createdAt:new Date().toISOString()};
  repo.insertForStructure('auditLogs',structureId,row);return row;
 },
 list(structureId=repo.state.activeStructureId){return repo.listForStructure('auditLogs',structureId).slice().sort((a,b)=>new Date(b.createdAt)-new Date(a.createdAt))}
});
