(()=>{
  const REGIONS=[
    {value:'Nacional',label:'Brasil'},
    {value:'Norte',label:'Norte'},
    {value:'Nordeste',label:'Nordeste'},
    {value:'Centro-Oeste',label:'Centro-Oeste'},
    {value:'Sudeste',label:'Sudeste'},
    {value:'Sul',label:'Sul'}
  ];
  const UF_TO_REGION={
    AC:'Norte',AP:'Norte',AM:'Norte',PA:'Norte',RO:'Norte',RR:'Norte',TO:'Norte',
    AL:'Nordeste',BA:'Nordeste',CE:'Nordeste',MA:'Nordeste',PB:'Nordeste',PE:'Nordeste',PI:'Nordeste',RN:'Nordeste',SE:'Nordeste',
    DF:'Centro-Oeste',GO:'Centro-Oeste',MT:'Centro-Oeste',MS:'Centro-Oeste',
    ES:'Sudeste',MG:'Sudeste',RJ:'Sudeste',SP:'Sudeste',
    PR:'Sul',RS:'Sul',SC:'Sul'
  };
  const ALL_UFS=['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
  const key=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z]/g,'');

  function rebuildRegions(selected=''){
    const select=document.getElementById('regiao');if(!select)return;
    select.replaceChildren();
    const all=document.createElement('option');all.value='';all.textContent='Todas';select.appendChild(all);
    REGIONS.forEach(r=>{const o=document.createElement('option');o.value=r.value;o.textContent=r.label;select.appendChild(o)});
    if([...select.options].some(o=>o.value===selected))select.value=selected;
  }
  function rebuildUfs(region='',selected=''){
    const select=document.getElementById('uf');if(!select)return;
    const wanted=key(region);
    const options=ALL_UFS.filter(uf=>!wanted||wanted==='nacional'||key(UF_TO_REGION[uf])===wanted);
    select.replaceChildren();
    const all=document.createElement('option');all.value='';all.textContent='Todas';select.appendChild(all);
    options.forEach(uf=>{const o=document.createElement('option');o.value=uf;o.textContent=uf;select.appendChild(o)});
    if(options.includes(selected))select.value=selected;
  }
  function setup(){
    const regiao=document.getElementById('regiao'),uf=document.getElementById('uf');
    if(!regiao||!uf||regiao.dataset.geoFixed==='true')return false;
    const selectedRegion=regiao.value,selectedUf=uf.value;
    rebuildRegions(selectedRegion==='Brasil'?'Nacional':selectedRegion);
    rebuildUfs(regiao.value,selectedUf);
    regiao.dataset.geoFixed='true';

    // Executa depois dos listeners antigos para garantir a lista completa solicitada.
    regiao.addEventListener('change',()=>setTimeout(()=>{
      rebuildUfs(regiao.value,'');
      if(typeof render==='function')render();
    },0));
    uf.addEventListener('change',()=>setTimeout(()=>{
      const chosen=uf.value;
      if(chosen){
        const target=UF_TO_REGION[chosen];
        const option=[...regiao.options].find(o=>key(o.value)===key(target));
        if(option)regiao.value=option.value;
        rebuildUfs(regiao.value,chosen);
      }
      if(typeof render==='function')render();
    },0));
    document.getElementById('limpar')?.addEventListener('click',()=>setTimeout(()=>{
      rebuildRegions('');rebuildUfs('','');
    },0));
    return true;
  }
  const timer=setInterval(()=>{if(setup())clearInterval(timer)},200);
  setTimeout(()=>clearInterval(timer),10000);
})();
