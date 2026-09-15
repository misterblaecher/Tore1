// Optional preview server; opening index.html directly also works.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webp':'image/webp','.png':'image/png','.json':'application/json'};
http.createServer((req,res)=>{
 let pathname;try{pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);}catch{res.writeHead(400).end();return;}
 const target=path.resolve(__dirname,'.'+(pathname==='/'?'/index.html':pathname));
 if(!target.startsWith(__dirname+path.sep)){res.writeHead(403).end();return;}
 fs.readFile(target,(err,bytes)=>{if(err){res.writeHead(404).end();return;}res.writeHead(200,{'Content-Type':types[path.extname(target)]||'application/octet-stream'});res.end(bytes);});
}).listen(4178,'127.0.0.1',()=>console.log('TORÈ preview: http://127.0.0.1:4178'));
