(()=>{
  const map=document.querySelector('#mapStage > img');
  if(map){
    map.src='./mapa-brasil-regioes.jpg?v=20260906a';
    map.alt='Mapa do Brasil colorido por regiões: Norte, Nordeste, Centro-Oeste, Sudeste e Sul';
  }
  document.querySelectorAll('#mapStage > .region').forEach(el=>el.remove());
})();
