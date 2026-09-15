// Asset export only: common canvas, alpha validation and exact layer compositing.
// Usage: NODE_PATH=<directory containing sharp> node prepare-assets.cjs
const sharp = require('sharp');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = __dirname;
const names = ['01_background_far','02_fire_halo','03_smoke_back','04_statue_tore','05_ground_mid','06_foreground_rocks','07_smoke_front','08_brand_glow'];
(async () => {
  const report = [];
  for (const name of names) {
    const source = path.join(root, 'assets', name + '.png');
    const output = path.join(root, 'assets', name + '.webp');
    let normalized=await sharp(source).resize(1920,1080,{fit:'fill'}).png().toBuffer();
    // Register the platform beneath the sculpture's plinth (not across its legs).
    if(name==='05_ground_mid') {
      normalized=await sharp(normalized).extract({left:0,top:0,width:1920,height:960}).extend({top:120,bottom:0,left:0,right:0,background:{r:0,g:0,b:0,alpha:0}}).png().toBuffer();
    }
    await sharp(normalized).webp({quality:88,alphaQuality:100}).toFile(output);
    const meta = await sharp(output).metadata();
    const stats = await sharp(output).stats();
    if (name !== names[0] && (!meta.hasAlpha || stats.isOpaque)) throw new Error(name + ': missing transparency');
    report.push({name,width:meta.width,height:meta.height,alpha:meta.hasAlpha,opaque:stats.isOpaque,bytes:(await fs.stat(output)).size});
  }
  const layers = ['03_smoke_back','02_fire_halo','04_statue_tore','05_ground_mid','06_foreground_rocks','07_smoke_front','08_brand_glow'];
  const opacity={'03_smoke_back':.32,'02_fire_halo':.8,'07_smoke_front':.15,'08_brand_glow':.15};
  const overlays=[];
  for(const n of layers){
    const p=path.join(root,'assets',n+'.webp');
    if(opacity[n]){
      const raw=await sharp(p).ensureAlpha().raw().toBuffer();
      for(let i=3;i<raw.length;i+=4) raw[i]=Math.round(raw[i]*opacity[n]);
      overlays.push({input:await sharp(raw,{raw:{width:1920,height:1080,channels:4}}).png().toBuffer()});
    }else overlays.push({input:p});
  }
  await sharp(path.join(root,'assets/01_background_far.webp')).composite(overlays).png().toFile(path.join(root,'composition-test.png'));
  const tiles = [];
  for(let i=0;i<names.length;i++) {
    const input = await sharp(path.join(root,'assets',names[i]+'.webp')).resize(480,270).flatten({background:'#202026'}).png().toBuffer();
    tiles.push({input,left:(i%2)*480,top:Math.floor(i/2)*270});
  }
  await sharp({create:{width:960,height:1080,channels:3,background:'#202026'}}).composite(tiles).png().toFile(path.join(root,'layers-contact-sheet.png'));
  await fs.writeFile(path.join(root,'asset-checks.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})();
