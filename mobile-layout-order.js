(()=>{
  const mq=window.matchMedia('(max-width:820px)');
  const layout=document.getElementById('pageLayout');
  const content=layout?.querySelector('.content');
  const rail=document.getElementById('dashboardRail');
  if(!layout||!content||!rail)return;

  const applyOrder=()=>{
    const mobile=mq.matches;
    const newsMode=!document.getElementById('newsPanel')?.hidden;
    if(!mobile){
      if(rail.parentElement!==layout)layout.appendChild(rail);
      return;
    }

    if(newsMode){
      const news=document.getElementById('newsPanel');
      if(news&&rail.parentElement!==content)content.insertBefore(rail,news);
      return;
    }

    const map=document.getElementById('eventMap');
    const agenda=document.getElementById('eventAgenda');
    const calendar=content.querySelector('.event-calendar');

    if(map&&map.parentElement===content&&content.firstElementChild!==map)content.insertBefore(map,content.firstElementChild);
    if(calendar){
      if(calendar.parentElement!==content)content.insertBefore(calendar,agenda||null);
      calendar.insertAdjacentElement('afterend',rail);
    }else if(agenda){
      content.insertBefore(rail,agenda);
    }else if(rail.parentElement!==content){
      content.appendChild(rail);
    }
  };

  const observer=new MutationObserver(()=>applyOrder());
  observer.observe(content,{childList:true,subtree:true});
  mq.addEventListener?.('change',applyOrder);
  window.addEventListener('resize',applyOrder,{passive:true});
  document.getElementById('tabEventos')?.addEventListener('click',()=>setTimeout(applyOrder,0));
  document.getElementById('tabNoticias')?.addEventListener('click',()=>setTimeout(applyOrder,0));
  setTimeout(applyOrder,0);
  setTimeout(applyOrder,500);
  setTimeout(applyOrder,1500);
})();