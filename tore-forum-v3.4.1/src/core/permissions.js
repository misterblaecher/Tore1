import { AuthorizationService,VISIBILITY_LEVELS } from './authorization.js';
export const visibilityOrder=VISIBILITY_LEVELS;
export const permissionService=repo=>{
  const auth=new AuthorizationService(repo);
  return {auth,context:(...a)=>auth.context(...a),can:(p)=>auth.hasPermission(p),canSee:(level)=>auth.canViewLevel(level)};
};
export const canSee=(level,ctx)=>{
  if(level==='Public')return true;if(level==='Utilisateurs TORÈ')return !!ctx.user;if(!ctx.member)return false;if(level==='Privé')return !!ctx.isAdmin;
  const order=['Public','Utilisateurs TORÈ','Membres','Staff','Bureau','Trésorerie','Privé'];return order.indexOf(ctx.audienceLevel||'Membres')>=order.indexOf(level);
};
