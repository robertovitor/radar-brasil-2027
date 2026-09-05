(()=>{
  const mq=window.matchMedia('(max-width: 820px)');
  const layout=document.getElementById('pageLayout');
  const content=layout?.querySelector('.content');
  const rail=document.getElementById('dashboardRail');
  const sidebar=document.getElementById('eventSidebar');
  const newsPanel=document.getElementById('newsPanel');
  const map=document.getElementById('eventMap');
  const agenda=document.getElementById('eventAgenda');
  if(!layout||!content||!rail)return;

  const place=()=>{
    const mobile=mq.matches;
    const newsMode=newsPanel && !newsPanel.hidden;
    const calendar=document.getElementById('eventCalendar');

    if(!mobile){
      if(calendar&&map&&calendar.parentElement!==map)map.appendChild(calendar);
      if(rail.parentElement!==layout)layout.appendChild(rail);
      rail.style.margin='';
      return;
    }

    rail.style.margin='0';

    if(newsMode){
      // Mobile Notícias: Últimas notícias primeiro, antes dos filtros e do conteúdo.
      if(rail.parentElement!==newsPanel || newsPanel.firstElementChild!==rail){
        newsPanel.insertBefore(rail,newsPanel.firstElementChild);
      }
      return;
    }

    // Mobile Eventos: Próximos eventos primeiro, depois filtros, mapa, calendário e conteúdo.
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

    if(calendar&&map){
      if(calendar.parentElement!==content || map.nextElementSibling!==calendar){
        map.insertAdjacentElement('afterend',calendar);
      }
    }

    if(agenda&&calendar&&calendar.nextElementSibling!==agenda){
      calendar.insertAdjacentElement('afterend',agenda);
    }else if(agenda&&map&&!calendar&&map.nextElementSibling!==agenda){
      map.insertAdjacentElement('afterend',agenda);
    }
  };

  document.getElementById('tabEventos')?.addEventListener('click',()=>setTimeout(place,0));
  document.getElementById('tabNoticias')?.addEventListener('click',()=>setTimeout(place,0));
  mq.addEventListener?.('change',place);
  window.addEventListener('resize',place,{passive:true});

  const observer=new MutationObserver(()=>place());
  if(newsPanel)observer.observe(newsPanel,{attributes:true,attributeFilter:['hidden']});
  if(map)observer.observe(map,{childList:true});

  setTimeout(place,0);
  setTimeout(place,400);
  setTimeout(place,1200);
})();