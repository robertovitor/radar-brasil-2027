from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")
old = "<title>Radar Brasil 2027 — Mapa Interativo Offline</title>"
new = """<title>Radar Brasil 2027 | Copa do Mundo Feminina</title>
<meta name="description" content="Eventos, notícias e ativações da Copa do Mundo Feminina 2027 no Brasil. Acompanhe tudo em um só lugar.">
<link rel="canonical" href="https://radarcopafeminina2027.com.br/">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_BR">
<meta property="og:site_name" content="Radar Brasil 2027">
<meta property="og:title" content="Radar Brasil 2027 | Copa do Mundo Feminina">
<meta property="og:description" content="Eventos, notícias e ativações da Copa do Mundo Feminina 2027 no Brasil. Acompanhe tudo em um só lugar.">
<meta property="og:url" content="https://radarcopafeminina2027.com.br/">
<meta property="og:image" content="https://radarcopafeminina2027.com.br/Radar%20Brasil%202027_%20O%20Mundo%20Se%20Conecta.png">
<meta property="og:image:alt" content="Radar Brasil 2027 — O Mundo Se Conecta">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Radar Brasil 2027 | Copa do Mundo Feminina">
<meta name="twitter:description" content="Eventos, notícias e ativações da Copa do Mundo Feminina 2027 no Brasil.">
<meta name="twitter:image" content="https://radarcopafeminina2027.com.br/Radar%20Brasil%202027_%20O%20Mundo%20Se%20Conecta.png">"""

if old not in s:
    raise SystemExit("Título antigo não encontrado; nenhuma alteração feita.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("Metadados sociais atualizados com sucesso.")
