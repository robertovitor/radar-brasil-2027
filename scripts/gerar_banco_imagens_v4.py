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
    r"Red Bull Bragantino|Botafogo|Vasco|Am[eé]rica Mineiro)", re.I)

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
    'Corinthians women football Brazil','Palmeiras women football Brazil','Ferroviaria women football Brazil',
    'Santos women football Brazil','Sao Paulo women football Brazil','Flamengo women football Brazil',
    'Fluminense women football Brazil','Internacional women football Brazil','Gremio women football Brazil',
    'Cruzeiro women football Brazil','Atletico Mineiro women football Brazil','Bahia women football Brazil',
    'Red Bull Bragantino women football Brazil','Botafogo women football Brazil',
    'Brazil women club football','Brazil women football league','Brazilian women football club',
]

base.SEARCHES['copas_femininas'] = [
    '2023 FIFA Women World Cup football','2023 FIFA Women World Cup players',
    '2023 FIFA Women World Cup match','2023 FIFA Women World Cup teams',
    '2023 FIFA Women World Cup Australia','2023 FIFA Women World Cup New Zealand',
    '2023 FIFA Women World Cup England','2023 FIFA Women World Cup Spain',
    '2023 FIFA Women World Cup Brazil','2023 FIFA Women World Cup USA',
    '2019 FIFA Women World Cup football','2019 FIFA Women World Cup players',
    '2019 FIFA Women World Cup match','2019 FIFA Women World Cup France',
    '2019 FIFA Women World Cup USA','2019 FIFA Women World Cup England',
    '2019 FIFA Women World Cup Netherlands','2019 FIFA Women World Cup Brazil',
    '2015 FIFA Women World Cup football','2015 FIFA Women World Cup players',
    '2015 FIFA Women World Cup match','2015 FIFA Women World Cup Canada',
    '2011 FIFA Women World Cup football','2011 FIFA Women World Cup players',
    '2011 FIFA Women World Cup Germany','2007 FIFA Women World Cup football',
    '2007 FIFA Women World Cup China','2003 FIFA Women World Cup football',
    '1999 FIFA Women World Cup football','1995 FIFA Women World Cup football',
    '1991 FIFA Women World Cup football','FIFA Women World Cup final',
    'FIFA Women World Cup semifinal','FIFA Women World Cup stadium women football',
]

_original_candidates = base.candidates
def candidates(query, pages=4):
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
        return bool(re.search(r'(?:world cup|copa do mundo)',text,re.I) and not MEN.search(text) and not base.BLOCK_AMERICAN.search(text))
    if cat=='futebol_feminino_internacional':
        return bool(base.SOCCER.search(text) and not base.BLOCK_AMERICAN.search(text) and not MEN.search(text))
    return True

base.editorial_ok=editorial_ok
base.main()
