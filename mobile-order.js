(()=>{
  const mq=window.matchMedia('(max-width: 820px)');
  const layout=document.getElementById('pageLayout');
  const content=layout?.querySelector('.content');
  const rail=document.getElementById('dashboardRail');
  const sidebar=document.getElementById('eventSidebar');
  const newsPanel=document.getElementById('newsPanel');
  if(!layout||!content||!rail)return;

  const place=()=>{
    const mobile=mq.matches;
    const newsMode=newsPanel && !newsPanel.hidden;
    if(!mobile){
      if(rail.parentElement!==layout)layout.appendChild(rail);
      rail.style.margin='';
      return;
    }
    rail.style.margin='0';
    if(newsMode){
      const newsFilters=newsPanel.querySelector('.news-filters');
      const newsActions=newsPanel.querySelector('.news-actions');
      const anchor=newsActions||newsFilters;
      if(anchor){anchor.insertAdjacentElement('afterend',rail)}else{newsPanel.prepend(rail)}
    }else{
      if(sidebar && sidebar.parentElement===layout){sidebar.insertAdjacentElement('afterend',rail)}
      else if(rail.parentElement!==layout){layout.insertBefore(rail,content)}
    }
  };

  document.getElementById('tabEventos')?.addEventListener('click',()=>setTimeout(place,0));
  document.getElementById('tabNoticias')?.addEventListener('click',()=>setTimeout(place,0));
  mq.addEventListener?.('change',place);
  window.addEventListener('resize',place,{passive:true});
  const observer=new MutationObserver(place);
  if(newsPanel)observer.observe(newsPanel,{attributes:true,attributeFilter:['hidden']});
  setTimeout(place,0);
})();