import * as base from './views.js?v=3.4.1';
import { h } from '../core/utils.js';

export * from './views.js?v=3.4.1';

const raw = ctx => ctx.rawRepo || ctx.repo?.repo || ctx.repo;
const auth = ctx => ctx.auth || ctx.permissions?.auth;
const activeStructure = ctx => raw(ctx).getGlobal('structures', raw(ctx).state.activeStructureId);
const VIS = ['Public','Utilisateurs TORÈ','Membres','Staff','Bureau','Trésorerie','Privé'];
const visibilitySelect = (id, value) => `<select id="${id}">${VIS.map(v=>`<option ${v===value?'selected':''}>${v}</option>`).join('')}</select>`;
const deniedPublic = (slug, title='Contenu non accessible') => `<div class="public-site"><main class="public-main"><section class="public-section"><div class="ux-state denied"><h3>${h(title)}</h3><p>Cette section n’est pas visible pour votre audience actuelle.</p><a class="btn" href="/structures/${h(slug)}" data-nav>Retour à la page publique</a></div></section></main></div>`;

export function eventsView(ctx, detailId){
  const a = auth(ctx), r = raw(ctx), structureId = r.state.activeStructureId;
  if(a.hasPermission('stats.view', r.state.currentUserId, structureId)) return base.eventsView(ctx, detailId);
  const services = {...ctx.services, stats:{...ctx.services.stats, list:()=>[]}};
  return base.eventsView({...ctx, services}, detailId);
}

export function visibilityView(ctx){
  let html = base.visibilityView(ctx);
  const services = ctx.services;
  const extra = [
    ['contact','Contact','eye'],
    ['publications','Actualités / Publications','news']
  ].map(([id,label])=>`<div class="visibility-row"><div class="iconbox"></div><div><b>${label}</b><small>Visibilité actuelle</small></div><select class="select visibility-select" data-resource="${id}">${VIS.map(v=>`<option ${services.visibility.get(id)===v?'selected':''}>${v}</option>`).join('')}</select></div>`).join('');
  return html.replace('<div class="warning-box">Les routes publiques, la recherche et les previews utilisent ces règles.', `${extra}<div class="warning-box">Les routes publiques, la recherche et les previews utilisent ces règles.`);
}

export function settingsView(ctx){
  const r = raw(ctx), s = activeStructure(ctx), a = auth(ctx);
  let html = base.settingsView(ctx);
  const logoPreview = s.logoBlobKey
    ? `<img class="blob-image branding-preview-logo" data-blob-key="${h(s.logoBlobKey)}" alt="Logo actuel ${h(s.name)}">`
    : `<img class="branding-preview-logo" src="/${h(s.logo || 'assets/app_icon.png')}" alt="Logo actuel ${h(s.name)}">`;
  const bannerPreview = s.bannerBlobKey
    ? `<img class="blob-image branding-preview-banner" data-blob-key="${h(s.bannerBlobKey)}" alt="Bannière actuelle ${h(s.name)}">`
    : `<div class="branding-empty">Aucune bannière personnalisée</div>`;
  const panel = `<article class="panel"><div class="panel-head"><h2>Branding</h2><span class="row-sub">Logo, bannière et identité publique</span></div><div class="panel-body branding-settings"><div class="branding-logo-row">${logoPreview}<div class="stack-actions"><label class="btn upload-btn">Changer le logo<input id="set-logo-file" type="file" accept="image/png,image/jpeg,image/webp" hidden></label>${s.logoBlobKey?'<button class="btn danger" data-v342-action="remove-branding" data-kind="logo">Supprimer le logo</button>':''}</div></div><div class="branding-banner-row">${bannerPreview}<div class="stack-actions"><label class="btn upload-btn">Changer la bannière<input id="set-banner-file" type="file" accept="image/png,image/jpeg,image/webp" hidden></label>${s.bannerBlobKey?'<button class="btn danger" data-v342-action="remove-branding" data-kind="banner">Supprimer la bannière</button>':''}</div></div><p class="row-sub">Chaque modification est journalisée dans Audit.</p></div></article>`;
  html = html.replace('<article class="panel"><div class="panel-head"><h2>Contact & SEO</h2>', `${panel}<article class="panel"><div class="panel-head"><h2>Contact & SEO</h2>`);
  if(s.ownerUserId !== r.state.currentUserId){
    html = html.replace(/<button class="btn small ghost-gold" data-action="transfer-ownership">Transférer la propriété<\/button>/g, '');
  }
  return html;
}

