#!/usr/bin/env python3
"""Alterna cards editoriais com artes ilustradas temáticas, sem API externa."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import unicodedata
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value).casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def load(path: pathlib.Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def wrap(draw: ImageDraw.ImageDraw, text: str, chosen_font, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=chosen_font)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def theme_for(text: str) -> str:
    v = normalized(text)
    rules = [
        ("seguranca", ("protecao", "seguranca", "mulheres", "assedio", "elas a frente")),
        ("trofeu", ("trofeu", "taca", "tour da taca", "premiacao")),
        ("marketing", ("patrocin", "marketing", "negocio", "audiencia", "marca", "comercial")),
        ("voluntariado", ("voluntari", "ativacao", "fan fest", "experiencia", "engajamento")),
        ("mobilidade", ("mobilidade", "metro", "transporte", "infraestrutura", "aeroporto")),
        ("governanca", ("lei", "legislacao", "governanca", "tribut", "fiscal", "planejamento", "organizacao")),
        ("selecao", ("selecao brasileira", "amistoso", "convocacao", "data fifa", "preparacao")),
        ("estadio", ("estadio", "arena", "cidade-sede", "cidade sede", "maracana")),
        ("legado", ("legado", "inclus", "social", "diversidade", "sustent")),
        ("tecnologia", ("tecnologia", "digital", "dados", "inovacao")),
        ("torcida", ("torcida", "torcedor", "publico", "ingresso")),
        ("evento", ("festival", "evento", "workshop", "painel", "seminario")),
    ]
    for theme, markers in rules:
        if any(marker in v for marker in markers):
            return theme
    return "futebol"


def palette(theme: str):
    palettes = {
        "seguranca": ((69, 29, 101), (137, 63, 162), (255, 213, 64)),
        "trofeu": ((12, 37, 76), (26, 81, 142), (255, 188, 40)),
        "marketing": ((6, 59, 48), (17, 126, 88), (255, 210, 0)),
        "voluntariado": ((9, 83, 56), (35, 151, 94), (255, 205, 48)),
        "mobilidade": ((16, 69, 96), (49, 139, 166), (255, 210, 70)),
        "governanca": ((25, 57, 96), (55, 96, 143), (255, 202, 48)),
        "selecao": ((4, 76, 49), (15, 145, 90), (255, 213, 0)),
        "estadio": ((9, 60, 82), (38, 129, 145), (255, 183, 54)),
        "legado": ((22, 102, 78), (62, 160, 123), (255, 205, 65)),
        "tecnologia": ((5, 40, 83), (19, 94, 164), (78, 214, 219)),
        "torcida": ((5, 83, 54), (20, 145, 82), (255, 205, 35)),
        "evento": ((64, 31, 105), (129, 47, 151), (255, 196, 47)),
        "futebol": ((4, 74, 48), (17, 142, 91), (255, 210, 0)),
    }
    return palettes[theme]


def gradient(image: Image.Image, start, end):
    px = image.load()
    for y in range(image.height):
        r = y / max(1, image.height - 1)
        color = tuple(int(a + (b - a) * r) for a, b in zip(start, end))
        for x in range(image.width):
            px[x, y] = color


def draw_ball(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(245,245,238,255), outline=(255,255,255,220), width=5)
    pts=[]
    for i in range(5):
        import math
        a=-math.pi/2+i*2*math.pi/5
        pts.append((cx+int(r*.35*math.cos(a)),cy+int(r*.35*math.sin(a))))
    draw.polygon(pts, fill=(22,52,47,255))
    for x,y in pts:
        draw.line((cx,cy,x,y), fill=(22,52,47,150), width=4)


def draw_scene(draw: ImageDraw.ImageDraw, theme: str, accent, digest: bytes):
    white=(255,255,255,220)
    dark=(5,25,28,210)
    if theme in {"futebol","selecao"}:
        draw.ellipse((655,155,760,260), fill=dark)
        draw.rounded_rectangle((665,245,750,595), radius=38, fill=dark)
        draw.line((690,360,575,525), fill=dark, width=34)
        draw.line((730,360,845,505), fill=dark, width=34)
        draw.line((690,575,595,790), fill=dark, width=38)
        draw.line((730,575,835,770), fill=dark, width=38)
        draw_ball(draw, 870, 760, 88)
    elif theme == "estadio":
        draw.ellipse((180,260,900,760), outline=white, width=28)
        draw.ellipse((265,345,815,675), outline=white, width=22)
        draw.rectangle((300,470,780,625), fill=(12,92,59,220))
        draw.line((540,470,540,625), fill=white, width=6)
    elif theme == "mobilidade":
        draw.rounded_rectangle((170,365,910,685), radius=70, fill=(235,245,245,230))
        draw.rounded_rectangle((245,415,835,520), radius=25, fill=(24,72,101,220))
        for x in (300,500,700): draw.ellipse((x,640,x+95,735), fill=dark)
        draw.line((95,815,985,815), fill=white, width=12)
    elif theme == "seguranca":
        shield=[(540,190),(800,300),(750,645),(540,820),(330,645),(280,300)]
        draw.polygon(shield, fill=(255,255,255,55), outline=white)
        draw.ellipse((455,330,625,500), outline=white, width=18)
        draw.line((540,500,540,680), fill=white, width=20)
        draw.line((470,590,610,590), fill=white, width=20)
    elif theme == "marketing":
        draw.rounded_rectangle((145,420,515,610), radius=70, fill=(235,235,225,230))
        draw.rounded_rectangle((565,420,935,610), radius=70, fill=(235,235,225,230))
        draw.line((470,520,610,520), fill=accent+(255,), width=44)
        draw.ellipse((445,470,555,580), fill=(205,170,120,255))
        draw.ellipse((525,470,635,580), fill=(140,95,65,255))
    elif theme == "voluntariado":
        for x in (300,540,780):
            draw.ellipse((x-55,285,x+55,395), fill=dark)
            draw.rounded_rectangle((x-80,390,x+80,720), radius=45, fill=dark)
            draw.line((x-65,470,x-145,330), fill=dark, width=32)
        draw.text((310,520), "VOLUNTÁRIO", font=font(36,True), fill=white)
    elif theme == "trofeu":
        draw.ellipse((390,210,690,510), outline=accent+(255,), width=30)
        draw.polygon([(455,450),(625,450),(590,720),(490,720)], fill=accent+(230,))
        draw.rounded_rectangle((390,700,690,805), radius=25, fill=accent+(245,))
    elif theme == "governanca":
        for x,h in ((220,380),(390,500),(560,620),(730,450)):
            draw.rectangle((x,820-h,x+105,820), fill=(240,245,245,205))
            for yy in range(850-h,800,80): draw.rectangle((x+25,yy,x+80,yy+28), fill=(20,70,100,180))
        draw.polygon([(120,820),(960,820),(900,875),(180,875)], fill=accent+(230,))
    elif theme == "legado":
        for i,x in enumerate((250,400,540,680,830)):
            skin=[(222,180,140,255),(145,95,65,255),(105,70,50,255)][i%3]
            draw.rounded_rectangle((x-35,410-(i%2)*50,x+35,790),radius=30,fill=skin)
            draw.ellipse((x-55,325-(i%2)*50,x+55,435-(i%2)*50),fill=skin)
        draw.arc((230,620,850,960), 190, 350, fill=white, width=25)
    elif theme == "tecnologia":
        for i in range(7):
            x=170+(digest[i]%700); y=230+(digest[i+7]%520)
            draw.ellipse((x-18,y-18,x+18,y+18), fill=accent+(245,))
            if i: draw.line((lastx,lasty,x,y), fill=(255,255,255,120), width=5)
            lastx,lasty=x,y
        draw_ball(draw, 730, 520, 120)
    elif theme == "torcida":
        for i in range(9):
            x=120+i*105; y=580+(i%3)*35
            draw.ellipse((x-35,y-230,x+35,y-160), fill=dark)
            draw.line((x,y-160,x,y+50), fill=dark, width=28)
            draw.line((x,y-80,x-65,y-220-(i%2)*80), fill=dark, width=24)
            draw.line((x,y-80,x+65,y-240+((i+1)%2)*70), fill=dark, width=24)
    else:
        for i in range(7):
            r=75+(digest[i]%100); x=140+(digest[i+7]%800); y=180+(digest[i+14]%600)
            draw.ellipse((x-r,y-r,x+r,y+r), fill=accent+(28,))
        draw_ball(draw, 765, 545, 145)


def illustrated_art(path: pathlib.Path, post: dict):
    caption=clean(post.get("caption"))
    title=caption.split("\n",1)[0]
    title=re.sub(r"^[^\wÀ-ÿ]+\s*", "", title)
    theme=theme_for(caption)
    start,end,accent=palette(theme)
    digest=hashlib.sha256((post.get("idempotency_key") or title).encode()).digest()

    image=Image.new("RGB",(1080,1080))
    gradient(image,start,end)
    draw=ImageDraw.Draw(image,"RGBA")

    for i in range(8):
        r=75+digest[i]
        x=(digest[i+8]*7+i*103)%1250-90
        y=(digest[i+16]*5+i*137)%1150-60
        draw.ellipse((x-r,y-r,x+r,y+r), fill=accent+(24,))

    draw_scene(draw,theme,accent,digest)
    draw.rectangle((0,0,1080,185), fill=(0,0,0,110))
    draw.text((66,48),"RADAR BRASIL 2027",font=font(46,True),fill=(255,255,255,255))
    draw.rounded_rectangle((755,52,1015,120),radius=28,fill=accent+(245,))
    draw.text((790,69),"ILUSTRAÇÃO",font=font(26,True),fill=(13,34,31,255))

    panel_top=790
    draw.rectangle((0,panel_top,1080,1080), fill=(0,0,0,175))
    tf=font(43,True)
    lines=wrap(draw,title,tf,930)
    while len(lines)>4 and tf.size>32:
        tf=font(tf.size-3,True); lines=wrap(draw,title,tf,930)
    y=825
    for line in lines[:4]:
        draw.text((66,y),line,font=tf,fill=(255,255,255,255)); y+=tf.size+10
    draw.text((66,1026),"Imagem conceitual • @RadarBrasil2027",font=font(22,True),fill=accent+(255,))

    path.parent.mkdir(parents=True,exist_ok=True)
    image.save(path,"PNG",optimize=True)


def art_path_from_url(url: str) -> pathlib.Path | None:
    marker="/main/"
    if marker not in url:
        return None
    return pathlib.Path(url.split(marker,1)[1])


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",type=pathlib.Path,required=True)
    parser.add_argument("--ledger",type=pathlib.Path,default="instagram/publicados.json")
    args=parser.parse_args()

    batch=load(args.batch,{})
    posts=batch.get("posts") or []
    if not posts:
        print("Sem publicação para avaliar.")
        return 0

    ledger=load(args.ledger,{"published":[]})
    published=ledger.get("published",[])

    # O histórico atual tem quantidade ímpar; assim a próxima publicação começa ilustrada.
    # Depois disso, cada sucesso no ledger alterna automaticamente o formato.
    use_illustrated=(len(published)%2)==1
    if not use_illustrated:
        print("Formato desta rodada: card editorial.")
        return 0

    post_path=pathlib.Path(posts[0])
    post=load(post_path,{})
    art_path=art_path_from_url(clean(post.get("image_url")))
    if not art_path:
        print("URL da arte não corresponde ao repositório; mantendo card editorial.")
        return 0

    illustrated_art(art_path,post)
    print(f"Formato desta rodada: arte ilustrada temática ({theme_for(post.get('caption',''))}).")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
