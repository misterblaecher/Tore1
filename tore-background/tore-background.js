/* TORÈ 2.5D — no dependencies, works over file://. */
(() => {
  'use strict';
  const scriptBase = new URL('.', document.currentScript?.src || location.href);
  const clamp = (v,min,max) => Math.min(max,Math.max(min,Number.isFinite(Number(v))?Number(v):min));
  const active = new Set();
  let globalFrame = 0;
  function schedule() { if (!globalFrame && active.size) globalFrame=requestAnimationFrame(tick); }
  function tick(time) {
    globalFrame=0;
    for(const instance of active) instance.update(time);
    schedule();
  }
  function unregister(instance) {
    active.delete(instance);
    if(!active.size && globalFrame) {cancelAnimationFrame(globalFrame);globalFrame=0;}
  }
  const definitions = [
    ['01_background_far',-60,4,1],['03_smoke_back',-35,6,.32],
    ['02_fire_halo',-20,9,.8],['04_statue_tore',15,12,1],
    ['05_ground_mid',25,16,1],['06_foreground_rocks',45,22,1],
    ['07_smoke_front',55,26,.15],['08_brand_glow',-10,4,.15]
  ];
  class ToreBackground3D {
    static presets = Object.freeze({
      HERO:Object.freeze({intensity:1,parallax:1,particles:true,smoke:true,clickPulse:true}),
      FORUM:Object.freeze({intensity:.7,parallax:.65,particles:true,smoke:true,clickPulse:true}),
      DASHBOARD:Object.freeze({intensity:.4,parallax:.3,particles:'reduced',smoke:'reduced',clickPulse:false})
    });
    constructor(element, options={}) {
      if(!(element instanceof HTMLElement)) throw new TypeError('ToreBackground3D requires a host element');
      this.host=element;
      this.options={...ToreBackground3D.presets.HERO,quality:'auto',assetsPath:new URL('assets/',scriptBase).href,...options};
      this.current={x:0,y:0};this.target={x:0,y:0};this.pulse=0;this.frames=0;this.last=0;this.time=0;
      this.destroyed=false;this.wanted=false;this.visible=true;this.particles=[];this.abort=new AbortController();
      this.motion=matchMedia('(prefers-reduced-motion: reduce)');this.coarse=matchMedia('(pointer: coarse)');
      this.scene=document.createElement('div');this.scene.className='tore-background__scene';this.scene.setAttribute('aria-hidden','true');
      this.layers=definitions.map(([name,z,amplitude,opacity])=>{
        const el=new Image();el.src=new URL(name+'.webp',new URL(this.options.assetsPath,document.baseURI)).href;
        el.alt='';el.draggable=false;el.className='tore-background__layer';el.dataset.layer=name;
        el.addEventListener('error',()=>this.host.dispatchEvent(new CustomEvent('tore:asset-error',{detail:name})),{signal:this.abort.signal});
        this.scene.append(el);return {el,name,z,amplitude,opacity};
      });
      this.canvases=[this.makeCanvas(0,false),this.makeCanvas(35,false),this.makeCanvas(-34,true),this.makeCanvas(54,true)];
      this.shade=document.createElement('div');this.shade.className='tore-background__shade';this.shade.setAttribute('aria-hidden','true');
      this.host.prepend(this.scene,this.shade);
      this.emberSprite=this.sprite(false);this.smokeSprite=this.sprite(true);
      const signal=this.abort.signal;
      this.host.addEventListener('pointermove',e=>{
        if(e.pointerType==='touch'||this.motion.matches)return;
        const r=this.host.getBoundingClientRect();
        this.target.x=clamp((e.clientX-r.left)/r.width*2-1,-1,1);
        this.target.y=clamp((e.clientY-r.top)/r.height*2-1,-1,1);
      },{passive:true,signal});
      this.host.addEventListener('pointerleave',()=>{this.target.x=0;this.target.y=0;},{signal});
      this.host.addEventListener('click',e=>{
        if(!e.target.closest('a,button,input,select,textarea,label,summary,[role="button"]')&&this.options.clickPulse)this.triggerPulse();
      },{signal});
      document.addEventListener('visibilitychange',()=>this.sync(),{signal});
      this.motion.addEventListener('change',()=>{this.resetMotion();this.sync();},{signal});
      this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(this.host);
      this.intersectionObserver=new IntersectionObserver(entries=>{this.visible=entries[0].isIntersecting;this.sync();});
      this.intersectionObserver.observe(this.host);
      this.setIntensity(this.options.intensity);this.setParallax(this.options.parallax);
      this.setQuality(this.options.quality);this.start();
    }
    get raf(){return active.has(this)?globalFrame:0;}
    makeCanvas(z,smoke){
      const el=document.createElement('canvas');el.className='tore-background__effect';this.scene.append(el);
      return {el,ctx:el.getContext('2d',{alpha:true}),z,smoke,amplitude:z<0?6:z>40?26:z>0?20:10};
    }
    sprite(smoke){
      const c=document.createElement('canvas');c.width=c.height=smoke?128:32;
      const ctx=c.getContext('2d'),r=c.width/2,g=ctx.createRadialGradient(r,r,0,r,r,r);
      g.addColorStop(0,smoke?'rgba(104,72,57,.2)':'rgba(255,238,186,1)');
      g.addColorStop(.25,smoke?'rgba(83,61,53,.15)':'rgba(255,135,37,.8)');
      g.addColorStop(1,'rgba(80,30,10,0)');ctx.fillStyle=g;ctx.fillRect(0,0,c.width,c.height);return c;
    }
    setIntensity(value){this.options.intensity=clamp(value,0,1.5);if(this.scene)this.render(0);return this;}
    setParallax(value){this.options.parallax=clamp(value,0,1.5);return this;}
    setQuality(value){
      if(!['low','medium','high','auto'].includes(value))throw new RangeError('Unknown quality');
      this.options.quality=value;this.chooseQuality();this.resize();return this;
    }
    chooseQuality(){
      const small=this.host.clientWidth<700;
      const weak=(navigator.hardwareConcurrency||8)<=4 || (navigator.deviceMemory||8)<=4;
      this.quality=this.options.quality==='auto'?(small||weak?'low':this.host.clientWidth<1100?'medium':'high'):this.options.quality;
      this.fps=this.quality==='high'?40:30;
      const cap={low:20,medium:48,high:96}[this.quality];
      this.cap=this.options.particles?Math.round(cap*(this.options.particles==='reduced'?.35:1)):0;
      if(this.particles.length>this.cap)this.particles.length=this.cap;
      while(this.particles.length<this.cap)this.particles.push(this.spawn({},true));
    }
    resize(){
      if(this.destroyed)return;
      this.chooseQuality();
      const w=this.host.clientWidth,h=this.host.clientHeight;
      const scale=Math.max((w+100)/1920,(h+100)/1080);
      this.width=Math.ceil(1920*scale);this.height=Math.ceil(1080*scale);
      const pos=w<700?.72:.5;
      Object.assign(this.scene.style,{width:this.width+'px',height:this.height+'px',left:((w-this.width)*pos)+'px',top:((h-this.height)*.5)+'px'});
      for(const c of this.canvases){
        const ratio=c.smoke?(this.quality==='low'?.2:.35):Math.min(devicePixelRatio||1,this.quality==='low'?1:1.5);
        c.el.width=Math.round(this.width*ratio);c.el.height=Math.round(this.height*ratio);
        c.ctx.setTransform(c.el.width/1920,0,0,c.el.height/1080,0,0);
      }
      this.render(0);this.draw(0);this.sync();
    }
    spawn(p,initial=false){
      // Emitters are fixed in artwork coordinates. Pointer coordinates never enter here.
      const halo=Math.random()<.65,a=Math.random()*Math.PI*2;
      p.x=halo?1400+Math.cos(a)*440:1040+Math.random()*780;
      p.y=halo?540+Math.sin(a)*360:975+Math.random()*65;
      p.origin={x:p.x,y:p.y,source:halo?'halo':'lava'};
      p.front=Math.random()<.3;p.vx=(Math.random()-.5)*14;p.vy=-(p.front?32:13)-Math.random()*14;
      p.life=0;p.maxLife=3+Math.random()*5;p.size=p.front?5+Math.random()*5:2+Math.random()*3;
      if(initial){p.life=Math.random()*p.maxLife;p.y+=p.vy*p.life;}
      return p;
    }
    triggerPulse(){
      if(this.destroyed||this.motion.matches||!this.options.clickPulse)return this;
      this.pulse=1;
      for(let i=0;i<Math.min(16,this.particles.length);i++)this.spawn(this.particles[i]);
      return this;
    }
    resetMotion(){this.current={x:0,y:0};this.target={x:0,y:0};this.pulse=0;this.render(0);this.draw(0);}
    sync(){
      if(this.destroyed)return;
      if(this.wanted&&this.visible&&!document.hidden&&!this.motion.matches){active.add(this);this.last=0;schedule();}
      else unregister(this);
    }
    start(){if(!this.destroyed){this.wanted=true;this.sync();}return this;}
    stop(){this.wanted=false;unregister(this);return this;}
    update(now){
      if(document.hidden||this.motion.matches||!this.visible){this.sync();return;}
      if(this.last&&now-this.last<1000/this.fps)return;
      const dt=this.last?Math.min((now-this.last)/1000,.08):1/this.fps;
      this.last=now;this.frames++;this.time+=dt;
      const f=1-Math.exp(-dt*5);
      this.current.x+=(this.target.x-this.current.x)*f;this.current.y+=(this.target.y-this.current.y)*f;
      this.pulse*=Math.exp(-dt*1.4);
      this.render(dt);this.draw(dt);
    }
    place(item,extraY=0,zoom=1){
      // Compensate perspective magnification: all layers retain identical registration at rest.
      const compensation=(1600-item.z)/1600;
      const mobile=this.host.clientWidth<700?.3:1;
      const p=this.motion.matches?0:this.options.parallax*mobile;
      const x=this.current.x*item.amplitude*p;
      const y=this.current.y*item.amplitude*p*.6+extraY;
      item.el.style.transform=`translate3d(${x*compensation}px,${y*compensation}px,${item.z}px) scale(${compensation*zoom})`;
    }
    render(){
      if(!this.layers)return;
      const i=this.options.intensity,t=this.motion.matches?0:this.time;
      for(const l of this.layers){
        const statue=l.name==='04_statue_tore',smoke=l.name.includes('smoke'),halo=l.name==='02_fire_halo';
        const drift=statue?Math.sin(t*.7)*1.2*i+this.pulse*.6:smoke?Math.sin(t*.15)*3:0;
        this.place(l,drift,statue?1+Math.sin(t*.7)*.001*i:1);
        const smokeFactor=this.options.smoke==='reduced'?.4:this.options.smoke?1:0;
        l.el.style.opacity=String(l.opacity*(smoke?smokeFactor*i:halo?(.45+.55*i)+this.pulse*.15:1));
        if(halo)l.el.style.filter=`brightness(${.8+i*.2+Math.sin(t*1.2)*.035*i+this.pulse*.7})`;
        if(l.name==='05_ground_mid')l.el.style.filter=`brightness(${1+this.pulse*.3})`;
      }
      if(this.canvases)for(const c of this.canvases)this.place(c);
      if(this.shade)this.shade.style.opacity=String(clamp(.45-i*.25,0,.5));
    }
    draw(dt){
      if(!this.canvases)return;
      for(const c of this.canvases)c.ctx.clearRect(0,0,1920,1080);
      if(this.motion.matches)return;
      for(const p of this.particles){
        p.life+=dt;p.x+=p.vx*dt;p.y+=p.vy*dt*(1+this.pulse*.7);
        if(p.life>p.maxLife||p.y<0)this.spawn(p);
        const ctx=this.canvases[p.front?1:0].ctx;
        ctx.globalAlpha=Math.max(0,Math.sin(p.life/p.maxLife*Math.PI))*.8*this.options.intensity;
        ctx.drawImage(this.emberSprite,p.x-p.size/2,p.y-p.size/2,p.size,p.size);
      }
      if(this.options.smoke){
        const count=this.quality==='low'?2:5;
        for(let depth=0;depth<2;depth++){
          const ctx=this.canvases[depth+2].ctx;
          ctx.globalAlpha=(depth?.22:.5)*this.options.intensity*(this.options.smoke==='reduced'?.35:1);
          for(let j=0;j<count;j++){
            const size=depth?580:400,x=(j%2?1500:250)+Math.sin(this.time*.09+j)*100;
            const y=950-Math.sin(this.time*.06+j*2)*65;
            ctx.drawImage(this.smokeSprite,x-size/2,y-size/2,size,size);
          }
        }
      }
    }
    destroy(){
      if(this.destroyed)return;
      this.stop();this.destroyed=true;this.abort.abort();this.resizeObserver.disconnect();this.intersectionObserver.disconnect();
      this.scene.remove();this.shade.remove();this.particles.length=0;
      for(const c of this.canvases){c.el.width=0;c.el.height=0;}
    }
  }
  window.ToreBackground3D=ToreBackground3D;
})();
