#!/usr/bin/env python3
"""Política visual isolada do Instagram do Radar Brasil 2027.

Esta camada não seleciona conteúdo, não publica e não altera schedules.
Ela apenas renderiza artes próprias por tipo e permite fallback legado.
"""
from __future__ import annotations

import json
import pathlib
from PIL import Image, ImageDraw

POLICY_PATH = pathlib.Path("instagram/visual-policy.json")

DEFAULT_POLICY = {
    "version": 1,
    "enabled": True,
    "fallback_to_legacy": True,
    "opportunity_instagram_enabled": False,
    "types": {
        "evento": "legacy",
        "noticia": "legacy",
        "oportunidade": "legacy",
    },
}

def clean(value):
    return " ".join(str(value or "").split())

def load_policy(path=POLICY_PATH):
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in ("version", "enabled", "fallback_to_legacy", "opportunity_instagram_enabled"):
                if key in raw:
                    policy[key] = raw[key]
            if isinstance(raw.get("types"), dict):
                policy["types"].update(raw["types"])
    except Exception as exc:
        print("visual_policy_warning=" + type(exc).__name__)
    return policy

def visual_mode(kind, policy=None):
    policy = policy or load_policy()
    if not policy.get("enabled"):
        return "legacy"
    return clean((policy.get("types") or {}).get(kind)) or "legacy"

def _pill(draw, xy, text, font, fill, text_fill):
    x0,y0,x1,y1=xy
    draw.rounded_rectangle(xy, radius=18, fill=fill)
    bbox=draw.textbbox((0,0),text,font=font)
    tw=bbox[2]-bbox[0]; th=bbox[3]-bbox[1]
    draw.text((x0+(x1-x0-tw)/2,y0+(y1-y0-th)/2-2),text,font=font,fill=text_fill)

def _fit(draw, title, width, fit_title, start=82, min_size=58, max_lines=4):
    return fit_title(draw, clean(title), width, start_size=start, min_size=min_size, max_lines=max_lines)

def render_event_text_art(out, item, *, font, wrap, fit_title):
    im=Image.new("RGB",(1080,1080),(5,69,48))
    draw=ImageDraw.Draw(im,"RGBA")
    left,right=115,965
    width=right-left

    draw.rectangle((0,0,1080,128),fill=(3,45,34,255))
    draw.text((left,36),"RADAR BRASIL 2027",font=font(36,True),fill="white")
    _pill(draw,(left,166,left+210,228),"EVENTO",font(25,True),(255,220,0,255),(14,48,36,255))

    # Elementos gráficos discretos: linhas de campo, sem depender de foto.
    draw.line((760,180,1010,430),fill=(255,255,255,30),width=8)
    draw.line((840,180,1010,350),fill=(255,220,0,80),width=8)
    draw.ellipse((825,250,1045,470),outline=(255,255,255,40),width=6)

    f,lines,readable=_fit(draw,item.get("title"),width,fit_title,start=82,max_lines=4)
    y=286
    for line in lines[:4]:
        draw.text((left,y),line,font=f,fill="white")
        y+=f.size+10

    info_y=max(650,y+32)
    date_text=clean(item.get("display_date") or item.get("subtitle"))
    place_text=clean(item.get("display_place"))
    draw.rounded_rectangle((left,info_y,right,info_y+128),radius=24,fill=(255,255,255,22),outline=(255,255,255,45),width=2)
    draw.text((left+28,info_y+20),"QUANDO",font=font(20,True),fill=(255,220,0))
    df=font(28,True)
    dlines=wrap(draw,date_text,df,width-56)
    draw.text((left+28,info_y+54),dlines[0] if dlines else "Data a confirmar",font=df,fill="white")

    place_y=info_y+150
    draw.rounded_rectangle((left,place_y,right,place_y+128),radius=24,fill=(255,255,255,22),outline=(255,255,255,45),width=2)
    draw.text((left+28,place_y+20),"ONDE",font=font(20,True),fill=(255,220,0))
    pf=font(27,True)
    plines=wrap(draw,place_text or "Local a definir",pf,width-56)
    draw.text((left+28,place_y+54),plines[0] if plines else "Local a definir",font=pf,fill="white")

    draw.rectangle((left,986,right,991),fill=(255,220,0,255))
    draw.text((left,1010),"Saiba mais pelo link da bio",font=font(20,True),fill="white")
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    im.save(out,"JPEG",quality=94,optimize=True)
    return readable and f.size>=58 and len(lines)<=4, f.size, len(lines), {
        "visual_mode":"radar_event_text_art",
        "semantic_reason":"owned_text_art_policy",
        "image_credit":"Arte própria do Radar Brasil 2027",
        "license_note":"arte_propria",
    }

