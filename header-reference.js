(()=>{
  const style=document.createElement('style');
  style.textContent=`
    .hero-banner{
      width:100%!important;
      height:auto!important;
      min-height:0!important;
      padding:0!important;
      margin:0!important;
      overflow:hidden!important;
      background:#07503b!important;
    }
    .hero-banner::before{display:none!important;content:none!important}
    .hero-banner-inner{
      width:100%!important;
      height:auto!important;
      min-height:0!important;
      max-width:none!important;
      margin:0!important;
      padding:0!important;
      aspect-ratio:1774/194!important;
      display:block!important;
      overflow:hidden!important;
      background:#07503b!important;
    }
    .hero-banner img{
      display:block!important;
      width:100%!important;
      height:100%!important;
      max-width:none!important;
      max-height:none!important;
      margin:0!important;
      padding:0!important;
      object-fit:cover!important;
      object-position:center center!important;
    }
    @media(max-width:820px){
      .hero-banner-inner{
        aspect-ratio:auto!important;
        height:118px!important;
      }
      .hero-banner img{
        width:100%!important;
        height:118px!important;
        object-fit:cover!important;
        object-position:center center!important;
      }
    }
  `;
  document.head.appendChild(style);
  const hero=document.querySelector('.hero-banner img');
  if(hero){
    hero.src='./radar-header-reference.jpg?v=20260905b';
    hero.alt='Radar Brasil 2027 — cabeçalho oficial do Radar';
  }
})();
