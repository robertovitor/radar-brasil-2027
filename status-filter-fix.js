(()=>{
  const status=document.getElementById('status');
  if(!status||status.dataset.liveStatusFix==='1')return;
  status.dataset.liveStatusFix='1';

  const normalize=()=>{
    const current=status.value;
    const allowed=['','Planejado','Realizado'];
    [...status.options].forEach(o=>{
      if(!allowed.includes(o.value))o.remove();
    });
    const ensure=(value,label)=>{
      if(![...status.options].some(o=>o.value===value)){
        const o=document.createElement('option');o.value=value;o.textContent=label;status.appendChild(o);
      }
    };
    ensure('','Todos');ensure('Planejado','Planejado');ensure('Realizado','Realizado');
    status.value=allowed.includes(current)?current:'Planejado';
  };

  const apply=()=>{
    if(typeof window.render==='function')window.render();
  };

  status.addEventListener('change',apply);
  const wait=setInterval(()=>{
    try{
      if(Array.isArray(window.EVENTS)&&window.EVENTS.length){normalize();clearInterval(wait);apply();}
    }catch(e){}
  },200);
  setTimeout(()=>clearInterval(wait),10000);
})();