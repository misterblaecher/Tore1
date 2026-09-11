import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PORT||8080);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.webmanifest':'application/manifest+json','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml'};
http.createServer((req,res)=>{let url=new URL(req.url,'http://localhost');let pathname=decodeURIComponent(url.pathname);let file=path.join(root,pathname.replace(/^\//,''));if(pathname==='/'||!path.extname(file))file=path.join(root,'index.html');if(!file.startsWith(root)){res.writeHead(403);return res.end('Forbidden')}fs.stat(file,(err,st)=>{if(err||!st.isFile()){file=path.join(root,'index.html')}fs.readFile(file,(e,data)=>{if(e){res.writeHead(500);return res.end('Error')}res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});res.end(data)})})}).listen(port,()=>console.log(`TORÈ Forum: http://localhost:${port}/structures/lembuscade/admin/dashboard`));
