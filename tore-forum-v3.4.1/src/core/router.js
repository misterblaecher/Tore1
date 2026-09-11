export class Router {
  constructor(onRoute){this.onRoute=onRoute;window.addEventListener('popstate',()=>this.emit())}
  normalize(path){return path.replace(/\/$/,'')||'/'}
  navigate(path,{replace=false}={}){const p=this.normalize(path);history[replace?'replaceState':'pushState']({},'',p);this.emit()}
  emit(){this.onRoute(this.match(location.pathname))}
  match(path){const p=this.normalize(path);const parts=p.split('/').filter(Boolean);if(parts[0]==='onboarding')return {name:'onboarding',params:{}};if(parts[0]!=='structures')return {name:'home',params:{}};const slug=parts[1];if(parts.length===2)return {name:'public-home',params:{slug}};if(parts[2]!=='admin')return {name:`public-${parts[2]||'home'}`,params:{slug,sub:parts[2],id:parts[3]||null}};const page=parts[3]||'dashboard';const id=parts[4]||null;return {name:`admin-${page}`,params:{slug,id}}}
  start(){this.emit()}
}
