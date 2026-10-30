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

# ---------- s04 公开回放 ----------
img, d = base()
topbar(d, "一、免登录公开回放：每一步都可复核", "01")
sim = Image.open("/tmp/share_view.png")
ar = sim.height/sim.width; sw=920; sh=int(sw*ar)
if sh>820: sh=820; sw=int(sh/ar)
shadow_paste(img, sim, 90, (H-sh)//2-10, sw, sh)
right_panel(d, [
    ("无需登录、只读回放，评审打开即可看", BLUE, None),
    ("39 步完整执行轨迹，可逐步回放", GREEN, None),
    ("每条沙箱命令与 HTTP 状态都可见", GOLD, None),
    ("点“跳到结尾”直接看最终报告", NAVY, None),
], x=1120, y=250, w=700)
save(img, "s04.png")

# ---------- s05 一次真实拦截的时间线 ----------
img, d = base()
topbar(d, "二、一次真实拦截：核验 → 越权调用 → 拦截 → 纠正", "02")
fig = Image.open(str(ROOT / "results" / "figures" / "guardrail_timeline.png"))
fw = 1780; fh = int(fw * fig.height / fig.width)
shadow_paste(img, fig, 70, 210, fw, fh)
d.text((70, 210+fh+30), "120 秒时尝试调用 save_memory（被禁）→ guardrail 2.1 秒内 stop → 纠正后续跑 → 160 秒输出合规 JSON",
       font=F(27, True), fill=NAVY)
d.text((70, 210+fh+78), "数据取自真实 run 的 SSE 事件时间戳，不是示意图。",
       font=F(24), fill=GRAY)
save(img, "s05.png")

# ---------- s06 干预前后对照 ----------
img, d = base()
topbar(d, "三、干预前后：交付可用 4/6 → 6/6", "03")
fig = Image.open(str(ROOT / "results" / "figures" / "guardrail_compare.png"))
fw = 1780; fh = int(fw * fig.height / fig.width)
shadow_paste(img, fig, 70, 220, fw, fh)
d.text((70, 220+fh+34), "6 个稿件注入用例：漏查条目、篡改 schema 各 1 例会让交付直接不可用（F1=0）；有 guardrail 时全部修复为合规交付。",
       font=F(25), fill=DARK)
d.text((70, 220+fh+80), "代价如实标注：修复要重发上下文，平均 token +82%、墙钟 +48%。", font=F(25, True), fill=RED)
save(img, "s06.png")

# ---------- s07 交付契约与回溯审计 ----------
img, d = base()
topbar(d, "四、交付契约：四类校验 + 35 个 run 回溯审计", "04")
rules = [
    ("S 结构", "字段齐全、类型正确、枚举合法、置信度 ∈ [0,1]"),
    ("C 覆盖", "references 必须恰好覆盖 1..N，不多不少不重"),
    ("E 证据", "结论必须给 evidence_url，且指向该条 DOI 的权威来源"),
    ("V 自洽", "metadata_match=false 不得配 pass；not_found 不得配 match=true"),
]
y = 210
for k, v in rules:
    rrect(d, [70, y, 1130, y+92], 14, LIGHT)
    d.text((100, y+28), k, font=F(30, True), fill=NAVY)
    d.text((330, y+30), v, font=F(25), fill=DARK)
    y += 105
# 右侧审计表
rrect(d, [1180, 210, 1850, 700], 16, LIGHT)
d.text((1210, 236), "契约回溯审计", font=F(28, True), fill=NAVY)
audit = [("专家核查工作流", "5/5"), ("guardrail 开启", "11/11"),
         ("guardrail 关闭", "5/7"), ("普通联网 Agent", "2/4"), ("离线基线", "0/7")]
yy = 300
for name, val in audit:
    d.text((1210, yy), name, font=F(24), fill=DARK)
    d.text((1740, yy-6), val, font=F(30, True), fill=(GREEN if val.split("/")[0] == val.split("/")[1] else RED))
    yy += 72
d.text((70, 720), "契约不是事后编的：专家、普通、离线三组结果都在契约定稿之前跑出，原样套用同一套判据。", font=F(24), fill=GRAY)
d.text((70, 780), "普通联网 Agent 的失败是“证据张冠李戴”：对不存在的 DOI 填了最接近的真实 DOI，F1 仍 1.0，但点开链接是另一篇文献。", font=F(24), fill=GRAY)
save(img, "s07.png")

# ---------- s08 结果页（PPT 第4页全屏）----------
save(ppt_page(4), "s08.png")

# ---------- s09 为什么结果可信 ----------
img, d = base()
topbar(d, "六、为什么结果可信：方法学严谨性", "06")
cards = [
    ("金标准可复现", "用 Crossref 实时构造 valid / not_found / mismatch 三类标签；伪造 DOI 仅篡改后缀并实时验证 404，避免靠未来年份推断。", BLUE),
    ("三方对照防稻草人", "离线基线关闭工具并用 SSE 审计确认零联网；另设工具全开、给基础取证指令但不教专家流程的普通 Agent，同输入对比。", GREEN),
    ("测试集未调参", "dev 与 test 分离，48 条测试样本（4 个随机种子）从未参与提示词调优；结论只由未调参的测试集给出。", GOLD),
]
x = 70
for t, c, col in cards:
    rrect(d, [x, 220, x+580, 780], 18, LIGHT)
    d.rectangle([x, 220, x+580, 236], fill=col)
    d.text((x+36, 280), t, font=F(36, True), fill=NAVY)
    para(d, x+36, 370, c, 26, DARK, 510, lh=1.4, gap=0)
    x += 610
d.text((70, 870), "主结果一（能力）：联网是能力闸门，F1 0.62→1.0、误报 23→0。", font=F(28, True), fill=RED)
d.text((70, 925), "主结果二（交付）：代码级 guardrail 把“必须覆盖、必须留证、不许写记忆”变成机制保证。", font=F(26, True), fill=NAVY)
save(img, "s09.png")

# ---------- s10 交付页（PPT 第5页全屏）----------
save(ppt_page(5), "s10.png")

# ---------- s11 结尾 ----------
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
d.text((110, 880), "配套代码仓库、技术报告、金标准评测集、SSE 审计与 guardrail 协议，支持一键复现。", font=F(30), fill=(191,208,232))
d.text((110, 960), "科研论文核查员 · Paper Reference Verifier", font=F(36, True), fill=WHITE)
save(img, "s11.png")

# 场景时长（秒）
DUR = {"s01": 8, "s02": 17, "s03": 19, "s04": 15, "s05": 24, "s06": 18,
       "s07": 22, "s08": 20, "s09": 16, "s10": 18, "s11": 9}
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
        f"zoompan=z='min(1.0+0.00025*on,1.02)':d={frames}:"
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

