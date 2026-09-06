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
      position:'absolute',inset:'0',background:color,opacity:'0.14',
      mixBlendMode:'multiply',clipPath:`polygon(${clip})`,WebkitClipPath:`polygon(${clip})`
    });
    wrap.appendChild(el);
  };

  make('Norte','#1b9e4b','3% 10%, 42% 2%, 62% 13%, 65% 34%, 57% 49%, 42% 48%, 33% 57%, 18% 59%, 3% 45%');
  make('Nordeste','#e53935','64% 19%, 95% 22%, 99% 47%, 91% 61%, 73% 60%, 66% 48%, 62% 34%');
  make('Centro-Oeste','#fb8c00','33% 45%, 65% 47%, 73% 61%, 67% 76%, 50% 79%, 37% 70%, 31% 58%');
  make('Sudeste','#f4df00','64% 60%, 91% 58%, 90% 80%, 73% 86%, 57% 80%, 55% 72%');
  make('Sul','#6f5bd3','50% 77%, 69% 83%, 66% 100%, 47% 100%, 43% 89%');

  stage.appendChild(wrap);
})();
