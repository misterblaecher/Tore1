import {spawn, spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';

const cwd=fileURLToPath(new URL('../',import.meta.url));
const artifactsDir=path.join(cwd,'tests','artifacts','browser');
fs.mkdirSync(artifactsDir,{recursive:true});
const children=new Set();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function existing(p){return p&&fs.existsSync(p)?p:null}
function commandPath(command){const finder=process.platform==='win32'?'where':'which';const r=spawnSync(finder,[command],{encoding:'utf8',windowsHide:true});if(r.status!==0||!r.stdout)return null;return r.stdout.split(/\r?\n/).map(x=>x.trim()).find(Boolean)||null}
function findBrowser(){
 for(const key of ['CHROMIUM','CHROME_PATH','EDGE_PATH']){const p=existing(process.env[key]);if(p)return{path:p,source:key}}
 const c=[];
 if(process.platform==='win32'){
  const pf=process.env.PROGRAMFILES,pfx=process.env['PROGRAMFILES(X86)'],local=process.env.LOCALAPPDATA;
  c.push(pf&&path.join(pf,'Google','Chrome','Application','chrome.exe'),pfx&&path.join(pfx,'Google','Chrome','Application','chrome.exe'),local&&path.join(local,'Google','Chrome','Application','chrome.exe'),pf&&path.join(pf,'Microsoft','Edge','Application','msedge.exe'),pfx&&path.join(pfx,'Microsoft','Edge','Application','msedge.exe'),local&&path.join(local,'Microsoft','Edge','Application','msedge.exe'),local&&path.join(local,'Chromium','Application','chrome.exe'));
  for(const cmd of ['chrome.exe','msedge.exe','chromium.exe']){const p=commandPath(cmd);if(p)c.push(p)}
 }else if(process.platform==='darwin'){
  c.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge','/Applications/Chromium.app/Contents/MacOS/Chromium');
  for(const cmd of ['google-chrome','chromium','chromium-browser','microsoft-edge']){const p=commandPath(cmd);if(p)c.push(p)}
 }else{
  c.push('/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/microsoft-edge');
  for(const cmd of ['chromium','chromium-browser','google-chrome','google-chrome-stable','microsoft-edge']){const p=commandPath(cmd);if(p)c.push(p)}
 }
 for(const candidate of c){const p=existing(candidate);if(p)return{path:p,source:'auto-detect'}}return null
}

async function killTree(child,{force=false}={}){
 if(!child?.pid)return;
 children.delete(child);
 if(process.platform==='win32'){
  spawnSync('taskkill',['/PID',String(child.pid),'/T',force?'/F':'/F'],{stdio:'ignore',windowsHide:true});
  return;
 }
 const signal=force?'SIGKILL':'SIGTERM';
 try{process.kill(-child.pid,signal)}catch{try{child.kill(signal)}catch{}}
 if(!force){await sleep(400);try{process.kill(-child.pid,'SIGKILL')}catch{try{child.kill('SIGKILL')}catch{}}}
}

async function cleanup(){for(const child of [...children])await killTree(child)}
process.on('SIGINT',async()=>{await cleanup();process.exit(130)});
process.on('SIGTERM',async()=>{await cleanup();process.exit(143)});

const browser=findBrowser();
if(!browser){
 console.log('Browser QA: SKIPPED — aucun navigateur Chromium compatible détecté.');
 console.log('Installe Google Chrome / Microsoft Edge / Chromium, ou définis CHROMIUM vers l’exécutable.');
 if(process.platform==='win32')console.log('$env:CHROMIUM="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"');
 process.exit(0);
}
console.log(`Browser QA: navigateur détecté (${browser.source})`);console.log(`Browser QA: ${browser.path}`);

const profileDir=fs.mkdtempSync(path.join(os.tmpdir(),'tore-browser-qa-'));
const commonArgs=['--headless=new','--disable-gpu','--disable-dev-shm-usage','--disable-extensions','--disable-background-networking','--no-first-run','--hide-scrollbars',`--user-data-dir=${profileDir}`];
if(process.platform==='linux')commonArgs.unshift('--no-sandbox');

async function runBrowser(args,timeoutMs=15000){
 return await new Promise(resolve=>{
  const p=spawn(browser.path,[...commonArgs,...args],{stdio:['ignore','pipe','pipe'],windowsHide:true,detached:process.platform!=='win32'});children.add(p);let stderr='',stdout='',settled=false;
  p.stderr.on('data',d=>stderr+=d.toString());p.stdout.on('data',d=>stdout+=d.toString());
  const finish=async result=>{if(settled)return;settled=true;clearTimeout(timer);children.delete(p);resolve({...result,stderr,stdout})};
  const timer=setTimeout(async()=>{await killTree(p);finish({ok:false,timeout:true})},timeoutMs);
  p.on('error',err=>finish({ok:false,error:err}));
  p.on('exit',code=>finish({ok:code===0,code}));
 });
}

let server=null,watchdog=null;
try{
 watchdog=setTimeout(async()=>{console.error('Browser QA: INCONCLUSIVE — timeout global de suite (90 s).');await cleanup();process.exit(2)},90000);

 const sanityOut=path.join(artifactsDir,'browser-sanity.png');try{fs.unlinkSync(sanityOut)}catch{}
 const sanity=await runBrowser([`--screenshot=${sanityOut}`,'about:blank'],12000);
 if(!sanity.ok||!fs.existsSync(sanityOut)){
  const diag=`${sanity.stderr||''}\n${sanity.stdout||''}`.trim().slice(-1800);
  console.error('Browser QA: INCONCLUSIVE — navigateur trouvé mais inutilisable dans cet environnement.');
  if(sanity.timeout)console.error('Raison: timeout au lancement du navigateur.');
  if(sanity.error)console.error(`Raison: ${sanity.error.message}`);
  if(diag)console.error(diag);
  process.exitCode=2;
 }else{
  const port=String(8098+Math.floor(Math.random()*100));
  server=spawn(process.execPath,['server.mjs'],{cwd,env:{...process.env,PORT:port},stdio:['ignore','pipe','pipe'],windowsHide:true,detached:process.platform!=='win32'});children.add(server);let serverOut='';server.stdout.on('data',d=>serverOut+=d.toString());server.stderr.on('data',d=>serverOut+=d.toString());
  const started=Date.now();let ready=false;while(Date.now()-started<8000&&!ready){try{const res=await fetch(`http://127.0.0.1:${port}/`);ready=res.ok}catch{}if(!ready)await sleep(150)}
  if(!ready)throw new Error(`Serveur TORÈ indisponible sur ${port}. ${serverOut.slice(-900)}`);

  const routes=[
   ['/structures/lembuscade',1440,900,'public-desktop'],
   ['/structures/lembuscade/admin/dashboard',1440,900,'admin-desktop'],
   ['/structures/lembuscade/admin/events/e1',1024,900,'event-tablet'],
   ['/structures/lembuscade/admin/visibility',768,1024,'visibility-tablet'],
   ['/structures/lembuscade/admin/settings',1440,900,'settings-desktop'],
   ['/structures/lembuscade/admin/publications',390,844,'publications-mobile'],
   ['/onboarding',390,844,'onboarding-mobile']
  ];
  const failures=[];let completed=0;
  for(const [route,width,height,name] of routes){
   const out=path.join(artifactsDir,`${name}.png`);try{fs.unlinkSync(out)}catch{}
   const result=await runBrowser([`--window-size=${width},${height}`,`--screenshot=${out}`,`http://127.0.0.1:${port}${route}`],15000);
   const ok=result.ok&&fs.existsSync(out)&&fs.statSync(out).size>0;
   if(ok){completed++;console.log(`Browser QA: OK   ${route} -> ${path.relative(cwd,out)}`)}else{failures.push({route,result});console.error(`Browser QA: FAIL ${route} (${width}x${height})`);const diag=`${result.stderr||''}\n${result.stdout||''}`.trim();if(diag)console.error(diag.slice(-1200))}
  }
  if(failures.length){console.error(`Browser QA: FAIL — ${failures.length}/${routes.length} scénario(s) navigateur ont échoué.`);process.exitCode=1}else{console.log(`Browser QA: PASS (${completed}/${routes.length} captures réelles)`);console.log(`Captures : ${path.relative(cwd,artifactsDir)}`)}
 }
}catch(err){console.error('Browser QA: FAIL — erreur du runner ou de l’application.');console.error(err?.stack||err);process.exitCode=1}
finally{
 if(watchdog)clearTimeout(watchdog);
 await cleanup();
 try{fs.rmSync(profileDir,{recursive:true,force:true})}catch{}
}
