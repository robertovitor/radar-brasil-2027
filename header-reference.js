(()=>{
  const section=document.querySelector('.hero-banner');
  const inner=document.querySelector('.hero-banner-inner');
  const hero=document.querySelector('.hero-banner img');

  const force=(el,props)=>{
    if(!el)return;
    Object.entries(props).forEach(([k,v])=>el.style.setProperty(k,v,'important'));
  };

  document.documentElement.style.setProperty('margin','0','important');
  document.documentElement.style.setProperty('padding','0','important');
  document.body.style.setProperty('margin','0','important');
  document.body.style.setProperty('padding','0','important');

  force(section,{
    'width':'100%',
    'height':'auto',
    'min-height':'0',
    'max-height':'none',
    'margin':'0',
    'padding':'0',
    'display':'block',
    'overflow':'hidden',
    'line-height':'0',
    'background':'transparent',
    'position':'relative',
    'top':'auto',
    'bottom':'auto'
  });

  force(inner,{
    'width':'100%',
    'height':'auto',
    'min-height':'0',
    'max-height':'none',
    'margin':'0',
    'padding':'0',
    'display':'block',
    'overflow':'hidden',
    'line-height':'0',
    'background':'transparent',
    'position':'relative',
    'top':'auto',
    'bottom':'auto'
  });

  force(hero,{
    'display':'block',
    'width':'100%',
    'height':'auto',
    'min-height':'0',
    'max-height':'none',
    'max-width':'100%',
    'margin':'0',
    'padding':'0',
    'object-fit':'contain',
    'object-position':'center top',
    'vertical-align':'top'
  });

  if(hero){
    hero.src='./cabecalho.png?v=20260909e';
    hero.alt='Radar Brasil 2027 — Todo o futebol feminino, em todo o Brasil';
  }

  document.querySelector('.hero-actions')?.remove();

  if(section && document.body.firstElementChild!==section){
    document.body.insertBefore(section,document.body.firstElementChild);
  }

  const header=document.querySelector('body > header');
  force(header,{'margin':'0','top':'auto'});
})();
