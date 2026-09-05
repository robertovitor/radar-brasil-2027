(()=>{
  const status=document.getElementById('status');
  if(!status)return;

  const normalizeStatus=()=>{
    const current=status.value;
    const allowed=['','Planejado','Realizado'];
    [...status.options].forEach(o=>{if(!allowed.includes(o.value))o.remove()});
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

  // Todos os filtros de Eventos passam a atualizar imediatamente.
  ['status','categoria','regiao','uf','ano','mes'].forEach(id=>{
    const el=document.getElementById(id);
    if(!el||el.dataset.liveFilterFix==='1')return;
    el.dataset.liveFilterFix='1';
    el.addEventListener('change',()=>setTimeout(apply,0));
  });

  // Busca também atualiza sem depender de Enter/botão Aplicar.
  const busca=document.getElementById('busca');
  if(busca&&busca.dataset.liveFilterFix!=='1'){
    busca.dataset.liveFilterFix='1';
    let timer;
    busca.addEventListener('input',()=>{
      clearTimeout(timer);
      timer=setTimeout(apply,180);
    });
  }

  const wait=setInterval(()=>{
    try{
      if(Array.isArray(window.EVENTS)&&window.EVENTS.length){
        normalizeStatus();
        clearInterval(wait);
        apply();
      }
    }catch(e){}
  },200);
  setTimeout(()=>clearInterval(wait),10000);
})();