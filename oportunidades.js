(()=>{const s=document.createElement('style');s.id='opp-title-link-style';s.textContent='.title-source-link{color:inherit;text-decoration:none;cursor:pointer}.title-source-link:hover,.title-source-link:focus{text-decoration:underline;text-underline-offset:2px}';document.head.appendChild(s)})();
(() => {
'use strict';
let O=[];
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
function group(v){const x=norm(v);if(x.includes('volunt'))return'Voluntariado';if(/trabalho|vaga|emprego|estagio/.test(x))return'Trabalho';if(/curso|capacit|formacao|mentoria/.test(x))return'Cursos e capacitações';if(/summit|congres|forum|workshop|semin/.test(x))return'Congressos e encontros';if(/chamada|submiss|programa/.test(x))return'Chamadas e programas';if(/seletiva|peneira|avaliacao/.test(x))return'Seletivas';return'Outros'}
function days(v){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(v||'')))return null;const t=new Date(new Date().toLocaleString('en-US',{timeZone:'America/Sao_Paulo'}));t.setHours(0,0,0,0);const[y,m,d]=v.split('-').map(Number);return Math.round((new Date(y,m-1,d)-t)/86400000)}
function status(o){const d=days(o.PrazoInscricao);if(d!==null){if(d<0)return'Encerrada';if(d<=7)return'Encerra em breve'}return o.Status||'Inscrições abertas'}
function dateBR(v){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(v||'')))return'';const[y,m,d]=v.split('-');return`${d}/${m}/${y}`}

