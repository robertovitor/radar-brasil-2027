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

  function applyBranding(){
    document.title='Radar Brasil 2027 | Mundial Feminino 2027';
    const hero=document.querySelector('.hero-banner img');
    if(hero){hero.src='./Radar%20Brasil%202027_%20O%20Mundo%20Se%20Conecta.png';hero.alt='Radar Brasil 2027 — Mundial Feminino 2027 — O Mundo Se Conecta';}
    document.querySelector('.hero-actions')?.remove();
    const headerText=document.querySelector('header .header-inner > div > p');
    if(headerText)headerText.textContent='Monitoramento de eventos e notícias do Mundial Feminino 2027';
    const newsIntro=document.querySelector('.news-head p');
    if(newsIntro)newsIntro.textContent='Notícias e sinais relevantes sobre o Mundial Feminino 2027.';
    const metaUpdates={
      'meta[name="description"]':'Eventos, notícias e ativações do Mundial Feminino 2027 no Brasil. Acompanhe tudo em um só lugar.',
      'meta[property="og:title"]':'Radar Brasil 2027 | Mundial Feminino 2027',
      'meta[property="og:description"]':'Eventos, notícias e ativações do Mundial Feminino 2027 no Brasil. Acompanhe tudo em um só lugar.',
      'meta[name="twitter:title"]':'Radar Brasil 2027 | Mundial Feminino 2027',
      'meta[name="twitter:description"]':'Eventos, notícias e ativações do Mundial Feminino 2027 no Brasil.'
    };
    Object.entries(metaUpdates).forEach(([selector,value])=>{const el=document.querySelector(selector);if(el)el.setAttribute('content',value);});
  }
  applyBranding();

  const responsiveStyle=document.createElement('style');
  responsiveStyle.textContent=`
    .hero-banner{
      position:relative;
      width:100%;
      height:auto!important;
      min-height:0!important;
      display:block!important;
      padding:0!important;
      overflow:hidden!important;
      background:#071b17;
      isolation:isolate;
    }
    .hero-banner::before{
      content:'';
      position:absolute;
      inset:-24px;
      z-index:-1;
      background-image:linear-gradient(rgba(7,27,23,.28),rgba(7,27,23,.28)),url('./Radar%20Brasil%202027_%20O%20Mundo%20Se%20Conecta.png');
      background-size:cover;
      background-position:center center;
      filter:blur(18px) saturate(.9) brightness(.72);
      transform:scale(1.08);
    }
    .hero-banner-inner{
      position:relative;
      z-index:1;
      width:100%!important;
      height:min(34vw,460px)!important;
      min-height:260px!important;
      max-width:none!important;
      margin:0!important;
      display:flex!important;
      align-items:center!important;
      justify-content:center!important;
      overflow:hidden!important;
      background:transparent!important;
    }
    .hero-banner img{
      display:block;
      width:auto!important;
      height:100%!important;
      max-width:100%!important;
      max-height:460px!important;
      object-fit:contain!important;
      object-position:center center!important;
      margin:0 auto!important;
      cursor:pointer;
    }
    .hero-actions{display:none!important;}

    .map-panel{background:#fff!important;}
    .map-stage{
      background:#fff!important;
      box-shadow:inset 0 0 0 1px rgba(7,63,43,.10);
    }
    .map-stage>img{
      filter:sepia(.38) saturate(7) hue-rotate(92deg) brightness(.72) contrast(1.06)!important;
      opacity:.96;
    }
    .region{
      background:rgba(7,63,43,.88)!important;
      color:#ffdf00!important;
      border:1px solid rgba(255,223,0,.45);
      box-shadow:0 2px 8px rgba(0,0,0,.12);
    }

    @media(max-width:820px){
      .hero-banner{
        height:auto!important;
        min-height:0!important;
        overflow:visible!important;
        background:#071b17!important;
      }
      .hero-banner::before{display:none!important;}
      .hero-banner-inner{
        width:100%!important;
        height:auto!important;
        min-height:0!important;
        display:block!important;
        overflow:visible!important;
      }
      .hero-banner img{
        width:100%!important;
        height:auto!important;
        max-width:100%!important;
        max-height:none!important;
        object-fit:contain!important;
        object-position:center top!important;
      }
      .layout.news-mode{padding:8px}
      .layout.news-mode .content{width:100%;max-width:none;min-width:0}
      .news-panel{padding:14px;min-width:0;overflow:hidden}
      .news-filters{grid-template-columns:1fr!important;gap:9px}
      .news-filters label,.news-filters select,.news-filters input{min-width:0;max-width:100%}
      .news-grid{grid-template-columns:1fr}
      .news-card,.news-feature{min-width:0;padding:10px}
      .news-title,.news-summary,.news-meta{overflow-wrap:anywhere;word-break:normal}
      .news-metrics{grid-template-columns:repeat(2,minmax(0,1fr));min-width:0}
      .news-metric:last-child{grid-column:1/-1}
      .news-actions{display:grid;grid-template-columns:1fr 1fr;justify-content:stretch;margin:0 0 14px}
      .news-action-primary,.news-action-secondary{width:100%;min-width:0;padding:10px 8px}
      .view-tabs{width:100%;max-width:100%}
      .view-tabs .tab-button{flex:1;min-width:0}
    }
    @media(max-width:420px){
      .news-actions{grid-template-columns:1fr}
      .news-metrics{grid-template-columns:1fr}
      .news-metric:last-child{grid-column:auto}
    }
  `;
  document.head.appendChild(responsiveStyle);

  function setupHeroClick(){
    const hero=document.querySelector('.hero-banner');
    const img=hero?.querySelector('img');
    const target=document.querySelector('header');
    if(!hero||!img||!target||hero.dataset.scrollReady==='true')return;
    const go=()=>target.scrollIntoView({behavior:'smooth',block:'start'});
    hero.dataset.scrollReady='true';
    hero.style.cursor='pointer';
    hero.setAttribute('role','button');
    hero.setAttribute('tabindex','0');
    hero.setAttribute('aria-label','Ir para o Radar Brasil 2027 e seus filtros');
    hero.addEventListener('click',go);
    hero.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}});
  }
  setupHeroClick();

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

    const aplicar=document.getElementById('aplicar');
    if(aplicar)aplicar.remove();
    const actions=document.querySelector('.actions');
    if(actions)actions.style.gridTemplateColumns='1fr';
    const limpar=document.getElementById('limpar');
    if(limpar){limpar.style.background='#0b7a4b';limpar.style.color='#fff';}

    ['noticiaLocal','noticiaSentimento'].forEach(id=>{
      const field=document.getElementById(id);
      if(field){field.value='';field.closest('label')?.setAttribute('hidden','');}
    });
    const newsFilters=document.querySelector('.news-filters');
    const syncNewsFilters=()=>{
      if(!newsFilters)return;
      newsFilters.style.gridTemplateColumns=window.matchMedia('(max-width:820px)').matches
        ?'1fr'
        :'minmax(180px,1fr) minmax(150px,.7fr) minmax(240px,1.4fr)';
    };
    syncNewsFilters();
    window.addEventListener('resize',syncNewsFilters,{passive:true});

    ['status','categoria','ano','mes'].forEach(id=>document.getElementById(id)?.addEventListener('change',()=>{
      if(typeof render==='function')render();
    }));
    document.getElementById('busca')?.addEventListener('input',()=>{
      if(typeof render==='function')render();
    });

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
    limpar?.addEventListener('click',()=>setTimeout(()=>{
      rebuildRegions('');rebuildUfs('','');
    },0));
    return true;
  }
  const timer=setInterval(()=>{setupHeroClick();if(setup())clearInterval(timer)},200);
  setTimeout(()=>clearInterval(timer),10000);
})();
