(() => {
  const preset=document.body.dataset.preset||'FORUM';
  document.body.classList.add(preset.toLowerCase());
  const copy={
    HERO:['Liège · Folklore · Héritage','La Cité<br><em>ardente.</em>','Un même feu. Une même ville. Un folklore qui nous rassemble.'],
    FORUM:['Le forum TORÈ','Le feu<br><em>nous rassemble.</em>','Les voix, les histoires et les rendez-vous de la communauté liégeoise.'],
    DASHBOARD:['Votre espace TORÈ','Au cœur de<br><em>la communauté.</em>','Un espace calme pour garder le fil de la vie du forum.']
  }[preset];
  document.querySelector('.eyebrow').textContent=copy[0];
  document.querySelector('h1').innerHTML=copy[1];
  document.querySelector('.intro').textContent=copy[2];
  document.querySelectorAll('[data-preset-link]').forEach(a=>{if(a.dataset.presetLink===preset)a.setAttribute('aria-current','page');});
  if(preset==='DASHBOARD')document.querySelector('.stats').hidden=false;
  window.toreBackground=new ToreBackground3D(document.querySelector('#tore-background'),{...ToreBackground3D.presets[preset],quality:'auto'});
  const pulse=document.querySelector('#pulse'),motion=document.querySelector('#motion'),clean=document.querySelector('#clean');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function motionState(){
    motion.disabled=reduced.matches;
    motion.textContent=reduced.matches?'Mouvement réduit':toreBackground.wanted?'Mettre en pause':'Reprendre';
    motion.setAttribute('aria-pressed',String(!toreBackground.wanted||reduced.matches));
    pulse.disabled=preset==='DASHBOARD'||reduced.matches;
  }
  reduced.addEventListener('change',motionState);motionState();
  pulse.addEventListener('click',()=>toreBackground.triggerPulse());
  motion.addEventListener('click',()=>{toreBackground.wanted?toreBackground.stop():toreBackground.start();motionState();});
  clean.addEventListener('click',()=>{const on=document.body.classList.toggle('clean');clean.textContent=on?'Afficher l’interface':'Voir le décor seul';clean.setAttribute('aria-pressed',String(on));});
  document.querySelector('#quality').addEventListener('change',e=>toreBackground.setQuality(e.target.value));
})();