/* Tradução apenas na exibição; fontes, IDs, JSON e publicações permanecem inalterados. */
const TITULOS_PT={
  "OPP-FIFA-TRAVEL-MANAGER": "Gerente de viagens — Copa do Mundo Feminina 2027",
  "OPP-B9B1541FAA8C": "Coordenador(a) de contas a pagar",
  "OPP-835DE9B778D7": "Gerente de sistemas e aplicativos de controle de acesso",
  "OPP-336E2CEE16B3": "Gerente de contabilidade",
  "OPP-AA57D46617F8": "Gerente de proteção de dados",
  "OPP-19143673F85F": "Gerente de produtos digitais",
  "OPP-6E5F015CBAB5": "Gerente de ambientação e design de sinalização",
  "OPP-22D98C0F8115": "Gerente de sinalização funcional e materiais",
  "OPP-E11CA9D08983": "Gerente de hospitalidade e infraestrutura — 6 cidades-sede (Brasil)",
  "OPP-712A8CC1CC59": "Coordenador(a) de operações de transmissão oficial",
  "OPP-90291D6CA9FA": "Gerente de serviços de televisão IPTV e CATV",
  "OPP-8604CFBF1238": "Coordenador(a) de relações institucionais",
  "OPP-E9BE5D619DE5": "Coordenador(a) de planejamento — LCC",
  "OPP-5E3F13FC8243": "Coordenador(a) jurídico(a)",
  "OPP-AEEC2DE2AD80": "Coordenador(a) de planejamento e desmobilização de materiais",
  "OPP-7394644BC8AF": "Coordenador(a) de segurança de deslocamentos",
  "OPP-FD22A570C312": "Coordenador(a) de locais fora das competições",
  "OPP-C3F3319062CF": "Gerente de ambientação de locais fora das competições",
  "OPP-5ED7FF24926F": "Gerente de projetos de serviços médicos",
  "OPP-9C002F2590EC": "Gerente de operações de segurança e proteção",
  "OPP-54563FFF3DE5": "Analista de recrutamento e relatórios — pessoas com deficiência",
  "OPP-85F4DA726C3C": "Gerente de riscos, inteligência e C4",
  "OPP-B02DC7DED3B3": "Gerente sênior de inteligência de negócios",
  "OPP-F701A6FD924C": "Gerente de segurança dos estádios — 8 cidades-sede (Brasil)",
  "OPP-3542B375CE4A": "Banco de talentos para pessoas com deficiência — 8 cidades-sede",
  "OPP-AB221A7B3932": "Coordenador(a) de canais de comunicação de CRM para ingressos",
  "OPP-2AF24974476C": "Gerente de qualidade e testes de aceitação — CRM de ingressos",
  "OPP-0AA2E415F183": "Gerente de relacionamento com parceiros e clientes locais — ingressos",
  "OPP-F9DE37778380": "Coordenador(a) de comunicação digital — ingressos",
  "OPP-3A962BE8E755": "Analista de atendimento ao público — ingressos",
  "OPP-6A05B37EE7EB": "Coordenador(a) de atendimento ao público — ingressos",
  "OPP-11A6F2F999A4": "Gerente de atendimento ao público — ingressos",
  "OPP-8D4CD06F7614": "Coordenador(a) de vendas para grupos — ingressos",
  "OPP-EC7BC8AFB4E1": "Gerente de atendimento às associações-membro — ingressos",
  "OPP-944645D6DA8A": "Coordenador(a) de vendas e estratégia — ingressos",
  "OPP-56522678779A": "Gerente de sistemas de ingressos",
  "OPP-4044C1A3C86C": "Coordenador(a) de treinamento — ingressos",
  "OPP-9E6A2D7A91E2": "Gerente de treinamento e preparação",
  "OPP-FIFA-UNIFORMS-MANAGER": "Gerente de uniformes — Copa do Mundo Feminina 2027",
  "OPP-87B626F99996": "Coordenador(a) de infraestrutura temporária — 8 cidades-sede (Brasil)",
  "OPP-0AFF1DD20CF9": "Gerente de infraestrutura temporária — 7 cidades-sede (Brasil)",
  "OPP-24D29206AB4E": "Gerente de energia e infraestrutura técnica — 7 cidades-sede (Brasil)",
  "OPP-7B2B74FD0E61": "Gerente de segurança e proteção dos locais — 8 cidades-sede (Brasil)",
  "OPP-2D51A3BD5922": "Gerente de tecnologia dos locais — Fortaleza",
  "OPP-C28D96172D27": "Gerente de tecnologia dos locais — Salvador",
  "OPP-B16F2D8B013E": "Coordenador(a) de operações do voluntariado",
  "OPP-24025813DD3B": "Gerente de armazém e distribuição",
  "OPP-1BF8DD247F6F": "Coordenador(a) de planejamento e operações da força de trabalho",
  "OPP-E9F27F231CB5": "Gerente de planejamento e operações da força de trabalho",
  "OPP-CBF-SUMMIT-2026": "Encontro CBF Academy 2026"
};
function localPT(v){return String(v||'').replace(/\bBrazil\b/gi,'Brasil').replace(/\bhost cities\b/gi,'cidades-sede').trim()}
function tituloPT(o){
  const original=String(o.Titulo||'').trim();
  const editorial=String(o.TituloPT||o.TituloTraduzido||'').trim();
  if(editorial)return editorial;
  if(TITULOS_PT[o.ID])return TITULOS_PT[o.ID];
  // Cargos novos: tradução de contingência até a curadoria preencher TituloPT.
  if(!/\b(manager|coordinator|analyst|specialist|director|officer|engineer|designer|supervisor|lead|associate|internship|intern|recruitment|workforce|venue|ticketing|volunteer|broadcast|stadium|applications|women.s world cup|host cities|jobs|career|training|planning|security)\b/i.test(original))return original;
  const areas=[
    [/ticketing|customer care/i,'ingressos e atendimento'],
    [/security|safety|intelligence|risk/i,'segurança e gestão de riscos'],
    [/venue|stadium|overlay/i,'infraestrutura dos locais'],
    [/technology|digital|applications|systems|data|software/i,'tecnologia e sistemas'],
    [/broadcast|media|communications/i,'comunicação e transmissão'],
    [/hospitality|accommodation|travel/i,'hospitalidade e viagens'],
    [/workforce|people|recruitment|human resources/i,'gestão de pessoas'],
    [/planning|operations|logistics|distribution/i,'planejamento e operações'],
    [/finance|accounting|payable|financial/i,'finanças'],
    [/medical|health/i,'serviços médicos'],
    [/training|readiness|education/i,'treinamento'],
    [/volunteer/i,'voluntariado'],
    [/legal|compliance/i,'assuntos jurídicos'],
    [/marketing|commercial|sales|partners/i,'negócios e relacionamento']
  ];
  const area=areas.find(([re])=>re.test(original))?.[1];
  const cargos=[[/\bmanager\b/i,'Gerente'],[/\bcoordinator\b/i,'Coordenador(a)'],[/\banalyst\b/i,'Analista'],[/\bdirector\b/i,'Diretor(a)'],[/\bengineer\b/i,'Engenheiro(a)'],[/\bspecialist\b/i,'Especialista'],[/\bdesigner\b/i,'Designer'],[/\bsupervisor\b/i,'Supervisor(a)'],[/\bofficer\b/i,'Profissional']];
  const cargo=cargos.find(([re])=>re.test(original))?.[1];
  const organizacao=String(o.Organizacao||o.Fonte||'').trim();
  if(cargo&&area)return cargo+' — '+area;
  if(area)return 'Oportunidade na área de '+area;
  return 'Oportunidade profissional'+(organizacao?' na '+organizacao:'');
}
function resumoPT(o){
  const texto=String(o.ResumoPT||o.ResumoTraduzido||o.Resumo||'').trim();
  if(!/\b(the role|you will|we are looking for|apply now|applications are open|key responsibilities|join our team|job description|requirements include)\b/i.test(texto))return texto.replace(/\bMatch Day\b/g,'dia de jogo');
  return 'Confira os detalhes, as atividades e os requisitos desta oportunidade na página oficial da organização.';
}

