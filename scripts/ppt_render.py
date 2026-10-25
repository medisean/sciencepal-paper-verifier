#!/usr/bin/env python3
"""把 pptx 渲染成 PNG 做视觉自检（无 Office 依赖）。
用法: python3 scripts/ppt_render.py <pptx> <out_dir>
支持: 矩形/圆角矩形/右箭头/文本框/图片/表格，颜色、文字、字号、粗体、左中右对齐与自动换行。
"""
import sys, tempfile, os
from pathlib import Path
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image, ImageDraw, ImageFont

S = 120  # px per inch
def emu_px(v): return int(Emu(v).inches * S)

REG = "/Library/Fonts/Arial Unicode.ttf"
BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
_font_cache = {}
def font(size, bold=False):
    key = (round(size), bold)
    if key not in _font_cache:
        path = BOLD if bold else REG
        try:
            _font_cache[key] = ImageFont.truetype(path, max(8,int(size*S/72.0)))
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]

def rgb(c):
    try:
        if c is None: return None
        return (c[0], c[1], c[2])
    except Exception:
        return None

def fill_rgb(shape):
    try:
        if shape.fill.type == 1:  # solid
            c = shape.fill.fore_color.rgb
            return (c[0], c[1], c[2])
    except Exception:
        pass
    return None

def wrap(draw, text, fnt, maxw):
    lines = []
    for hard in text.split("\n"):
        cur = ""
        for ch in hard:
            if draw.textlength(cur + ch, font=fnt) <= maxw:
                cur += ch
            else:
                lines.append(cur); cur = ch
        lines.append(cur)
    return lines

def draw_text(draw, shape, W, H):
    tf = shape.text_frame
    l, t, w, h = emu_px(shape.left), emu_px(shape.top), emu_px(shape.width), emu_px(shape.height)
    ml = emu_px(tf.margin_left or 0); mr = emu_px(tf.margin_right or 0)
    mt = emu_px(tf.margin_top or 0); mb = emu_px(tf.margin_bottom or 0)
    tw = max(10, w - ml - mr)
    blocks = []
    for p in tf.paragraphs:
        align = p.alignment
        runs = p.runs
        if not runs:
            continue
        # 合并同段文字，按每 run 取样式
        for r in runs:
            sz = r.font.size.pt if r.font.size else 14
            col = (0,0,0)
            try:
                if r.font.color and r.font.color.rgb:
                    col = (r.font.color.rgb[0], r.font.color.rgb[1], r.font.color.rgb[2])
            except Exception:
                pass
            fnt = font(sz, bool(r.font.bold))
            lines = wrap(draw, r.text, fnt, tw)
            for ln in lines:
                blocks.append((ln, fnt, col, align, sz))
    # 垂直锚点
    total_h = sum(draw.textbbox((0,0), b[0] if b[0] else " ", font=b[1])[3]-
                  draw.textbbox((0,0), b[0] if b[0] else " ", font=b[1])[1] for b in blocks)
    total_h += len(blocks)*2
    y = t + mt
    if tf.vertical_anchor == MSO_ANCHOR.MIDDLE:
        y = t + max(mt, (h-total_h)//2)
    elif tf.vertical_anchor == MSO_ANCHOR.BOTTOM:
        y = t + h - mb - total_h
    for ln, fnt, col, align, sz in blocks:
        twd = draw.textlength(ln, font=fnt)
        x = l + ml
        if align == PP_ALIGN.CENTER:
            x = l + (w - twd)//2
        elif align == PP_ALIGN.RIGHT:
            x = l + w - mr - twd
        draw.text((x, y), ln, font=fnt, fill=col)
        y += int(sz*S/72.0*1.25) + 2

def render(pptx_path, out_dir):
    prs = Presentation(pptx_path)
    PW, PH = int(prs.slide_width.inches*S), int(prs.slide_height.inches*S)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    for i, slide in enumerate(prs.slides, start=1):
        img = Image.new("RGB", (PW, PH), (255,255,255))
        d = ImageDraw.Draw(img)
        for shape in slide.shapes:
            l,t,w,h = emu_px(shape.left), emu_px(shape.top), emu_px(shape.width), emu_px(shape.height)
            st = shape.shape_type
            if st == MSO_SHAPE_TYPE.PICTURE:
                try:
                    blob = shape.image.blob
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        f.write(blob); tmp=f.name
                    pic = Image.open(tmp).convert("RGB")
                    pic = pic.resize((w,h))
                    img.paste(pic, (l,t)); os.unlink(tmp)
                except Exception as e:
                    print("img err", e)
                continue
            if shape.has_table:
                tb = shape.table
                yy = t
                for ri, row in enumerate(tb.rows):
                    rh = int(row.height*S/914400)
                    xx = l
                    for ci, cell in enumerate(row.cells):
                        cw = int(tb.columns[ci].width*S/914400)
                        bg = fill_rgb(cell) or (255,255,255)
                        d.rectangle([xx,yy,xx+cw,yy+rh], fill=bg)
                        para = cell.text_frame.paragraphs[0]
                        r0 = para.runs[0] if para.runs else None
                        sz = r0.font.size.pt if r0 is not None and r0.font.size else 14
                        col=(0,0,0)
                        if r0 is not None:
                            try:
                                if r0.font.color and r0.font.color.rgb:
                                    col=(r0.font.color.rgb[0],r0.font.color.rgb[1],r0.font.color.rgb[2])
                            except Exception: pass
                        fnt=font(sz, bool(r0 and r0.font.bold))
                        twd=d.textlength(cell.text, font=fnt)
                        tx = xx + (cw-twd)//2 if para.alignment==PP_ALIGN.CENTER else xx+6
                        bbox=d.textbbox((0,0),cell.text,font=fnt)
                        th=bbox[3]-bbox[1]
                        d.text((tx, yy+(rh-th)//2), cell.text, font=fnt, fill=col)
                        d.rectangle([xx,yy,xx+cw,yy+rh], outline=(200,200,200))
                        xx += cw
                    yy += rh
                continue
            # 自动形状
            try:
                auto = shape.auto_shape_type
            except Exception:
                auto = None
            fc = fill_rgb(shape)
            if auto is not None:
                # 右箭头
                if int(auto) == 33:
                    bar = 0.30
                    poly = [(l+w*0.62,t+h*0.12),(l+w*0.62,t+h*0.34),(l,t+h*0.34),
                            (l,t+h*0.66),(l+w*0.62,t+h*0.66),(l+w*0.62,t+h*0.88),
                            (l+w,t+h*0.5)]
                    d.polygon([(int(x),int(y)) for x,y in poly], fill=fc or (95,102,112))
                elif fc is not None:
                    radius = int(min(w,h)*0.12)
                    d.rounded_rectangle([l,t,l+w,t+h], radius=radius, fill=fc)
            if shape.has_text_frame and shape.text_frame.text.strip():
                draw_text(d, shape, PW, PH)
        p = out_dir / f"p{i:02d}.png"
        img.save(p, quality=92)
        print("渲染", p, img.size)

if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
