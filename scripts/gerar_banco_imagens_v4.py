#!/usr/bin/env python3
import re
import gerar_banco_imagens_v3 as base

MEN=re.compile(r"(?:\bmen\b|men['’]?s|\bmale\b|masculin)",re.I)
BRAZIL_WOMEN=re.compile(
    r"(?:Brazil|Brasil|brasileir|Marta|Formiga|Debinha|Cristiane|Kerolin|Adriana|Gabi Nunes|"
    r"Tamires|Bia Zaneratto|Andressa Alves|Andressinha|Ary Borges|Antonia|Lauren|Rafaelle|"
    r"Ludmila|Geyse|Jheniffer|Duda Sampaio|Angelina|Yasmim|Bruninha|Tarciane|Thaissa|"
    r"Aline Gomes|Priscila|Amanda Gutierres|Lorena|Luciana|Barbara|Gabi Portilho|"
    r"Taina Maranhão|Giovana Queiroz|Micaelly|Aline Milene|Leticia Santos|Camila Rodrigues)", re.I)
KNOWN_PLAYER=BRAZIL_WOMEN
BRAZIL_FEM=re.compile(
    r"(?:Brazil|Brasil|brasileir|Brasileir[aã]o Feminino|Campeonato Brasileiro.*Feminino|"
    r"Corinthians|Palmeiras|Ferrovi[aá]ria|Santos|S[aã]o Paulo|Flamengo|Fluminense|"
    r"Internacional|Gr[eê]mio|Cruzeiro|Atl[eé]tico Mineiro|Bahia|Fortaleza|Ava[ií]|Kindermann|"
    r"Red Bull Bragantino|Botafogo|Vasco|Am[eé]rica Mineiro|Real Bras[ií]lia|Minas Bras[ií]lia|"
    r"3B da Amaz[oô]nia|Mixto|Sport Recife|Vit[oó]ria|Juventude)", re.I)

base.SEARCHES['selecao_brasileira'] = [
    'Brazil women national football team','Brazil women national football team 2024',
    'Brazil women national football team 2023','Brazil women national football team 2019',
    'Brazil women national football team 2016','Brazil women national football team Olympics',
    'Brazil women football World Cup','Brazil at 2023 FIFA Women World Cup',
    'Brazil at 2019 FIFA Women World Cup','Brazil women football 2024 Olympics',
    'Brazil women football 2016 Olympics','Brazil women football Copa America Femenina',
    'Brazil women football SheBelieves Cup','Brazil women football Tournament of Nations',
    'Brazil women football friendly','Brazil women football Marta','Brazil women football Formiga',
    'Brazil women football Debinha','Brazil women football Cristiane','Brazil women football Kerolin',
    'Brazil women football Adriana','Brazil women football Gabi Nunes','Brazil women football Tamires',
    'Brazil women football Bia Zaneratto','Brazil women football Andressa Alves','Brazil women football Ary Borges',
    'Brazil women football Rafaelle','Brazil women football Ludmila','Brazil women football Geyse',
    'Brazil women football Angelina','Brazil women football Yasmim','Brazil women football Tarciane',
    'Brazil women football Amanda Gutierres','Brazil women football Lorena goalkeeper',
    'Brazil women football Gabi Portilho','Brazil women football Taina Maranhão',
    'Brazil women football Giovana Queiroz','Brazil women football Micaelly',
    'Brazil women football Aline Milene','Brazil women football Leticia Santos',
    'Brazil women football Camila Rodrigues goalkeeper',
]

base.SEARCHES['futebol_feminino_brasil'] = [
    'women association football Brazil','Brazil female footballer','Brazil women football players',
    'Campeonato Brasileiro de Futebol Feminino','Brasileirao Feminino football',
    'Campeonato Brasileiro Feminino A1','Campeonato Brasileiro Feminino A2','Copa do Brasil futebol feminino',
    'Corinthians women football Brazil','Palmeiras women football Brazil','Ferroviaria women football Brazil',
    'Santos women football Brazil','Sao Paulo women football Brazil','Flamengo women football Brazil',
    'Fluminense women football Brazil','Internacional women football Brazil','Gremio women football Brazil',
    'Cruzeiro women football Brazil','Atletico Mineiro women football Brazil','Bahia women football Brazil',
    'Red Bull Bragantino women football Brazil','Botafogo women football Brazil','Vasco women football Brazil',
    'Real Brasilia women football','Minas Brasilia women football','Kindermann women football Brazil',
    '3B da Amazonia women football','Mixto women football Brazil','Sport Recife women football',
    'Vitoria women football Brazil','Juventude women football Brazil',
    'Brazil women club football','Brazil women football league','Brazilian women football club',
    'Libertadores Femenina Brazil club','Copa Libertadores Femenina Corinthians',
    'Copa Libertadores Femenina Ferroviaria','Copa Libertadores Femenina Palmeiras',
]