export function onboardingView(ctx){
  let html = base.onboardingView(ctx);
  const d = ctx.services.onboarding.getDraft();
  if(!html.includes('id="on-publish-now"')) return html;
  const extra = `<label class="field"><span>Folklore</span>${visibilitySelect('on-vis-folklore',d.visibility?.folklore||'Public')}</label><label class="field"><span>Sponsors</span>${visibilitySelect('on-vis-sponsors',d.visibility?.sponsors||'Public')}</label><label class="field"><span>Contact</span>${visibilitySelect('on-vis-contact',d.visibility?.contact||'Public')}</label><label class="field"><span>Actualités / Publications</span>${visibilitySelect('on-vis-publications',d.visibility?.publications||'Public')}</label><label class="field"><span>Résumé Stats</span>${visibilitySelect('on-vis-stats',d.visibility?.stats||'Privé')}</label>`;
  return html.replace('<label class="field full"><span>Publication initiale</span>', `${extra}<label class="field full"><span>Publication initiale</span>`);
}

export function documentsView(ctx){
  let html = base.documentsView(ctx);
  const params = new URLSearchParams(location.search);
  const id = params.get('doc') || sessionStorage.getItem('doc-selected');
  if(!id) return html;
  let doc = null;
  try { doc = ctx.services.documents.get(id); } catch { return html; }
  const versions = (doc?.versions || []).filter(v=>v.blobKey);
  if(!versions.length) return html;
  const versionHtml = `<div class="document-version-history"><h3>Versions précédentes</h3>${versions.slice().sort((a,b)=>b.version-a.version).map(v=>`<div class="stat-row"><div><b>v${v.version} · ${h(v.name||doc.name)}</b><small>${h(v.at||'')}</small></div><div class="stack-actions"><button class="btn small" data-v342-action="preview-document-version" data-id="${doc.id}" data-version="${v.version}">Preview</button><button class="btn small" data-v342-action="download-document-version" data-id="${doc.id}" data-version="${v.version}">Télécharger</button></div></div>`).join('')}</div>`;
  return html.replace('</aside></div>', `${versionHtml}</aside></div>`);
}

export function publicView(ctx, sub='home', detailId=null){
  const r = raw(ctx), s = activeStructure(ctx), services = ctx.services;
  const preview = new URLSearchParams(location.search).get('preview');
  const audience = services.publicData.audience(s.id, preview);
  const canContact = services.publicData.canSection(s.id, 'contact', audience);

  if(sub === 'contact' && !canContact) return deniedPublic(s.slug, 'Contact non accessible');

  const originalContact = s.contact;
  if(!canContact) s.contact = {email:'',phone:'',address:'',instagram:'',website:''};
  let html;
  try { html = base.publicView(ctx, sub, detailId); }
  finally { s.contact = originalContact; }

  if(!canContact){
    html = html.replace(/<section class="public-section contact-section">[\s\S]*?<\/section>/, '');
    html = html.replace(new RegExp(`<a href="/structures/${s.slug}/contact" data-nav>Contact<\\/a>`,'g'), '');
  }

  if(sub === 'home' && s.bannerBlobKey && html.includes('<section class="public-hero">')){
    html = html.replace('<section class="public-hero">', `<section class="public-hero has-banner"><img class="blob-image public-hero-banner" data-blob-key="${h(s.bannerBlobKey)}" alt="Bannière ${h(s.name)}"><div class="public-hero-shade" aria-hidden="true"></div>`);
  }

  return html;
}