def render_news_art(out, item, *, font, wrap, fit_title):
    im=Image.new("RGB",(1080,1080),(11,52,78))
    draw=ImageDraw.Draw(im,"RGBA")
    left,right=115,965
    width=right-left

    # Composição editorial própria: blocos e curvas, sem foto externa.
    draw.polygon([(0,650),(1080,430),(1080,1080),(0,1080)],fill=(7,102,73,255))
    draw.polygon([(700,0),(1080,0),(1080,390)],fill=(255,220,0,235))
    draw.ellipse((720,110,1120,510),outline=(255,255,255,34),width=8)
    draw.ellipse((800,190,1040,430),outline=(255,220,0,110),width=8)
    draw.rectangle((0,0,1080,128),fill=(4,34,54,235))
    draw.text((left,36),"RADAR BRASIL 2027",font=font(36,True),fill="white")
    _pill(draw,(left,166,left+220,228),"NOTÍCIA",font(25,True),(255,220,0,255),(17,43,52,255))

    f,lines,readable=_fit(draw,item.get("title"),width,fit_title,start=84,max_lines=4)
    y=302
    for line in lines[:4]:
        draw.text((left,y),line,font=f,fill="white")
        y+=f.size+10

    subtitle=clean(item.get("subtitle"))
    if subtitle:
        sy=max(720,y+36)
        sf=font(25,True)
        slines=wrap(draw,subtitle,sf,width)
        for line in slines[:2]:
            draw.text((left,sy),line,font=sf,fill=(232,244,240))
            sy+=34

    draw.text((left,900),"Acompanhe o que está movimentando",font=font(24,False),fill=(232,244,240))
    draw.text((left,934),"a Copa Feminina 2027 no Brasil.",font=font(24,True),fill="white")
    draw.rectangle((left,986,right,991),fill=(255,220,0,255))
    draw.text((left,1010),"Saiba mais pelo link da bio",font=font(20,True),fill="white")
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    im.save(out,"JPEG",quality=94,optimize=True)
    return readable and f.size>=58 and len(lines)<=4, f.size, len(lines), {
        "visual_mode":"radar_news_owned_art",
        "semantic_reason":"owned_editorial_art_policy",
        "image_credit":"Arte própria do Radar Brasil 2027",
        "license_note":"arte_propria",
    }

def render_opportunity_art(out, item, *, font, wrap, fit_title):
    im=Image.new("RGB",(1080,1080),(247,196,52))
    draw=ImageDraw.Draw(im,"RGBA")
    left,right=115,965
    width=right-left
    dark=(5,69,48,255)

    draw.polygon([(0,0),(1080,0),(1080,175),(0,315)],fill=dark)
    draw.polygon([(680,1080),(1080,850),(1080,1080)],fill=(11,91,66,255))
    draw.ellipse((770,80,1110,420),outline=(255,255,255,55),width=9)
    draw.ellipse((840,150,1040,350),outline=(5,69,48,100),width=9)
    draw.text((left,42),"RADAR BRASIL 2027",font=font(36,True),fill="white")
    _pill(draw,(left,190,left+330,254),"OPORTUNIDADE",font(24,True),(255,255,255,245),dark)

    f,lines,readable=_fit(draw,item.get("title"),width,fit_title,start=80,max_lines=4)
    y=338
    for line in lines[:4]:
        draw.text((left,y),line,font=f,fill=dark)
        y+=f.size+10

    category=clean(item.get("category"))
    org=clean(item.get("organization"))
    details=" • ".join(x for x in (category,org) if x)
    if details:
        sy=max(700,y+30)
        sf=font(25,True)
        for line in wrap(draw,details,sf,width)[:2]:
            draw.text((left,sy),line,font=sf,fill=(17,66,52))
            sy+=34

    deadline=clean(item.get("display_date"))
    if deadline:
        dy=850
        draw.rounded_rectangle((left,dy,right,dy+86),radius=22,fill=dark)
        draw.text((left+25,dy+24),deadline,font=font(28,True),fill="white")

    _pill(draw,(left,955,left+370,1018),"CONFIRA E PARTICIPE",font(21,True),dark,(255,255,255,255))
    draw.text((right-270,974),"link na bio",font=font(20,True),fill=dark)
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    im.save(out,"JPEG",quality=94,optimize=True)
    return readable and f.size>=58 and len(lines)<=4, f.size, len(lines), {
        "visual_mode":"radar_opportunity_owned_art",
        "semantic_reason":"owned_opportunity_art_policy",
        "image_credit":"Arte própria do Radar Brasil 2027",
        "license_note":"arte_propria",
    }

def render_owned_art(out, item, *, font, wrap, fit_title, policy=None):
    mode=visual_mode(clean(item.get("type")),policy)
    if mode=="text_art":
        return render_event_text_art(out,item,font=font,wrap=wrap,fit_title=fit_title)
    if mode=="radar_art":
        return render_news_art(out,item,font=font,wrap=wrap,fit_title=fit_title)
    if mode=="radar_art_opportunity":
        return render_opportunity_art(out,item,font=font,wrap=wrap,fit_title=fit_title)
    raise ValueError("legacy_visual_mode")
