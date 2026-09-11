import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const root = new URL('../', import.meta.url);
const js = fs.readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
const sw = fs.readFileSync(new URL('../sw.js', import.meta.url), 'utf8');

const nodes = new Map();
const mkNode = () => ({
  innerHTML:'', value:'', dataset:{}, style:{}, hidden:false,
  classList:{toggle(){},add(){},remove(){},contains(){return false}},
  addEventListener(){}, setAttribute(){}, appendChild(){}, remove(){}, click(){},
  querySelector(){return null}, querySelectorAll(){return []},
});
for (const id of ['app','toast-root','modal-root']) nodes.set(id, mkNode());

const sandbox = {
  console,
  localStorage:{_v:{},getItem(k){return this._v[k]??null},setItem(k,v){this._v[k]=String(v)}},
  document:{
    getElementById(id){return nodes.get(id)??null},
    querySelector(){return null}, querySelectorAll(){return []},
    createElement(){return mkNode()}, body:{appendChild(){}}, onkeydown:null,
  },
  window:{scrollTo(){},addEventListener(){}},
  navigator:{},
  setTimeout(fn){return 1}, clearTimeout(){},
  Blob:globalThis.Blob, URL:globalThis.URL, Date, JSON, Math, String, Number, Array, Object,
};
vm.createContext(sandbox);
vm.runInContext(js, sandbox, {filename:'app.js'});
const E = expr => vm.runInContext(expr, sandbox);

// 1. All main routes render without throwing.
for (const route of E('Object.keys(routes)')) {
  const html = E(`routes[${JSON.stringify(route)}]()`);
  assert.equal(typeof html, 'string', `route ${route} should render a string`);
  assert.ok(html.length > 50, `route ${route} should not be empty`);
}

// 2. User supplied HTML is escaped.
assert.equal(E(`h('<img src=x onerror=alert(1)>')`), '&lt;img src=x onerror=alert(1)&gt;');

// 3. Message reactions are actual buttons and persisted state supports likes.
E(`state.route='discussions'`);
const discussion = E('discussions()');
assert.match(discussion, /data-action="toggle-like"/);
assert.match(discussion, /reaction-btn/);
const before = E(`reactionParts(state.messages[0].reaction).count`);
E(`toggleLike(0,{textContent:'',classList:{toggle(){}},setAttribute(){}})`);
const after = E(`reactionParts(state.messages[0].reaction).count`);
assert.equal(after, before + 1, 'first like should increment count');
E(`toggleLike(0,{textContent:'',classList:{toggle(){}},setAttribute(){}})`);
assert.equal(E(`reactionParts(state.messages[0].reaction).count`), before, 'second like should remove current user like');

// 4. Icon sizing regression: generic icons must have explicit finite dimensions.
assert.match(css, /\.ico\{width:18px;height:18px/);
assert.match(css, /\.btn \.ico\{width:15px;height:15px/);
assert.match(css, /\.icon-btn \.ico\{width:17px;height:17px/);
assert.match(css, /\.global-search \.ico\{width:15px;height:15px/);

// 5. Document-level shortcut listener no longer accumulates on every render.
assert.ok(!js.includes("document.addEventListener('keydown',shortcut)"));
assert.ok(js.includes('document.onkeydown=shortcut'));

// 6. Cache versioning must invalidate the old v2 cache.
assert.match(sw, /tore-forum-v2\.1\.0/);
assert.match(sw, /caches\.delete/);
assert.match(sw, /skipWaiting/);

// 7. Important controls have actions instead of dead buttons.
for (const action of [
  'manage-event','toggle-like','download-attachment','import-document','download-document',
  'new-album','delete-album','export-archives','new-archive','edit-folklore','export-finance',
  'invite-member','export-audit','refresh-audit','add-planning'
]) {
  assert.ok(js.includes(`case '${action}'`) || js.includes(`data-action="${action}"`), `missing control/action: ${action}`);
}

// 8. Search, filters and selection wiring exists.
for (const fn of ['bindTabs','bindChannels','bindFolders','bindAlbums','bindArchiveYears','bindFolklore','bindAuditRows','openGlobalSearch']) {
  assert.equal(E(`typeof ${fn}`),'function', `${fn} should exist`);
}

console.log('TORÈ Forum v2.1 audit tests: PASS');
