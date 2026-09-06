(()=>{
  const stage=document.getElementById('mapStage');
  if(!stage||stage.querySelector('.region-color-overlay')) return;

  const wrap=document.createElement('div');
  wrap.className='region-color-overlay';
  Object.assign(wrap.style,{
    position:'absolute',inset:'0',zIndex:'2',pointerEvents:'none',overflow:'hidden',borderRadius:'12px'
  });

  const make=(name,color,clip)=>{
    const el=document.createElement('div');
    el.setAttribute('aria-hidden','true');
    el.dataset.region=name;
    Object.assign(el.style,{
      position:'absolute',inset:'0',background:color,opacity:'0.11',
      mixBlendMode:'multiply',clipPath:`polygon(${clip})`,WebkitClipPath:`polygon(${clip})`
    });
    wrap.appendChild(el);
  };

  // Polígonos deliberadamente recuados para permanecer dentro da silhueta do Brasil.
  make('Norte','#1b9e4b','10% 15%, 39% 8%, 57% 16%, 60% 31%, 54% 43%, 43% 44%, 34% 51%, 21% 52%, 10% 42%');
  make('Nordeste','#e53935','68% 24%, 90% 27%, 94% 43%, 87% 54%, 75% 54%, 69% 47%, 66% 35%');
  make('Centro-Oeste','#fb8c00','37% 48%, 61% 49%, 68% 60%, 63% 71%, 51% 74%, 41% 67%, 35% 58%');
  make('Sudeste','#f4df00','66% 62%, 86% 61%, 86% 75%, 75% 81%, 61% 77%, 58% 70%');
  make('Sul','#6f5bd3','52% 79%, 65% 84%, 62% 94%, 50% 94%, 47% 88%');

  stage.appendChild(wrap);
})();
