#!/usr/bin/env python3
"""生成《科研论文核查员》3-4 分钟演示视频的 1920x1080 场景帧。
运行后用 ffmpeg 合成（见脚本末尾打印命令）。
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "video_frames"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080

NAVY = (27, 58, 107)
BLUE = (79, 107, 154)
GREEN = (46, 139, 87)
RED = (192, 57, 43)
GRAY = (95, 102, 112)
LIGHT = (244, 246, 249)
DARK = (26, 27, 28)
WHITE = (255, 255, 255)
LINE = (217, 222, 230)
GOLD = (224, 160, 48)

REG = "/Library/Fonts/Arial Unicode.ttf"
BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
_fc = {}
def F(size, bold=False):
    k = (size, bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(BOLD if bold else REG, size)
    return _fc[k]

def base(bg=WHITE):
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)

def wrap(d, text, fnt, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if d.textlength(cur+ch, font=fnt) <= maxw:
                cur += ch
            else:
                lines.append(cur); cur = ch
        lines.append(cur)
    return lines

def para(d, x, y, text, size, color, maxw, bold=False, lh=1.35, gap=10):
    fnt = F(size, bold)
    for ln in wrap(d, text, fnt, maxw):
        d.text((x, y), ln, font=fnt, fill=color)
        y += int(size*lh)
    return y + gap

def rrect(d, box, r, fill, outline=None, ow=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=ow)

def topbar(d, title, idx=None):
    d.rectangle([0, 0, W, 14], fill=NAVY)
    d.text((70, 48), title, font=F(40, True), fill=NAVY)
    d.rectangle([70, 118, 170, 125], fill=BLUE)
    if idx:
        d.text((W-140, 50), idx, font=F(30, True), fill=LINE)

def shadow_paste(canvas, img, x, y, w, h):
    """把截图缩放为 w×h 贴入，带阴影边框。"""
    im = img.convert("RGB").resize((w, h))
    sh = Image.new("RGBA", (w+40, h+40), (0,0,0,0))
    sdd = ImageDraw.Draw(sh)
    sdd.rounded_rectangle([18,18,w+18,h+18], radius=14, fill=(0,0,0,90))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    canvas.paste(sh, (x-20, y-20), sh)
    canvas.paste(im, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x,y,x+w,y+h], radius=12, outline=(180,190,205), width=2)

def right_panel(d, points, x=1180, y=230, w=660):
    for t, c, big in points:
        rrect(d, [x, y, x+w, y+130], 16, LIGHT)
        d.rectangle([x, y, x+10, y+130], fill=c)
        if big:
            d.text((x+38, y+24), big, font=F(52, True), fill=c)
        para(d, x+38, y+28 if not big else y+86, t, 24, DARK, w-70,
             bold=False, lh=1.25, gap=0)
        y += 155

def save(img, name):
    p = OUT / name
    img.save(p, quality=92)
    return p

# ---------- s01 标题卡 ----------
img, d = base(NAVY)
d.rectangle([0, 600, W, 610], fill=BLUE)
d.text((110, 200), "SciencePal · AI4Science Hackathon 2026", font=F(30, True), fill=(191,208,232))
d.text((110, 300), "科研论文核查员", font=F(108, True), fill=WHITE)
d.text((112, 450), "Paper Reference Verifier", font=F(48), fill=(159,182,214))
d.text((112, 660), "在 SciencePal 沙箱里逐条联网核验参考文献，用可追溯证据替代“凭记忆猜测”", font=F(34), fill=WHITE)
d.text((112, 900), "DOI 真伪核验 · 题录逐字段比对 · 撤稿识别 · 方法学沙箱复算", font=F(30, True), fill=(191,208,232))
d.text((112, 980), "邹亮明 · 邹晶晶 | 香港城市大学 HKAI-Sci | 2026-10-31", font=F(26), fill=(174,194,222))
save(img, "s01.png")

# ---------- s02 问题（PPT 第2页全屏）----------
def ppt_page(n):
    im = Image.open(f"/tmp/ppt_render2/p{n:02d}.png").convert("RGB")
    return im.resize((W, H), Image.LANCZOS)
save(ppt_page(2), "s02.png")
save(ppt_page(3), "s03.png")
save(ppt_page(4), "s09.png")
save(ppt_page(5), "s11.png")

# ---------- 截图讲解页 ----------
def demo_page(name, title, shot, points, idx=None):
    img, d = base()
    topbar(d, title, idx)
    # 截图在左
    sim = Image.open(shot)
    ar = sim.height/sim.width
    sw = 960; sh = int(sw*ar)
    if sh > 820: sh = 820; sw = int(sh/ar)
    shadow_paste(img, sim, 70, (H-sh)//2 - 10, sw, sh)
    # 右侧要点
    right_panel(d, points)
    return img

# s04 引导
img, d = base()
topbar(d, "一、免登录公开回放，执行过程全留痕", "01")
sim = Image.open("/tmp/share_view.png")
ar = sim.height/sim.width; sw=920; sh=int(sw*ar)
if sh>820: sh=820; sw=int(sh/ar)
shadow_paste(img, sim, 90, (H-sh)//2-10, sw, sh)
y = 250
rrect(d, [1130, 250, 1850, 760], 18, LIGHT)
d.text((1170, 300), "打开公开链接即可看到", font=F(32, True), fill=NAVY)
for i, t in enumerate(["无需登录，只读的“智能体运行记录”",
                       "40 步完整执行轨迹，可逐步回放",
                       "每一条沙箱命令、HTTP 状态都可见",
                       "点“跳到结尾”直接看最终报告",
                       "每一步都可独立复核"]):
    d.ellipse([1170, 380+i*72, 1192, 402+i*72], fill=GREEN)
    para(d, 1210, 376+i*72, t, 25, DARK, 600, lh=1.1, gap=0)
save(img, "s04.png")

# s05 HTTP 实测
img = demo_page("s05", "二、逐条联网 Crossref：404 即判 DOI 不存在", "/tmp/demo_done.png",
    [("Agent 在隔离沙箱中对每条 DOI 发起真实 HTTP 请求", RED, "实测"),
     ("[1] 200 真实；[2] 404 判定伪造 DOI 不存在", RED, "HTTP 200 / 404"),
     ("[3][4] 200 后再逐字段比对题录与撤稿", BLUE, "取证"),
     ("不靠记忆，每一条结论都有可复核的来源", GREEN, "可追溯")],
    "02")
save(img, "s05.png")

# s06 最终报告
img = demo_page("s06", "三、四条引用、四种状态：零误判", "/tmp/share_end.png",
    [("[1] LeCun 真实，全部字段匹配，放行", GREEN, "通过"),
     ("[2] DOI 被篡改（404），还指出真实后缀", RED, "幻觉 DOI"),
     ("[3] Crossref 为 2024 年，引用写成 2027", RED, "年份错配"),
     ("[4] STAP 细胞论文已撤稿，未披露", RED, "已撤稿")],
    "03")
save(img, "s06.png")

# s07 撤稿
img = demo_page("s07", "四、撤稿识别：题录合法但已撤稿的 STAP 论文", "/tmp/share_retraction.png",
    [("DOI 有效（HTTP 200），但标题带 RETRACTED ARTICLE", RED, "Retracted: TRUE"),
     ("Agent 主动查询 relation 字段定位撤稿通知", BLUE, "撤稿通知"),
     ("对照正常文献（LeCun）正确放行", GREEN, "对照"),
     ("避免引用已撤稿论文", NAVY, "学术诚信")],
    "04")
save(img, "s07.png")

# s08 方法学
img = demo_page("s08", "五、沙箱复算：报告 p 值与数据矛盾", "/tmp/share_method_end.png",
    [("沙箱安装 scipy 1.15.3，按原始数据真实复算", BLUE, "真实执行"),
     ("报告 p=0.03/0.04，复算 p=0.206/0.138（不显著）", RED, "p 值矛盾"),
     ("两两 t 检验替代 ANOVA；样本量不足（功效0.24）", RED, "方法错误"),
     ("产出可审计复算脚本 recompute_stats.py", GREEN, "证据留痕")],
    "05")
save(img, "s08.png")

# s10 严谨性（自定义）
img, d = base()
topbar(d, "六、为什么结果可信：方法学严谨性", "06")
cards = [
    ("金标准可复现", "用 Crossref 实时构造 valid / not_found / mismatch 三类标签；伪造 DOI 用过去年份、同格式仅篡改后缀并实时验证 404，避免靠未来年份推断。", BLUE),
    ("对照公平可审计", "离线基线禁用 execute_command 与 web_search，SSE 逐条重放审计确认 8 个 run 全程零联网（工具请求被 blocked），确认未获取外部答案。", GREEN),
    ("测试集未调参", "dev 与 test 分离，48 条测试样本（4 个随机种子）从未参与提示词调优；结论由独立测试集给出。", GOLD),
]
x = 70
for t, c, col in cards:
    rrect(d, [x, 220, x+580, 780], 18, LIGHT)
    d.rectangle([x, 220, x+580, 236], fill=col)
    d.text((x+36, 280), t, font=F(36, True), fill=NAVY)
    para(d, x+36, 370, c, 26, DARK, 510, lh=1.4, gap=0)
    x += 610
d.text((70, 880), "结论：核查员三项 F1=1.000、零误报；离线基线幻觉 DOI F1 仅 0.62，共 23 次误报。", font=F(30, True), fill=RED)
save(img, "s10.png")

# s12 结尾
img, d = base(NAVY)
d.text((110, 150), "真实可复现，打开即见全过程", font=F(72, True), fill=WHITE)
links = [
    ("主演示（4 引用 × 4 状态）", "sciencepal.ai/share/ee4068d7-07e5-4a27-9af7-1f3c50fedcaa"),
    ("案例 A · 撤稿识别", "sciencepal.ai/share/f6f8746c-3350-48f1-ac58-d0150e135ac1"),
    ("案例 B · 统计复算", "sciencepal.ai/share/8de1f3cc-cde0-41ad-a2b5-b3b9af5a004b"),
]
y = 330
for t, u in links:
    rrect(d, [110, y, 1810, y+130], 14, (38,74,128))
    d.text((150, y+26), t, font=F(32, True), fill=WHITE)
    d.text((150, y+76), u, font=F(28), fill=(159,182,214))
    y += 160
d.text((110, 880), "配套代码仓库、技术报告、金标准评测集与 SSE 审计报告，支持一键复现。", font=F(30), fill=(191,208,232))
d.text((110, 960), "科研论文核查员 · Paper Reference Verifier", font=F(36, True), fill=WHITE)
save(img, "s12.png")

# 场景时长（秒）
DUR = {"s01":8, "s02":16, "s03":18, "s04":13, "s05":18, "s06":20,
       "s07":17, "s08":22, "s09":19, "s10":15, "s11":18, "s12":9}
import json
(OUT / "durations.json").write_text(json.dumps(DUR, ensure_ascii=False, indent=1))
print("场景帧已生成于", OUT, "总时长", sum(DUR.values()), "秒")

# ---------- ffmpeg 合成 ----------
import subprocess, shutil
seg_dir = OUT / "seg"
seg_dir.mkdir(exist_ok=True)
fps = 30
segs = []
for i, key in enumerate(sorted(DUR.keys()), start=1):
    t = DUR[key]
    frames = t * fps
    seg = seg_dir / f"seg{i:02d}.mp4"
    vf = (
        "scale=3840:2160,"
        f"zoompan=z='min(1.0+0.00075*on,1.10)':d={frames}:"
        "x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s=1920x1080:fps={fps},"
        "fade=t=in:st=0:d=0.5,fade=t=out:st=%.2f:d=0.5,format=yuv420p" % (t-0.5)
    ).format(fps=fps)
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(OUT / f"{key}.png"),
           "-t", str(t), "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-r", str(fps), str(seg)]
    print("生成片段", i, key, t, "秒")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:]); raise SystemExit("ffmpeg 失败 "+key)
    segs.append(seg)

# concat
listf = seg_dir / "list.txt"
listf.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs))
silent = OUT / "video.mp4"
cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
       "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
       "-c:v", "copy", "-c:a", "aac", "-shortest",
       "-movflags", "+faststart", str(silent)]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1500:]); raise SystemExit("concat 失败")

final = ROOT / "assets" / "科研论文核查员_演示视频.mp4"
shutil.move(str(silent), str(final))
print("最终视频:", final, "时长", sum(DUR.values()), "秒")

