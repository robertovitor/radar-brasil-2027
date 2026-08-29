(()=>{
  const style=document.createElement('style');
  style.textContent=`
  .map-panel{display:grid;grid-template-columns:minmax(0,1fr) minmax(330px,430px);gap:14px;align-items:start}
  .map-stage{width:min(100%,calc(76vh * 727 / 702))}
  .event-calendar{border:1px solid var(--border);border-radius:12px;background:#fff;overflow:hidden;min-width:0}
  .calendar-head{display:grid;grid-template-columns:auto 1fr auto auto;gap:6px;align-items:center;padding:10px;border-bottom:1px solid var(--border)}
  .calendar-head button{background:#edf3f0;color:#073f2b;padding:8px 10px}.calendar-head button:hover{background:#dce9e3}
  .calendar-title{font-size:16px;text-align:center;margin:0;color:#14211d}
  .calendar-today{font-size:11px!important;padding:8px!important}
  .calendar-weekdays,.calendar-grid{display:grid;grid-template-columns:repeat(7,1fr)}
  .calendar-weekdays{border-bottom:1px solid var(--border);background:#f8faf9}
  .calendar-weekdays span{text-align:center;padding:8px 2px;font-size:10px;font-weight:bold;color:var(--muted)}
  .calendar-day{position:relative;min-width:0;min-height:92px;padding:5px;border-right:1px solid #edf2ef;border-bottom:1px solid #edf2ef;background:#fff;color:var(--text);cursor:pointer;overflow:hidden}
  .calendar-day:hover{background:#f2f8f5}.calendar-day.outside{color:#a9b2ae;background:#fafbfb}.calendar-day.today .day-number{background:#0b7a4b;color:#fff}.calendar-day.selected{box-shadow:inset 0 0 0 2px #0b7a4b;background:#eef8f3}.calendar-day:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
  .day-number{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;font-size:11px}
  .day-labels{display:grid;gap:3px;margin-top:4px;min-width:0}
  .event-label{display:block;width:100%;min-width:0;padding:4px 5px;border-radius:5px;background:#fff1c9;color:#604600;font-size:9px;font-weight:bold;line-height:1.15;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .event-label.realizado{background:#e2e9fb;color:#274681}.event-label:hover{filter:brightness(.96)}
  .more-events{font-size:9px;font-weight:bold;color:var(--muted);padding:1px 3px}
  .mobile-dots{display:none;gap:3px;flex-wrap:wrap;margin-top:5px}.day-dot{width:7px;height:7px;border-radius:50%;background:#d79b00}.day-dot.realizado{background:#3465d9}
  .calendar-note{padding:9px 11px;font-size:11px;color:var(--muted);background:#fbfdfc}.calendar-note strong{color:#073f2b}
  @media(max-width:1180px){.map-panel{grid-template-columns:1fr}.event-calendar{max-width:760px;width:100%;margin:0 auto}.calendar-day{min-height:88px}}
  @media(max-width:620px){.calendar-day{min-height:55px;padding:4px}.day-labels{display:none}.mobile-dots{display:flex}.calendar-head{grid-template-columns:auto 1fr auto}.calendar-today{grid-column:1/-1}.calendar-title{font-size:14px}}
  `;
  document.head.appendChild(style);

  let selectedDate='';
  let selectedEventId='';
  let viewDate=new Date();
  const monthNames=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  const monthShort=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const weekdays=['DOM','SEG','TER','QUA','QUI','SEX','SÁB'];
  const pad=n=>String(n).padStart(2,'0');
  const iso=(y,m,d)=>`${y}-${pad(m+1)}-${pad(d)}`;
  const parseDate=s=>{const [y,m,d]=String(s||'').split('-').map(Number);return y&&m&&d?new Date(y,m-1,d):null};

  function filteredWithoutCalendar(e){
    const q=document.getElementById('busca').value.trim().toLowerCase();
    const value=id=>document.getElementById(id).value;
    return (!value('status')||e.Status===value('status'))&&
      (!value('categoria')||categoryGroup(e.Categoria)===value('categoria'))&&
      (!value('regiao')||e.Regiao===value('regiao'))&&
      (!value('uf')||e.UF===value('uf'))&&
      (!q||(`${e.Titulo||''} ${e.Cidade} ${e.Categoria} ${e.ID}`).toLowerCase().includes(q));
  }

  function createCalendar(){
    const map=document.getElementById('eventMap');
    if(!map||document.getElementById('eventCalendar')) return;
    const panel=document.createElement('aside');
    panel.id='eventCalendar';panel.className='event-calendar';panel.setAttribute('aria-label','Calendário de eventos');
    panel.innerHTML=`<div class="calendar-head"><button id="calPrev" type="button" aria-label="Mês anterior">‹</button><h2 class="calendar-title" id="calTitle"></h2><button id="calNext" type="button" aria-label="Próximo mês">›</button><button id="calToday" class="calendar-today" type="button">Hoje</button></div><div class="calendar-weekdays">${weekdays.map(w=>`<span>${w}</span>`).join('')}</div><div class="calendar-grid" id="calGrid"></div><div class="calendar-note" id="calNote">Clique em uma data para filtrar os eventos.</div>`;
    map.appendChild(panel);
    document.getElementById('calPrev').addEventListener('click',()=>changeMonth(-1));
    document.getElementById('calNext').addEventListener('click',()=>changeMonth(1));
    document.getElementById('calToday').addEventListener('click',()=>{viewDate=new Date();selectedDate='';selectedEventId='';syncMonthFilters();renderCalendar();render();});
  }

  function changeMonth(delta){
    viewDate=new Date(viewDate.getFullYear(),viewDate.getMonth()+delta,1);selectedDate='';selectedEventId='';syncMonthFilters();renderCalendar();render();
  }
  function syncMonthFilters(){
    const ano=document.getElementById('ano'),mes=document.getElementById('mes');
    const y=String(viewDate.getFullYear()),m=monthShort[viewDate.getMonth()];
    if([...ano.options].some(o=>o.value===y||o.text===y)) ano.value=y; else ano.value='';
    if([...mes.options].some(o=>o.value===m||o.text===m)) mes.value=m; else mes.value='';
  }
  function selectDay(d,key){
    viewDate=new Date(d.getFullYear(),d.getMonth(),1);
    selectedEventId='';
    selectedDate=selectedDate===key?'':key;
    document.getElementById('ano').value='';document.getElementById('mes').value='';
    renderCalendar();render();document.getElementById('eventAgenda').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function selectEvent(event,d,key,clickEvent){
    clickEvent.stopPropagation();
    viewDate=new Date(d.getFullYear(),d.getMonth(),1);
    selectedDate=key;selectedEventId=String(event.ID||'');
    document.getElementById('ano').value='';document.getElementById('mes').value='';
    renderCalendar();render();document.getElementById('eventAgenda').scrollIntoView({behavior:'smooth',block:'start'});
  }

  function renderCalendar(){
    const grid=document.getElementById('calGrid');if(!grid) return;
    const y=viewDate.getFullYear(),m=viewDate.getMonth();
    document.getElementById('calTitle').textContent=`${monthNames[m]} de ${y}`;
    const first=new Date(y,m,1),start=new Date(y,m,1-first.getDay());
    const today=todayInBrazil();
    const counts={};
    EVENTS.filter(filteredWithoutCalendar).forEach(e=>{if(e.Data) counts[e.Data]=(counts[e.Data]||[]).concat(e)});
    grid.replaceChildren();
    for(let i=0;i<42;i++){
      const d=new Date(start);d.setDate(start.getDate()+i);
      const key=iso(d.getFullYear(),d.getMonth(),d.getDate());
      const events=(counts[key]||[]).sort((a,b)=>String(a.Titulo||a.Categoria).localeCompare(String(b.Titulo||b.Categoria),'pt-BR'));
      const cell=document.createElement('div');cell.className='calendar-day';cell.tabIndex=0;cell.setAttribute('role','button');
      if(d.getMonth()!==m)cell.classList.add('outside');if(key===today)cell.classList.add('today');if(key===selectedDate)cell.classList.add('selected');
      cell.setAttribute('aria-label',`${d.toLocaleDateString('pt-BR')}: ${events.length} evento${events.length===1?'':'s'}`);
      const num=document.createElement('span');num.className='day-number';num.textContent=d.getDate();cell.appendChild(num);
      if(events.length){
        const labels=document.createElement('div');labels.className='day-labels';
        events.slice(0,2).forEach(event=>{
          const label=document.createElement('button');label.type='button';label.className='event-label'+(event.Status==='Realizado'?' realizado':'');
          label.textContent=event.Titulo||event.Categoria||'Evento';label.title=event.Titulo||event.Categoria||'Evento';
          label.setAttribute('aria-label',`Filtrar evento: ${event.Titulo||event.Categoria||'Evento'}`);
          label.addEventListener('click',ev=>selectEvent(event,d,key,ev));labels.appendChild(label);
        });
        if(events.length>2){const more=document.createElement('span');more.className='more-events';more.textContent=`+${events.length-2} evento${events.length-2===1?'':'s'}`;labels.appendChild(more)}
        cell.appendChild(labels);
        const dots=document.createElement('div');dots.className='mobile-dots';events.slice(0,4).forEach(event=>{const dot=document.createElement('span');dot.className='day-dot'+(event.Status==='Realizado'?' realizado':'');dots.appendChild(dot)});cell.appendChild(dots);
      }
      cell.addEventListener('click',()=>selectDay(d,key));
      cell.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();selectDay(d,key)}});
      grid.appendChild(cell);
    }
    const note=document.getElementById('calNote');
    if(selectedEventId){const event=EVENTS.find(e=>String(e.ID||'')===selectedEventId);note.innerHTML=`Filtrando <strong>${esc(event?.Titulo||event?.Categoria||'evento selecionado')}</strong>. Clique na data para ver todos os eventos do dia.`}
    else if(selectedDate) note.innerHTML=`Filtrando <strong>${parseDate(selectedDate).toLocaleDateString('pt-BR')}</strong>. Clique novamente na data para mostrar o mês.`;
    else note.textContent='Clique no nome de um evento para abri-lo ou em uma data para filtrar o dia. Use ‹ e › para navegar.';
  }

  const originalOk=window.ok;
  window.ok=function(e){return originalOk(e)&&(!selectedDate||e.Data===selectedDate)&&(!selectedEventId||String(e.ID||'')===selectedEventId)};
  const originalRender=window.render;
  window.render=function(){originalRender();renderCalendar()};

  function clearCalendarSelection(){selectedDate='';selectedEventId='';renderCalendar();}
  ['status','categoria','regiao','uf','ano','mes'].forEach(id=>document.getElementById(id)?.addEventListener('change',clearCalendarSelection));
  document.getElementById('aplicar')?.addEventListener('click',clearCalendarSelection);
  document.getElementById('limpar')?.addEventListener('click',()=>{selectedDate='';selectedEventId='';viewDate=new Date();renderCalendar()});

  createCalendar();
  const ready=setInterval(()=>{
    if(Array.isArray(window.EVENTS)&&window.EVENTS.length){clearInterval(ready);const planned=window.EVENTS.filter(e=>e.Status==='Planejado'&&e.Data).sort((a,b)=>a.Data.localeCompare(b.Data))[0];const d=planned?parseDate(planned.Data):new Date();if(d)viewDate=new Date(d.getFullYear(),d.getMonth(),1);renderCalendar();}
  },250);
  setTimeout(()=>clearInterval(ready),10000);

  // Mantém Região e UF sincronizados e elimina opções vazias indevidas.
  const UF_TO_REGION={
    AC:'Norte',AP:'Norte',AM:'Norte',PA:'Norte',RO:'Norte',RR:'Norte',TO:'Norte',
    AL:'Nordeste',BA:'Nordeste',CE:'Nordeste',MA:'Nordeste',PB:'Nordeste',PE:'Nordeste',PI:'Nordeste',RN:'Nordeste',SE:'Nordeste',
    DF:'Centro-Oeste',GO:'Centro-Oeste',MT:'Centro-Oeste',MS:'Centro-Oeste',
    ES:'Sudeste',MG:'Sudeste',RJ:'Sudeste',SP:'Sudeste',
    PR:'Sul',RS:'Sul',SC:'Sul'
  };
  function regionKey(value){
    return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z]/g,'');
  }
  function matchingRegionOption(region){
    const select=document.getElementById('regiao');
    const wanted=regionKey(region);
    return [...select.options].find(o=>o.value&&regionKey(o.value)===wanted)?.value||'';
  }
  function cleanRegionOptions(){
    const select=document.getElementById('regiao');
    if(!select)return;
    [...select.options].forEach((option,index)=>{
      if(index>0&&!String(option.value||'').trim()&&!String(option.textContent||'').trim())option.remove();
    });
  }
  function availableUfs(region=''){
    const wanted=regionKey(region);
    return BRAZIL_UFS.filter(uf=>{
      if(wanted&&regionKey(UF_TO_REGION[uf])!==wanted)return false;
      return EVENTS.some(e=>String(e.UF||'').toUpperCase()===uf);
    });
  }
  function rebuildUf(region='',selected=''){
    const select=document.getElementById('uf');
    if(!select)return;
    const options=availableUfs(region);
    select.replaceChildren();
    const all=document.createElement('option');all.value='';all.textContent='Todas';select.appendChild(all);
    options.forEach(uf=>{const option=document.createElement('option');option.value=uf;option.textContent=uf;select.appendChild(option)});
    select.value=options.includes(selected)?selected:'';
  }
  function setupRegionUfLink(){
    const regiao=document.getElementById('regiao'),uf=document.getElementById('uf');
    if(!regiao||!uf||regiao.dataset.ufLinked==='true')return;
    cleanRegionOptions();
    regiao.dataset.ufLinked='true';
    regiao.addEventListener('change',()=>{
      rebuildUf(regiao.value,'');
      clearCalendarSelection();
      render();
    });
    uf.addEventListener('change',()=>{
      const selectedUf=uf.value;
      if(selectedUf){
        const region=matchingRegionOption(UF_TO_REGION[selectedUf]);
        if(region)regiao.value=region;
        rebuildUf(regiao.value,selectedUf);
      }else{
        rebuildUf(regiao.value,'');
      }
      clearCalendarSelection();
      render();
    });
    const limpar=document.getElementById('limpar');
    limpar?.addEventListener('click',()=>setTimeout(()=>{cleanRegionOptions();rebuildUf('','');},0));
  }
  const regionUfReady=setInterval(()=>{
    const regiao=document.getElementById('regiao'),uf=document.getElementById('uf');
    if(!Array.isArray(window.EVENTS)||!window.EVENTS.length||!regiao||regiao.options.length<2||!uf||uf.options.length<2)return;
    clearInterval(regionUfReady);cleanRegionOptions();setupRegionUfLink();
  },250);
  setTimeout(()=>clearInterval(regionUfReady),10000);

  // Simplifica o filtro de Tema das Notícias sem alterar o campo Tema dos dados.
  const NEWS_THEME_GROUPS=[
    'Seleção Brasileira',
    'Seleções de Base',
    'Cidades-sede, Estádios e Infraestrutura',
    'Organização, Governança e Legislação',
    'Marketing, Patrocínios e Negócios',
    'Ativações, Voluntariado e Experiência',
    'Legado, Inclusão e Impacto Social',
    'Outros'
  ];
  function newsThemeGroup(theme){
    const v=String(theme||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    if(/selec(oes|ao) de base|sub[ -]?(15|16|17|18|19|20|23)/.test(v))return'Seleções de Base';
    if(/selecao brasileira|data fifa|amistoso|convocacao|preparacao da selecao/.test(v))return'Seleção Brasileira';
    if(/cidade.?sede|estadio|arena|infraestrutura|mobilidade|operacao|workshop de cidades/.test(v))return'Cidades-sede, Estádios e Infraestrutura';
    if(/governanca|legislacao|tribut|politica publica|beneficio fiscal|fifa|cbf|organizacao|planejamento institucional/.test(v))return'Organização, Governança e Legislação';
    if(/marketing|patrocin|negocio|audiencia|marca|comercial|direitos de transmissao|midia/.test(v))return'Marketing, Patrocínios e Negócios';
    if(/ativacao|tour da taca|voluntari|fan fest|experiencia|torcedor|promocao|engajamento/.test(v))return'Ativações, Voluntariado e Experiência';
    if(/legado|inclus|mulher|seguranca|social|sustent|diversidade|protecao/.test(v))return'Legado, Inclusão e Impacto Social';
    return'Outros';
  }
  const originalNewsOk=window.newsOk;
  window.newsOk=function(n){
    const selected=document.getElementById('noticiaTema')?.value||'';
    if(!selected)return originalNewsOk(n);
    const select=document.getElementById('noticiaTema');
    const saved=select.value;
    select.value='';
    const base=originalNewsOk(n);
    select.value=saved;
    return base&&newsThemeGroup(n.Tema)===selected;
  };
  const newsFilterReady=setInterval(()=>{
    const select=document.getElementById('noticiaTema');
    if(!select||select.options.length<2||!Array.isArray(NEWS)||!NEWS.length)return;
    clearInterval(newsFilterReady);
    const groups=NEWS_THEME_GROUPS.filter(group=>NEWS.some(n=>newsThemeGroup(n.Tema)===group));
    select.replaceChildren();
    const all=document.createElement('option');all.value='';all.textContent='Todos';select.appendChild(all);
    groups.forEach(group=>{const option=document.createElement('option');option.value=group;option.textContent=group;select.appendChild(option)});
    renderNews();
  },250);
  setTimeout(()=>clearInterval(newsFilterReady),10000);
})();
