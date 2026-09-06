(()=>{
  const mq=window.matchMedia('(max-width: 820px)');
  const layout=document.getElementById('pageLayout');
  const content=layout?.querySelector('.content');
  const rail=document.getElementById('dashboardRail');
  const sidebar=document.getElementById('eventSidebar');
  const newsPanel=document.getElementById('newsPanel');
  const map=document.getElementById('eventMap');
  const agenda=document.getElementById('eventAgenda');
  const clearButton=document.getElementById('limpar');
  const actions=sidebar?.querySelector('.actions');
  const agendaTitle=document.getElementById('agendaTitulo');
  if(!layout||!content||!rail)return;

  const placeClearButton=(mobile)=>{
    if(!clearButton||!actions||!agenda||!agendaTitle)return;
    if(mobile){
      clearButton.textContent='Limpar filtros';
      clearButton.classList.add('mobile-clear-filters');
      if(agendaTitle.nextElementSibling!==clearButton){
        agendaTitle.insertAdjacentElement('afterend',clearButton);
      }
    }else{
      clearButton.textContent='Limpar';
      clearButton.classList.remove('mobile-clear-filters');
      if(clearButton.parentElement!==actions)actions.appendChild(clearButton);
    }
  };

  if(!document.getElementById('mobileClearFiltersStyle')){
    const style=document.createElement('style');
    style.id='mobileClearFiltersStyle';
    style.textContent='@media(max-width:820px){#eventAgenda .mobile-clear-filters{display:block;width:100%;margin:0 0 12px;padding:11px 14px;background:#edf3f0;color:#073f2b}#eventSidebar .actions{grid-template-columns:1fr}}';
    document.head.appendChild(style);
  }

  const place=()=>{
    const mobile=mq.matches;
    const newsMode=!!(newsPanel && !newsPanel.hidden);
    const calendar=document.getElementById('eventCalendar');
    placeClearButton(mobile);

    if(!mobile){
      if(calendar&&map&&calendar.parentElement!==map)map.appendChild(calendar);
      if(rail.parentElement!==layout)layout.appendChild(rail);
      rail.style.margin='';
      return;
    }

    rail.style.margin='0';

    if(newsMode){
      if(rail.parentElement!==layout || layout.firstElementChild!==rail){
        layout.insertBefore(rail,layout.firstElementChild);
      }
      if(newsPanel.parentElement!==layout){
        layout.insertBefore(newsPanel,content);
      }
      if(rail.nextElementSibling!==newsPanel){
        rail.insertAdjacentElement('afterend',newsPanel);
      }
      return;
    }

    if(rail.parentElement!==layout || layout.firstElementChild!==rail){
      layout.insertBefore(rail,layout.firstElementChild);
    }
    if(sidebar&&rail.nextElementSibling!==sidebar){
      rail.insertAdjacentElement('afterend',sidebar);
    }
    if(content&&sidebar&&sidebar.nextElementSibling!==content){
      sidebar.insertAdjacentElement('afterend',content);
    }
    if(map&&map.parentElement===content&&content.firstElementChild!==map){
      content.insertBefore(map,content.firstElementChild);
    }
    if(calendar&&map&&(calendar.parentElement!==content || map.nextElementSibling!==calendar)){
      map.insertAdjacentElement('afterend',calendar);
    }
    if(agenda&&calendar&&calendar.nextElementSibling!==agenda){
      calendar.insertAdjacentElement('afterend',agenda);
    }else if(agenda&&map&&!calendar&&map.nextElementSibling!==agenda){
      map.insertAdjacentElement('afterend',agenda);
    }
  };

  if(clearButton&&clearButton.dataset.clearScroll!=='1'){
    clearButton.dataset.clearScroll='1';
    clearButton.addEventListener('click',()=>{
      setTimeout(()=>sidebar?.scrollIntoView({behavior:'smooth',block:'start'}),0);
    });
  }

  document.getElementById('tabEventos')?.addEventListener('click',()=>setTimeout(place,0));
  document.getElementById('tabNoticias')?.addEventListener('click',()=>setTimeout(place,0));
  mq.addEventListener?.('change',place);
  window.addEventListener('resize',place,{passive:true});
  const observer=new MutationObserver(place);
  if(newsPanel)observer.observe(newsPanel,{attributes:true,attributeFilter:['hidden']});
  if(map)observer.observe(map,{childList:true});
  setTimeout(place,0);setTimeout(place,300);setTimeout(place,900);
})();