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
      background:#fff!important;
    }
    .hero-banner::before{display:none!important;content:none!important}
    .hero-banner-inner{
      width:100%!important;
      height:auto!important;
      min-height:0!important;
      max-width:none!important;
      margin:0!important;
      padding:0!important;
      display:block!important;
      overflow:hidden!important;
      background:#fff!important;
    }
    .hero-banner img{
      display:block!important;
      width:100%!important;
      height:auto!important;
      max-width:100%!important;
      max-height:none!important;
      margin:0!important;
      padding:0!important;
      object-fit:contain!important;
      object-position:center top!important;
    }
    @media(max-width:820px){
      .hero-banner,
      .hero-banner-inner{
        height:auto!important;
        min-height:0!important;
      }
      .hero-banner img{
        width:100%!important;
        height:auto!important;
        object-fit:contain!important;
        object-position:center top!important;
      }
    }
  `;
  document.head.appendChild(style);
  const hero=document.querySelector('.hero-banner img');
  if(hero){
    hero.src='./cabecalho.png?v=20260905c';
    hero.alt='Radar Brasil 2027';
  }
})();