const style=document.createElement('style');style.textContent='.layout.opportunity-mode{grid-template-columns:1fr}.layout.opportunity-mode #eventCalendar{display:none!important}.layout.opportunity-mode .content{max-width:1200px;width:100%;margin:0 auto}.opp-card{border:1px solid var(--border);border-radius:13px;padding:14px;background:#fff}.opp-card h3{margin:7px 0}.opp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.opp-meta{font-size:11px;color:var(--muted);font-weight:bold;text-transform:uppercase}.opp-summary{font-size:13px;line-height:1.45}.opp-link{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;border-radius:9px;padding:9px 12px;font-size:12px;font-weight:bold}.opp-deadline{font-size:12px;font-weight:bold;margin:9px 0}@media(max-width:820px){.view-tabs{overflow-x:auto}.tab-button{white-space:nowrap}.opp-grid{grid-template-columns:1fr}.news-filters{grid-template-columns:1fr 1fr}.news-filters label:last-child{grid-column:1/-1}}';document.head.appendChild(style);
const nav=document.querySelector('.view-tabs'),tab=document.createElement('button');tab.className='tab-button';tab.id='tabOportunidades';tab.type='button';tab.textContent='Oportunidades';nav.appendChild(tab);
const panel=document.createElement('section');panel.className='panel news-panel';panel.id='opportunityPanel';panel.hidden=true;panel.innerHTML='<div class="news-head"><div><h2>Oportunidades</h2><p>Trabalhe, participe, aprenda e faça parte do ecossistema do futebol feminino e da Copa do Mundo Feminina 2027.</p></div><div class="news-metrics"><div class="news-metric"><small>Abertas</small><strong id="oAbertas">0</strong></div><div class="news-metric"><small>Encerram em 7 dias</small><strong id="oUrgentes">0</strong></div><div class="news-metric"><small>Online/Híbridas</small><strong id="oOnline">0</strong></div></div></div><div class="news-filters"><label>Tipo<select id="oppCategoria"></select></label><label>Formato<select id="oppModalidade"></select></label><label>Local<select id="oppLocal"></select></label><label>Status<select id="oppStatus"></select></label><label>Busca<input id="oppBusca" placeholder="Título, organização ou tema"></label></div><div id="oppGrid" class="opp-grid"></div>';document.querySelector('#pageLayout main.content').appendChild(panel);
function fill(id,vals,label){const el=$(id),cur=el.value;el.innerHTML='<option value="">'+esc(label)+'</option>'+vals.filter(Boolean).sort((a,b)=>a.localeCompare(b,'pt-BR')).map(v=>'<option>'+esc(v)+'</option>').join('');if([...el.options].some(o=>o.value===cur))el.value=cur}
function filters(){fill('oppCategoria',[...new Set(O.map(x=>group(x.Categoria)))],'Todos');fill('oppModalidade',[...new Set(O.map(x=>x.Modalidade))],'Todos');fill('oppLocal',[...new Set(O.map(x=>localPT(x.CidadeUF||x.Abrangencia||x.Cidade)))],'Todos');fill('oppStatus',['Inscrições abertas','Encerra em breve','Inscrições em breve','Encerrada'],'Todos');$('oppStatus').value='Inscrições abertas'}
function card(o){
 const s=status(o),local=localPT(o.CidadeUF||o.Abrangencia||o.Cidade||'Brasil'),deadline=o.PrazoInscricao?'Inscrições até '+dateBR(o.PrazoInscricao):'Prazo não informado';
 const link=/^https?:\/\//i.test(String(o.Link||''))?o.Link:'';
 const titulo=tituloPT(o),resumo=resumoPT(o);
 const original=titulo!==o.Titulo?' title="Título original na fonte: '+esc(o.Titulo)+'"':'';
 return '<article class="opp-card"><div class="opp-meta">'+esc(o.Organizacao||o.Fonte||'')+'</div><div class="badges"><span class="badge">'+esc(group(o.Categoria))+'</span>'+(o.Modalidade?'<span class="badge">'+esc(o.Modalidade)+'</span>':'')+'<span class="badge">'+esc(s)+'</span></div><h3>'+(link?'<a href="'+esc(link)+'" target="_blank" rel="noopener noreferrer" class="title-source-link"'+original+'>'+esc(titulo)+'</a>':esc(titulo))+'</h3><p class="opp-summary">'+esc(resumo)+'</p><div class="badges"><span class="badge">'+esc(local)+'</span>'+(o.GratuitoPago?'<span class="badge">'+esc(o.GratuitoPago)+'</span>':'')+'</div><div class="opp-deadline">'+esc(deadline)+'</div>'+(link?'<a class="opp-link" href="'+esc(link)+'" target="_blank" rel="noopener noreferrer">Ver oportunidade →</a>':'')+'</article>'
}
function render(){const cat=$('oppCategoria').value,mod=$('oppModalidade').value,loc=$('oppLocal').value,st=$('oppStatus').value,q=norm($('oppBusca').value),en=O.map(o=>({...o,_s:status(o)}));const list=en.filter(o=>(!cat||group(o.Categoria)===cat)&&(!mod||o.Modalidade===mod)&&(!loc||localPT(o.CidadeUF||o.Abrangencia||o.Cidade||'')===loc)&&(!st||(st==='Inscrições abertas'?['Inscrições abertas','Encerra em breve'].includes(o._s):o._s===st))&&(!q||norm([tituloPT(o),o.Titulo,resumoPT(o),o.Resumo,o.Organizacao,o.Categoria,o.CidadeUF,o.Abrangencia].join(' ')).includes(q))).sort((a,b)=>(a.PrazoInscricao||'9999-12-31').localeCompare(b.PrazoInscricao||'9999-12-31'));const open=en.filter(o=>['Inscrições abertas','Encerra em breve'].includes(o._s));$('oAbertas').textContent=open.length;$('oUrgentes').textContent=open.filter(o=>{const d=days(o.PrazoInscricao);return d!==null&&d>=0&&d<=7}).length;$('oOnline').textContent=open.filter(o=>/online|híbr|hybrid/i.test(o.Modalidade||'')).length;$('oppGrid').innerHTML=list.length?list.map(card).join(''):'<div class="opp-card">Nenhuma oportunidade corresponde aos filtros.</div>'}
['oppCategoria','oppModalidade','oppLocal','oppStatus'].forEach(id=>$(id).onchange=render);$('oppBusca').oninput=render;
const old=window.showView;function show(v){if(v!=='opportunities'){panel.hidden=true;$('pageLayout').classList.remove('opportunity-mode');tab.classList.remove('active');old(v);return}['eventSidebar','eventMap','eventAgenda','eventFooter'].forEach(id=>{const e=$(id);if(e)e.hidden=true});$('newsPanel').hidden=true;panel.hidden=false;$('pageLayout').classList.remove('news-mode');$('pageLayout').classList.add('opportunity-mode');$('tabEventos').classList.remove('active');$('tabNoticias').classList.remove('active');tab.classList.add('active');render()}window.showView=show;$('tabEventos').onclick=()=>show('events');$('tabNoticias').onclick=()=>show('news');tab.onclick=()=>show('opportunities');
fetch('./oportunidades.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).then(x=>{O=Array.isArray(x)?x:[];filters();render()}).catch(e=>{console.error('Erro ao carregar oportunidades.json',e);O=[];filters();render()});
})();