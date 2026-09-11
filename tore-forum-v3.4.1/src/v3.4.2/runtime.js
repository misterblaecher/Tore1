const VISIBILITY_LEVELS=['Public','Utilisateurs TORÈ','Membres','Staff','Bureau','Trésorerie','Privé'];
const getCtx=()=>window.__TORE_V342__||null;

function makeField(label,id,value='Public'){
  const field=document.createElement('label');field.className='field';field.innerHTML=`<span>${label}</span><select id="${id}">${VISIBILITY_LEVELS.map(v=>`<option ${v===value?'selected':''}>${v}</option>`).join('')}</select>`;return field;
}

function enhancePostModal(root=document){
  const status=root.querySelector('#post-status');if(!status||root.querySelector('#post-vis'))return;
  const stored=sessionStorage.getItem('tore-v342-post-visibility')||'Public';
  const field=makeField('Visibilité','post-vis',stored);
  const eventField=root.querySelector('#post-event')?.closest('.field');
  if(eventField?.parentNode)eventField.parentNode.insertBefore(field,eventField);else status.closest('.field')?.after(field);
  field.querySelector('select').addEventListener('change',e=>sessionStorage.setItem('tore-v342-post-visibility',e.target.value));
}

function enhanceRoleModal(root=document){
  const checkboxes=[...root.querySelectorAll('[name="role-perm"]')];if(!checkboxes.length)return;
  const ctx=getCtx();if(!ctx)return;
  const grantable=new Set(ctx.services.roles.grantablePermissions());
  for(const cb of checkboxes){
    if(!grantable.has(cb.value)){cb.disabled=true;cb.closest('label')?.classList.add('permission-disabled');cb.title='Vous ne pouvez pas déléguer cette permission.'}
  }
  const grid=checkboxes[0]?.closest('.check-grid');
  if(grid&&!grid.parentElement.querySelector('.permission-ceiling-note')){
    const note=document.createElement('small');note.className='permission-ceiling-note';note.textContent='Seules les permissions que votre rôle peut déléguer sont modifiables.';grid.after(note);
  }
}

function enhanceSettings(root=document){
  const ctx=getCtx();if(!ctx)return;
  const bindUpload=(id,kind)=>{const input=root.querySelector(`#${id}`);if(!input||input.dataset.bound)return;input.dataset.bound='1';input.addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;try{await ctx.services.structure.setBranding(kind,file);location.reload()}catch(err){console.error(err);alert(err.message)}})};
  bindUpload('set-logo-file','logo');bindUpload('set-banner-file','banner');
  for(const button of root.querySelectorAll('[data-v342-action="remove-branding"]')){if(button.dataset.bound)continue;button.dataset.bound='1';button.addEventListener('click',async()=>{if(!confirm(`Supprimer ${button.dataset.kind==='logo'?'le logo':'la bannière'} personnalisé(e) ?`))return;try{await ctx.services.structure.removeBranding(button.dataset.kind);location.reload()}catch(err){console.error(err);alert(err.message)}})}
  for(const edit of root.querySelectorAll('[data-action="edit-role"]')){
    const role=ctx.repo.getForStructure('roles',ctx.repo.state.activeStructureId,edit.dataset.id);if(role&&!ctx.services.roles.canManageRole(role)){edit.disabled=true;edit.title='Ce rôle contient des permissions que vous ne pouvez pas déléguer.'}
  }
}

function bindDocumentVersions(root=document){
  const ctx=getCtx();if(!ctx)return;
  for(const el of root.querySelectorAll('[data-v342-action^="preview-document-version"],[data-v342-action^="download-document-version"]')){if(el.dataset.bound)continue;el.dataset.bound='1';el.addEventListener('click',async()=>{try{if(el.dataset.v342Action==='preview-document-version'){const url=await ctx.services.documents.previewVersion(el.dataset.id,el.dataset.version);window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),60000)}else await ctx.services.documents.downloadVersion(el.dataset.id,el.dataset.version)}catch(err){console.error(err);alert(err.message)}})}
}

function captureActions(event){
  const el=event.target.closest?.('[data-action],[data-v342-action]');if(!el)return;
  const ctx=getCtx();
  if(el.dataset.action==='new-post')sessionStorage.setItem('tore-v342-post-visibility','Public');
  if(el.dataset.action==='edit-post'&&ctx){const post=ctx.repo.getForStructure('publicPosts',ctx.repo.state.activeStructureId,el.dataset.id);sessionStorage.setItem('tore-v342-post-visibility',post?.visibility||'Public')}
  if(el.dataset.action==='close-modal')sessionStorage.removeItem('tore-v342-post-visibility');
  if(el.dataset.action==='complete-onboarding'&&ctx){
    const ids={folklore:'on-vis-folklore',sponsors:'on-vis-sponsors',contact:'on-vis-contact',publications:'on-vis-publications',stats:'on-vis-stats'};
    const current=ctx.services.onboarding.getDraft();const visibility={...(current.visibility||{})};let changed=false;
    for(const [key,id] of Object.entries(ids)){const input=document.getElementById(id);if(input){visibility[key]=input.value;changed=true}}
    if(changed)ctx.services.onboarding.saveDraft({visibility});
  }
}

function enhance(root=document){enhancePostModal(root);enhanceRoleModal(root);enhanceSettings(root);bindDocumentVersions(root)}

document.addEventListener('click',captureActions,true);
const observer=new MutationObserver(()=>enhance(document));observer.observe(document.documentElement,{subtree:true,childList:true});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>enhance(document));else enhance(document);
