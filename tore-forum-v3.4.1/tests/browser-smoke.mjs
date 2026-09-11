import {spawn, spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const cwd = fileURLToPath(new URL('../', import.meta.url));
const artifactsDir = path.join(cwd, 'tests', 'artifacts', 'browser');
fs.mkdirSync(artifactsDir, {recursive: true});

function existing(p) {
  return p && fs.existsSync(p) ? p : null;
}

function commandPath(command) {
  const finder = process.platform === 'win32' ? 'where' : 'which';
  const r = spawnSync(finder, [command], {encoding: 'utf8', windowsHide: true});
  if (r.status !== 0 || !r.stdout) return null;
  return r.stdout.split(/\r?\n/).map(x => x.trim()).find(Boolean) || null;
}

function findBrowser() {
  for (const key of ['CHROMIUM', 'CHROME_PATH', 'EDGE_PATH']) {
    const p = existing(process.env[key]);
    if (p) return {path: p, source: key};
  }

  const candidates = [];

  if (process.platform === 'win32') {
    const pf = process.env.PROGRAMFILES;
    const pfx86 = process.env['PROGRAMFILES(X86)'];
    const local = process.env.LOCALAPPDATA;

    candidates.push(
      pf && path.join(pf, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      pfx86 && path.join(pfx86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      local && path.join(local, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      pf && path.join(pf, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      pfx86 && path.join(pfx86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      local && path.join(local, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      local && path.join(local, 'Chromium', 'Application', 'chrome.exe')
    );

    for (const cmd of ['chrome.exe', 'msedge.exe', 'chromium.exe']) {
      const p = commandPath(cmd);
      if (p) candidates.push(p);
    }
  } else if (process.platform === 'darwin') {
    candidates.push(
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium'
    );
    for (const cmd of ['google-chrome', 'chromium', 'chromium-browser', 'microsoft-edge']) {
      const p = commandPath(cmd);
      if (p) candidates.push(p);
    }
  } else {
    candidates.push(
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/microsoft-edge'
    );
    for (const cmd of ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable', 'microsoft-edge']) {
      const p = commandPath(cmd);
      if (p) candidates.push(p);
    }
  }

  for (const candidate of candidates) {
    const p = existing(candidate);
    if (p) return {path: p, source: 'auto-detect'};
  }
  return null;
}

const browser = findBrowser();

if (!browser) {
  console.error('Browser QA: FAIL — aucun navigateur Chromium détecté.');
  console.error('Installe Google Chrome / Microsoft Edge / Chromium, ou définis CHROMIUM vers l’exécutable.');
  if (process.platform === 'win32') {
    console.error('PowerShell exemple :');
    console.error(`  $env:CHROMIUM="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"`);
    console.error('  npm run test:browser');
  }
  process.exit(1);
}

console.log(`Browser QA: navigateur détecté (${browser.source})`);
console.log(`Browser QA: ${browser.path}`);

const port = String(8098 + Math.floor(Math.random() * 100));
const server = spawn(process.execPath, ['server.mjs'], {
  cwd,
  env: {...process.env, PORT: port},
  stdio: ['ignore', 'pipe', 'pipe'],
  windowsHide: true
});

let serverOut = '';
server.stdout.on('data', d => serverOut += d.toString());
server.stderr.on('data', d => serverOut += d.toString());

async function waitForServer(timeoutMs = 8000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      if (response.ok) return;
    } catch {}
    await new Promise(r => setTimeout(r, 150));
  }
  throw new Error(`Le serveur TORÈ n’a pas démarré sur le port ${port}.\n${serverOut.slice(-1000)}`);
}

function killServer() {
  if (!server.killed) {
    try { server.kill(); } catch {}
  }
}

process.on('exit', killServer);
process.on('SIGINT', () => { killServer(); process.exit(130); });
process.on('SIGTERM', () => { killServer(); process.exit(143); });

await waitForServer();

async function shot(route, width, height, name) {
  const out = path.join(artifactsDir, `${name}.png`);
  try { fs.unlinkSync(out); } catch {}

  const args = [
    '--headless=new',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-extensions',
    '--no-first-run',
    '--hide-scrollbars',
    `--window-size=${width},${height}`,
    `--screenshot=${out}`,
    `http://127.0.0.1:${port}${route}`
  ];

  if (process.platform === 'linux') args.unshift('--no-sandbox');

  return await new Promise(resolve => {
    const p = spawn(browser.path, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    let stderr = '';
    let stdout = '';
    p.stderr.on('data', d => stderr += d.toString());
    p.stdout.on('data', d => stdout += d.toString());

    const timer = setTimeout(() => {
      try { p.kill(); } catch {}
      resolve({ok: false, timeout: true, stderr, stdout, out});
    }, 15000);

    p.on('error', err => {
      clearTimeout(timer);
      resolve({ok: false, error: err, stderr, stdout, out});
    });

    p.on('exit', code => {
      clearTimeout(timer);
      resolve({
        ok: code === 0 && fs.existsSync(out) && fs.statSync(out).size > 0,
        code, stderr, stdout, out
      });
    });
  });
}

const routes = [
  ['/structures/lembuscade', 1440, 1000, 'public-desktop'],
  ['/structures/lembuscade/admin/dashboard', 1440, 1000, 'admin-desktop'],
  ['/structures/lembuscade/admin/discussions', 390, 844, 'discussions-mobile'],
  ['/structures/lembuscade/admin/documents', 768, 900, 'documents-tablet'],
  ['/structures/lembuscade/admin/events/e1', 1024, 900, 'event-tablet'],
  ['/onboarding', 390, 844, 'onboarding-mobile']
];

let completed = 0;
const failures = [];

for (const args of routes) {
  const [route, width, height] = args;
  const result = await shot(...args);

  if (!result.ok) {
    failures.push({route, width, height, result});
    console.error(`Browser QA: FAIL ${route} (${width}x${height})`);
    if (result.timeout) console.error('  timeout navigateur');
    if (result.error) console.error(`  ${result.error.message}`);
    const diagnostics = `${result.stderr || ''}\n${result.stdout || ''}`.trim();
    if (diagnostics) console.error(diagnostics.slice(-1200));
    continue;
  }

  completed++;
  console.log(`Browser QA: OK   ${route} -> ${path.relative(cwd, result.out)}`);
}

killServer();

assert.equal(
  failures.length,
  0,
  `${failures.length} capture(s) navigateur ont échoué. Voir tests/artifacts/browser et les logs ci-dessus.`
);

console.log(`Browser QA: PASS (${completed}/${routes.length} captures réelles)`);
console.log(`Captures : ${path.relative(cwd, artifactsDir)}`);