base.SEARCHES['copas_femininas'] = [
    "2023 FIFA Women's World Cup football","2023 FIFA Women's World Cup players",
    "2023 FIFA Women's World Cup match","2023 FIFA Women's World Cup teams",
    "2023 FIFA Women's World Cup final","2023 FIFA Women's World Cup semifinal",
    "2023 FIFA Women's World Cup quarterfinal","2023 FIFA Women's World Cup opening",
    "2023 FIFA Women's World Cup Australia","2023 FIFA Women's World Cup New Zealand",
    "2023 FIFA Women's World Cup England","2023 FIFA Women's World Cup Spain",
    "2023 FIFA Women's World Cup Brazil","2023 FIFA Women's World Cup USA",
    "2023 Women's World Cup Japan","2023 Women's World Cup Sweden",
    "2023 Women's World Cup Colombia","2023 Women's World Cup France",
    "2023 Women's World Cup Nigeria","2023 Women's World Cup Germany",
    "2023 Women's World Cup Alexia Putellas","2023 Women's World Cup Sam Kerr",
    "2023 Women's World Cup Megan Rapinoe","2023 Women's World Cup Marta",
    "2023 Women's World Cup Lauren James","2023 Women's World Cup Mary Earps",
    "2023 Women's World Cup Aitana Bonmati","2023 Women's World Cup Olga Carmona",
    "2019 FIFA Women's World Cup football","2019 FIFA Women's World Cup players",
    "2019 FIFA Women's World Cup match","2019 FIFA Women's World Cup final",
    "2019 FIFA Women's World Cup semifinal","2019 FIFA Women's World Cup quarterfinal",
    "2019 FIFA Women's World Cup France","2019 FIFA Women's World Cup USA",
    "2019 FIFA Women's World Cup England","2019 FIFA Women's World Cup Netherlands",
    "2019 FIFA Women's World Cup Brazil","2019 Women's World Cup Germany",
    "2019 Women's World Cup Sweden","2019 Women's World Cup Norway",
    "2019 Women's World Cup Japan","2019 Women's World Cup Australia",
    "2019 Women's World Cup Megan Rapinoe","2019 Women's World Cup Alex Morgan",
    "2019 Women's World Cup Lucy Bronze","2019 Women's World Cup Vivianne Miedema",
    "2015 FIFA Women's World Cup football","2015 FIFA Women's World Cup players",
    "2015 FIFA Women's World Cup match","2015 FIFA Women's World Cup final",
    "2015 FIFA Women's World Cup semifinal","2015 FIFA Women's World Cup Canada",
    "2015 Women's World Cup USA","2015 Women's World Cup Germany",
    "2015 Women's World Cup Japan","2015 Women's World Cup England",
    "2011 FIFA Women's World Cup football","2011 FIFA Women's World Cup players",
    "2011 FIFA Women's World Cup final","2011 FIFA Women's World Cup Germany",
    "2011 Women's World Cup Japan","2011 Women's World Cup USA",
    "2007 FIFA Women's World Cup football","2007 FIFA Women's World Cup final",
    "2007 FIFA Women's World Cup China","2007 Women's World Cup Brazil",
    "2007 Women's World Cup Germany","2003 FIFA Women's World Cup football",
    "2003 FIFA Women's World Cup final","1999 FIFA Women's World Cup football",
    "1999 FIFA Women's World Cup final","1995 FIFA Women's World Cup football",
    "1995 FIFA Women's World Cup final","1991 FIFA Women's World Cup football",
    "1991 FIFA Women's World Cup final","FIFA Women's World Cup trophy football",
    "FIFA Women's World Cup supporters football","FIFA Women's World Cup stadium football",
    "FIFA Women's World Cup opening ceremony",
]

base.SEARCHES['torcida_futebol_feminino'] = [
    "FIFA Women's World Cup fans football",
    "FIFA Women's World Cup supporters stadium",
    "FIFA Women's World Cup crowd football",
    "2023 Women's World Cup fans Australia",
    "2023 Women's World Cup fans New Zealand",
    "2023 Women's World Cup fans England",
    "2023 Women's World Cup fans Spain",
    "2023 Women's World Cup fans Brazil",
    "2023 Women's World Cup fans USA",
    "2019 Women's World Cup fans France",
    "2019 Women's World Cup fans USA",
    "2019 Women's World Cup fans England",
    "2019 Women's World Cup supporters Netherlands",
    "2015 Women's World Cup fans Canada",
    "women football supporters Brazil stadium",
    "women football supporters England stadium",
    "women football supporters Spain stadium",
    "women football supporters Australia stadium",
    "women soccer supporters national team",
    "women association football fans stadium",
    "female football supporters crowd stadium",
    "women football crowd supporters",
    "women soccer fans flags stadium",
    "women football fans cheering stadium",
]

_original_candidates = base.candidates
def candidates(query, pages=4):
    # Mantem a profundidade alta, mas as consultas ficaram mais especificas para
    # gerar menos resultados irrelevantes por chamada.
    return _original_candidates(query, pages=7)
base.candidates = candidates


def editorial_ok(cat,title,desc):
    text=f'{title} {desc}'
    if base.BLOCK_COMMON.search(text):
        return False
    if cat=='torcida_futebol_feminino':
        return bool(base.WOMEN.search(text) and base.SOCCER.search(text) and base.FANS.search(text) and not base.BLOCK_AMERICAN.search(text) and not MEN.search(text))
    if cat=='selecao_brasileira':
        return bool(not MEN.search(text) and ((BRAZIL_WOMEN.search(text) and base.SOCCER.search(text)) or KNOWN_PLAYER.search(text)))
    if cat=='futebol_feminino_brasil':
        return bool(BRAZIL_FEM.search(text) and base.SOCCER.search(text) and not MEN.search(text) and not base.BLOCK_AMERICAN.search(text))
    if cat=='copas_femininas':
        return bool(re.search(r"(?:women['’]?s? world cup|world cup|copa do mundo)",text,re.I) and not MEN.search(text) and not base.BLOCK_AMERICAN.search(text))
    if cat=='futebol_feminino_internacional':
        return bool(base.SOCCER.search(text) and not base.BLOCK_AMERICAN.search(text) and not MEN.search(text))
    return True

base.editorial_ok=editorial_ok
base.main()
