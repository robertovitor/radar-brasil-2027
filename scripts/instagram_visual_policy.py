#!/usr/bin/env python3
"""Política visual isolada do Instagram do Radar Brasil 2027.

Esta camada não seleciona conteúdo, não publica e não altera schedules.
Ela apenas renderiza artes próprias por tipo e permite fallback legado.
"""
from __future__ import annotations

import json
import pathlib
import hashlib
import math
from PIL import Image, ImageDraw, ImageFont

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


def _variant_for(item, modulo=2):
    key=clean(item.get("key") or item.get("title"))
    digest=hashlib.sha256(key.encode("utf-8")).digest()
    return digest[0] % max(1,modulo)

def _draw_stadium_lights(draw, x, y, scale=1.0, color=(255,255,255,110)):
    pole=int(150*scale)
    draw.line((x,y,x,y+pole),fill=color,width=max(3,int(6*scale)))
    for dx in (-32,-10,12,34):
        draw.ellipse((x+dx*scale-6*scale,y-8*scale,x+dx*scale+6*scale,y+4*scale),fill=color)

def _draw_ball(draw, cx, cy, r, fill=(245,245,235,255), dark=(18,45,38,255)):
    draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill,outline=dark,width=max(4,r//16))
    draw.regular_polygon((cx,cy,max(10,r//3)),5,rotation=18,fill=dark)
    for ang in (18,90,162,234,306):
        x1=cx+(r*0.34)*math.cos(math.radians(ang))
        y1=cy+(r*0.34)*math.sin(math.radians(ang))
        x2=cx+(r*0.82)*math.cos(math.radians(ang))
        y2=cy+(r*0.82)*math.sin(math.radians(ang))
        draw.line((x1,y1,x2,y2),fill=dark,width=max(3,r//20))

def _draw_footballer(draw, x, y, scale=1.0):
    # Jogadora estilizada, vista de costas, em área reservada da direita.
    skin=(116,74,48,255)
    hair=(20,25,28,255)
    jersey=(244,196,40,255)
    shorts=(18,74,128,255)
    outline=(8,34,48,255)
    head_r=int(44*scale)
    draw.ellipse((x-head_r,y-head_r,x+head_r,y+head_r),fill=skin,outline=outline,width=max(3,int(5*scale)))
    draw.ellipse((x-head_r-8*scale,y-head_r-10*scale,x+head_r+5*scale,y+head_r*0.3),fill=hair)
    draw.polygon([
        (x+head_r*0.4,y-head_r*0.3),
        (x+105*scale,y-30*scale),
        (x+160*scale,y+25*scale),
        (x+95*scale,y+22*scale),
    ],fill=hair)
    torso=[
        (x-72*scale,y+52*scale),(x+72*scale,y+52*scale),
        (x+92*scale,y+245*scale),(x-92*scale,y+245*scale)
    ]
    draw.polygon(torso,fill=jersey,outline=outline)
    draw.polygon([
        (x-92*scale,y+110*scale),(x-142*scale,y+255*scale),
        (x-110*scale,y+272*scale),(x-45*scale,y+135*scale)
    ],fill=skin)
    draw.polygon([
        (x+92*scale,y+110*scale),(x+158*scale,y+245*scale),
        (x+130*scale,y+265*scale),(x+44*scale,y+136*scale)
    ],fill=skin)
    draw.rectangle((x-85*scale,y+245*scale,x+85*scale,y+330*scale),fill=shorts)
    draw.polygon([(x-65*scale,y+330*scale),(x-18*scale,y+330*scale),(x-36*scale,y+520*scale),(x-76*scale,y+520*scale)],fill=skin)
    draw.polygon([(x+18*scale,y+330*scale),(x+65*scale,y+330*scale),(x+78*scale,y+520*scale),(x+38*scale,y+520*scale)],fill=skin)
    # Número decorativo sem associação a atleta real.
    try:
        draw.text((x-24*scale,y+125*scale),"7",font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",int(70*scale)),fill=(12,70,75,220))
    except Exception:
        pass

def _draw_trophy(draw, cx, cy, scale=1.0):
    gold=(242,185,46,255)
    dark=(83,59,20,255)
    w=150*scale; h=190*scale
    draw.rounded_rectangle((cx-w/2,cy-h/2,cx+w/2,cy+h/3),radius=int(25*scale),fill=gold,outline=dark,width=max(4,int(6*scale)))
    draw.arc((cx-w,cy-h/2,cx-w/4,cy+h/4),70,285,fill=gold,width=max(12,int(24*scale)))
    draw.arc((cx+w/4,cy-h/2,cx+w,cy+h/4),255,110,fill=gold,width=max(12,int(24*scale)))
    draw.rectangle((cx-24*scale,cy+h/3,cx+24*scale,cy+h*0.67),fill=gold)
    draw.rounded_rectangle((cx-90*scale,cy+h*0.62,cx+90*scale,cy+h*0.82),radius=int(12*scale),fill=dark)

def _draw_laptop_bundle(draw, x, y, scale=1.0):
    dark=(7,68,50,255)
    blue=(26,95,150,255)
    paper=(244,244,232,255)
    # Livros
    for i,(dx,dy,w) in enumerate(((0,0,220),(22,-48,180),(5,-92,205))):
        draw.rounded_rectangle((x+dx*scale,y+dy*scale,x+(dx+w)*scale,y+(dy+42)*scale),radius=int(10*scale),fill=(255,255,255,235),outline=dark,width=max(2,int(4*scale)))
    # Laptop
    lx=x+65*scale; ly=y-235*scale
    draw.rounded_rectangle((lx,ly,lx+260*scale,ly+175*scale),radius=int(14*scale),fill=dark,outline=(255,255,255,130),width=max(3,int(4*scale)))
    draw.rounded_rectangle((lx+20*scale,ly+20*scale,lx+240*scale,ly+150*scale),radius=int(8*scale),fill=(18,87,120,255))
    draw.polygon([(lx-15*scale,ly+175*scale),(lx+280*scale,ly+175*scale),(lx+245*scale,ly+208*scale),(lx+20*scale,ly+208*scale)],fill=(235,235,225,255),outline=dark)
    # Certificado na tela
    draw.rounded_rectangle((lx+58*scale,ly+55*scale,lx+205*scale,ly+118*scale),radius=int(7*scale),fill=paper)
    draw.ellipse((lx+75*scale,ly+72*scale,lx+108*scale,ly+105*scale),fill=(244,196,40,255))
    draw.line((lx+120*scale,ly+78*scale,lx+186*scale,ly+78*scale),fill=blue,width=max(2,int(4*scale)))
    draw.line((lx+120*scale,ly+95*scale,lx+174*scale,ly+95*scale),fill=blue,width=max(2,int(4*scale)))
    # Lâmpada
    bx=lx+230*scale; by=ly-50*scale
    draw.ellipse((bx-44*scale,by-44*scale,bx+44*scale,by+44*scale),fill=(255,220,60,255),outline=dark,width=max(2,int(4*scale)))
    draw.line((bx-12*scale,by+48*scale,bx+12*scale,by+48*scale),fill=dark,width=max(3,int(5*scale)))

def _draw_volunteer_scene(draw, x, y, scale=1.0):
    colors=((18,84,145,255),(11,108,73,255),(244,188,36,255))
    skin=((92,61,40,255),(126,82,52,255),(178,117,77,255))
    for i,dx in enumerate((-95,0,95)):
        cx=x+dx*scale
        draw.ellipse((cx-34*scale,y-34*scale,cx+34*scale,y+34*scale),fill=skin[i])
        draw.polygon([
            (cx-55*scale,y+42*scale),(cx+55*scale,y+42*scale),
            (cx+72*scale,y+190*scale),(cx-72*scale,y+190*scale)
        ],fill=colors[i],outline=(8,57,45,255))
    # Estádio simplificado
    draw.arc((x-245*scale,y+125*scale,x+245*scale,y+390*scale),180,360,fill=(255,255,255,115),width=max(5,int(9*scale)))
    for n in range(6):
        yy=y+245*scale+n*18*scale
        draw.line((x-220*scale,yy,x+220*scale,yy),fill=(255,255,255,55),width=max(2,int(3*scale)))


def _draw_city_skyline(draw, base_x, base_y, scale=1.0):
    dark=(6,43,62,255)
    light=(255,255,255,105)
    yellow=(255,219,48,220)
    buildings=[
        (0,120,72),(78,180,88),(172,145,62),(240,235,96),(344,165,72)
    ]
    for i,(dx,h,w) in enumerate(buildings):
        x0=base_x+dx*scale; y0=base_y-h*scale
        x1=x0+w*scale; y1=base_y
        fill=dark if i%2==0 else (10,68,86,255)
        draw.rectangle((x0,y0,x1,y1),fill=fill)
        for wy in range(18,int(h)-18,34):
            for wx in range(14,int(w)-12,28):
                draw.rectangle((x0+wx*scale,y0+wy*scale,x0+(wx+8)*scale,y0+(wy+12)*scale),fill=light)
    draw.ellipse((base_x+285*scale,base_y-285*scale,base_x+355*scale,base_y-215*scale),fill=yellow)

def _draw_stadium_scene(draw, cx, cy, scale=1.0):
    white=(255,255,255,120)
    yellow=(255,220,0,180)
    dark=(4,48,56,255)
    # arquibancadas estilizadas
    for i in range(5):
        pad=i*20*scale
        draw.arc((cx-230*scale+pad,cy-120*scale+pad,cx+230*scale-pad,cy+190*scale-pad),180,360,fill=white,width=max(4,int(8*scale)))
    draw.ellipse((cx-165*scale,cy+35*scale,cx+165*scale,cy+120*scale),outline=yellow,width=max(5,int(8*scale)))
    draw.line((cx-165*scale,cy+78*scale,cx+165*scale,cy+78*scale),fill=white,width=max(3,int(5*scale)))
    draw.line((cx,cy+38*scale,cx,cy+118*scale),fill=white,width=max(3,int(5*scale)))
    draw.rectangle((cx-28*scale,cy-165*scale,cx+28*scale,cy-95*scale),fill=dark,outline=white,width=max(2,int(4*scale)))
    draw.line((cx,cy-95*scale,cx,cy-25*scale),fill=white,width=max(3,int(5*scale)))

def _draw_news_ribbons(draw):
    draw.polygon([(0,790),(1080,520),(1080,650),(0,920)],fill=(255,220,0,28))
    draw.polygon([(0,860),(1080,600),(1080,690),(0,960)],fill=(255,255,255,18))
    draw.line((45,775,650,625),fill=(255,220,0,95),width=10)

def render_news_art(out, item, *, font, wrap, fit_title):
    variant=_variant_for(item,4)
    palettes=[
        ((8,47,96),(8,106,76)),
        ((8,58,88),(12,104,78)),
        ((15,61,110),(8,92,76)),
        ((7,54,82),(10,112,83)),
    ]
    top,bottom=palettes[variant]
    im=Image.new("RGB",(1080,1080),top)
    draw=ImageDraw.Draw(im,"RGBA")
    left=105
    text_right=760
    width=text_right-left

    # Fundo mais elaborado, mas mantendo amplo espaço limpo para headline.
    draw.polygon([(0,760),(1080,455),(1080,1080),(0,1080)],fill=(*bottom,255))
    draw.polygon([(735,0),(1080,0),(1080,290)],fill=(255,218,0,238))
    _draw_news_ribbons(draw)
    draw.rectangle((0,0,1080,128),fill=(4,34,54,238))
    draw.text((left,36),"RADAR BRASIL 2027",font=font(36,True),fill="white")
    _pill(draw,(left,166,left+220,228),"NOTÍCIA",font(25,True),(255,220,0,255),(17,43,52,255))

    # Quatro composições visuais para reduzir repetição. Nenhuma usa a antiga
    # bola decorativa no canto inferior direito.
    if variant==0:
        _draw_stadium_lights(draw,860,190,0.78,(255,255,255,105))
        _draw_stadium_lights(draw,1005,170,0.62,(255,255,255,82))
        _draw_footballer(draw,900,405,0.72)
        draw.arc((735,680,1080,1015),200,340,fill=(255,255,255,70),width=9)
    elif variant==1:
        _draw_trophy(draw,905,455,1.0)
        _draw_stadium_scene(draw,900,790,0.72)
        draw.line((770,260,1010,215),fill=(255,255,255,55),width=8)
    elif variant==2:
        _draw_city_skyline(draw,700,900,0.86)
        _draw_stadium_lights(draw,980,250,0.55,(255,255,255,80))
        draw.arc((755,225,1070,540),210,345,fill=(255,220,0,125),width=9)
    else:
        _draw_stadium_scene(draw,895,585,0.92)
        _draw_stadium_lights(draw,780,210,0.54,(255,255,255,80))
        _draw_stadium_lights(draw,1020,205,0.52,(255,255,255,70))
        draw.rounded_rectangle((792,845,1015,930),radius=18,fill=(4,40,54,165),outline=(255,220,0,110),width=3)

    f,lines,readable=_fit(draw,item.get("title"),width,fit_title,start=78,max_lines=4)
    y=292
    for line in lines[:4]:
        draw.text((left,y),line,font=f,fill="white")
        y+=f.size+10

    subtitle=clean(item.get("subtitle"))
    if subtitle:
        sy=max(705,y+30)
        sf=font(23,True)
        for line in wrap(draw,subtitle,sf,width)[:2]:
            draw.text((left,sy),line,font=sf,fill=(230,244,240))
            sy+=33

    draw.rounded_rectangle((left,922,650,980),radius=18,fill=(5,54,54,225),outline=(255,220,0,205),width=2)
    draw.text((left+24,938),"Saiba mais pelo link da bio",font=font(20,True),fill="white")
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    im.save(out,"JPEG",quality=94,optimize=True)
    return readable and f.size>=58 and len(lines)<=4, f.size, len(lines), {
        "visual_mode":"radar_news_illustrated_bank_v2",
        "visual_variant":f"news-{variant+1:02d}",
        "semantic_reason":"owned_illustrated_news_bank_v2",
        "image_credit":"Arte própria do Radar Brasil 2027",
        "license_note":"arte_propria",
    }

def render_opportunity_art(out, item, *, font, wrap, fit_title):
    variant=_variant_for(item,2)
    im=Image.new("RGB",(1080,1080),(249,200,47) if variant==0 else (252,211,66))
    draw=ImageDraw.Draw(im,"RGBA")
    left,right=105,975
    text_right=685
    width=text_right-left
    dark=(5,69,48,255)

    draw.polygon([(0,0),(580,0),(0,310)],fill=(7,82,57,58))
    draw.polygon([(700,1080),(1080,820),(1080,1080)],fill=(11,91,66,255))
    for yy in (250,430,610):
        draw.line((20,yy,625,yy-95),fill=(8,78,57,25),width=18)
    draw.text((left,42),"RADAR BRASIL 2027",font=font(36,True),fill=dark)
    _pill(draw,(left,176,left+330,240),"OPORTUNIDADE",font(24,True),(255,255,255,238),dark)

    if variant==0:
        _draw_laptop_bundle(draw,715,720,0.9)
    else:
        _draw_volunteer_scene(draw,865,610,0.9)
        draw.ellipse((815,240,930,355),fill=(255,221,62,255),outline=dark,width=5)
        draw.line((872,355,872,410),fill=dark,width=8)

    f,lines,readable=_fit(draw,item.get("title"),width,fit_title,start=78,max_lines=4)
    y=320
    for line in lines[:4]:
        draw.text((left,y),line,font=f,fill=dark)
        y+=f.size+10

    category=clean(item.get("category"))
    org=clean(item.get("organization"))
    details=" • ".join(x for x in (category,org) if x)
    if details:
        sy=max(700,y+24)
        sf=font(24,True)
        for line in wrap(draw,details,sf,width)[:2]:
            draw.text((left,sy),line,font=sf,fill=(17,66,52))
            sy+=34

    deadline=clean(item.get("display_date"))
    if deadline:
        draw.rounded_rectangle((left,842,625,905),radius=18,fill=dark)
        draw.text((left+22,859),deadline,font=font(24,True),fill="white")

    draw.rounded_rectangle((left,936,625,994),radius=18,fill=dark)
    draw.text((left+22,952),"Confira e participe • link na bio",font=font(19,True),fill="white")
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    im.save(out,"JPEG",quality=94,optimize=True)
    return readable and f.size>=58 and len(lines)<=4, f.size, len(lines), {
        "visual_mode":"radar_opportunity_illustrated_bank_v1",
        "visual_variant":f"opportunity-{variant+1:02d}",
        "semantic_reason":"owned_illustrated_opportunity_bank",
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
