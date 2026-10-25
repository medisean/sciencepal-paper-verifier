#!/usr/bin/env python3
"""生成《科研论文核查员》黑客松 5 页演示 PPT（16:9）与评测对比图。
依赖: python-pptx, matplotlib。运行: python3 scripts/build_ppt.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
ASSETS = ROOT / "assets"
FIG.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

# ---------- 配色 ----------
NAVY = RGBColor(0x1B, 0x3A, 0x6B)      # 主深科技蓝
BLUE = RGBColor(0x4F, 0x6B, 0x9A)      # 强调蓝
GREEN = RGBColor(0x2E, 0x8B, 0x57)     # 核查 Agent（成功）
RED = RGBColor(0xC0, 0x39, 0x2B)       # 离线基线（错误）
GRAY = RGBColor(0x5F, 0x66, 0x70)      # 次要文本
LIGHT = RGBColor(0xF4, 0xF6, 0xF9)     # 浅底
DARK = RGBColor(0x1A, 0x1B, 0x1C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD9, 0xDE, 0xE6)

# matplotlib 中文字体
for f in ["PingFang SC", "Arial Unicode MS", "Heiti SC", "STHeiti"]:
    try:
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [f]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

# ---------- 读取指标 ----------
m = json.loads((ROOT / "results" / "metrics_summary.json").read_text(encoding="utf-8"))["metrics"]
tasks = ["幻觉 DOI", "题录错配", "任意问题"]
keys = ["hallucinated_doi_detection", "metadata_error_detection", "any_issue_detection"]
vf1 = [m["verifier"][k]["f1"] for k in keys]
nf1 = [m["naive"][k]["f1"] for k in keys]
bf1 = [m["baseline"][k]["f1"] for k in keys]
vfp = [m["verifier"][k]["fp"] for k in keys]
nfp = [m["naive"][k]["fp"] for k in keys]
bfp = [m["baseline"][k]["fp"] for k in keys]
bfn = [m["baseline"][k]["fn"] for k in keys]

# ---------- 图 1：F1 对比（三方） ----------
fig, ax = plt.subplots(figsize=(6.2, 4.1), dpi=200)
import numpy as np
x = np.arange(len(tasks)); w = 0.26
b0 = ax.bar(x - w, bf1, w, label="离线基线（审计零联网）", color="#C0392B")
b2 = ax.bar(x, nf1, w, label="普通联网 Agent（无专家流程）", color="#5B8DB8")
b1 = ax.bar(x + w, vf1, w, label="专家核查工作流（本作品）", color="#2E8B57")
ax.set_ylim(0, 1.18); ax.set_ylabel("F1 分数", fontsize=12)
ax.set_xticks(x); ax.set_xticklabels(tasks, fontsize=12)
ax.set_title("48 条金标准 · 三类检测 F1：联网是闸门（0.62→1.0）", fontsize=12.5, fontweight="bold", color="#1B3A6B")
ax.legend(fontsize=9, loc="lower left", framealpha=0.9)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, ls="--", alpha=0.35); ax.set_axisbelow(True)
for bars, dy in ((b0, 0.015), (b2, 0.015), (b1, 0.06)):
    for r in bars:
        ax.annotate(f"{r.get_height():.2f}", (r.get_x()+r.get_width()/2, r.get_height()+dy),
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
plt.tight_layout()
fig1 = FIG / "ppt_f1_compare.png"; fig.savefig(fig1, bbox_inches="tight"); plt.close(fig)

# ---------- 图 2：误报/漏报对比（三方） ----------
fig, ax = plt.subplots(figsize=(6.2, 3.4), dpi=200)
ax.bar(x - w, bfp, w, label="离线 误报(FP)", color="#C0392B")
ax.bar(x - w, bfn, w, bottom=bfp, label="离线 漏报(FN)", color="#E0A030")
ax.bar(x, nfp, w, label="普通联网 误报", color="#5B8DB8")
ax.bar(x + w, vfp, w, label="专家工作流 误报", color="#2E8B57")
ax.set_xticks(x); ax.set_xticklabels(tasks, fontsize=12)
ax.set_ylabel("错误条数", fontsize=12); ax.set_ylim(0, 12)
ax.set_title("错误分解：两个联网方法均零误报；离线基线共 23 次误报", fontsize=12, fontweight="bold", color="#1B3A6B")
ax.legend(fontsize=8.5, loc="upper right", framealpha=0.9)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, ls="--", alpha=0.35); ax.set_axisbelow(True)
for i, (fp, fn) in enumerate(zip(bfp, bfn)):
    ax.annotate(f"FP{fp}/FN{fn}", (i-w, fp+fn+0.2), ha="center", fontsize=9, color="#7a2a20")
plt.tight_layout()
fig2 = FIG / "ppt_errors.png"; fig.savefig(fig2, bbox_inches="tight"); plt.close(fig)

# ================= PPT =================
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height
FONT = "PingFang SC"

def _set_ea(run, name=FONT):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)

def box(slide, l, t, w, h, fill=None, line=None, line_w=0.75, rounded=False, shadow=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        l, t, w, h)
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid(); shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line; shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    if rounded:
        try:
            shape.adjustments[0] = 0.08
        except Exception:
            pass
    return shape

def text(slide, l, t, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         space_after=6, line_spacing=1.05, wrap=True):
    """runs: list of paragraphs; each paragraph is list of (txt, size, bold, color, font)"""
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(2); tf.margin_right = Pt(2)
    tf.margin_top = Pt(1); tf.margin_bottom = Pt(1)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        p.line_spacing = line_spacing
        for (txt, size, bold, color, *rest) in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = rest[0] if rest else FONT
            _set_ea(r, rest[0] if rest else FONT)
    return tb

def header(slide, idx, title, sub=None):
    box(slide, 0, 0, SW, Inches(0.12), fill=NAVY)
    text(slide, Inches(0.6), Inches(0.42), Inches(11.4), Inches(0.7),
         [[(title, 27, True, NAVY)]], anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(slide, Inches(0.62), Inches(1.12), Inches(12.0), Inches(0.4),
             [[(sub, 13.5, False, GRAY)]])
    box(slide, Inches(0.62), Inches(1.58), Inches(0.62), Pt(3), fill=BLUE)
    text(slide, Inches(12.2), Inches(0.42), Inches(0.7), Inches(0.5),
         [[(f"0{idx}", 16, True, LINE)]], align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)

# ---------- 第 1 页：封面 ----------
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, SW, SH, fill=NAVY)
box(s, 0, Inches(5.05), SW, Inches(0.06), fill=BLUE)
text(s, Inches(0.9), Inches(1.35), Inches(11.5), Inches(0.5),
     [[("SciencePal · AI4Science Hackathon 2026", 15, True, RGBColor(0xBF,0xD0,0xE8))]])
text(s, Inches(0.9), Inches(2.0), Inches(11.6), Inches(1.5),
     [[("科研论文核查员", 54, True, WHITE)]])
text(s, Inches(0.92), Inches(3.25), Inches(11.5), Inches(0.6),
     [[("Paper Reference Verifier", 24, False, RGBColor(0x9F,0xB6,0xD6))]])
text(s, Inches(0.92), Inches(4.15), Inches(11.4), Inches(0.8),
     [[("在 SciencePal 沙箱里逐条联网核验参考文献，用可追溯证据替代“凭记忆猜测”", 17, False, WHITE)]])
tags = ["DOI 真伪核验", "题录逐字段比对", "撤稿识别", "方法学沙箱复算"]
tl = Inches(0.92); tw = Inches(2.72); gap = Inches(0.22)
for i, tag in enumerate(tags):
    l = Emu(int(tl) + i*(int(tw)+int(gap)))
    c = box(s, l, Inches(5.45), tw, Inches(0.62), fill=RGBColor(0x26,0x4A,0x80), rounded=True)
    text(s, l, Inches(5.45), tw, Inches(0.62), [[(tag, 14.5, True, WHITE)]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, Inches(0.92), Inches(6.55), Inches(11.5), Inches(0.5),
     [[("主办：香港城市大学 HKAI-Sci    |    参赛：邹亮明 · 邹晶晶    |    提交截止：2026-10-31", 12.5, False, RGBColor(0xAE,0xC2,0xDE))]])

# ---------- 第 2 页：痛点 + 背景量级 ----------
s = prs.slides.add_slide(BLANK)
header(s, 2, "问题：模型凭记忆无法可靠识别引用幻觉",
       "这不是小概率问题，而是科研可信度的系统性风险；右侧为我们 48 条金标准的实测")
# 左：问题
box(s, Inches(0.6), Inches(1.55), Inches(6.0), Inches(3.55), fill=LIGHT, rounded=True)
text(s, Inches(0.9), Inches(1.68), Inches(5.5), Inches(0.4),
     [[("为什么需要外部证据", 16, True, NAVY)]])
probs = [
    ("编造 DOI", "大模型“编造”参考文献，DOI 格式逼真，肉眼难辨。"),
    ("题录错配", "真实 DOI 配错作者、年份、期刊或卷期页，张冠李戴。"),
    ("撤稿未披露", "被撤稿论文仍被当作正常文献引用，污染证据链。"),
    ("人工成本高", "逐条查库、核对、查撤稿极耗时，审稿难规模化。"),
]
yy = 2.12
for t, d in probs:
    box(s, Inches(0.92), Inches(yy+0.06), Inches(0.14), Inches(0.14), fill=RED)
    text(s, Inches(1.2), Inches(yy-0.04), Inches(5.2), Inches(0.72),
         [[(t+"　", 13.5, True, DARK), (d, 12, False, GRAY)]], line_spacing=1.05)
    yy += 0.74
# 右：实证
box(s, Inches(6.9), Inches(1.55), Inches(5.85), Inches(3.55), fill=WHITE, line=LINE, rounded=True)
text(s, Inches(7.2), Inches(1.68), Inches(5.3), Inches(0.4),
     [[("实测：纯模型只能猜“格式规律”（48 条）", 16, True, NAVY)]])
stats = [
    ("0.62", "幻觉 DOI 检测 F1 仅 0.62，误报 8 次、漏报 3 次", RED),
    ("8 次误报", "用臆想的“期刊 DOI 格式规则”冤枉真实文献", RED),
    ("3 次漏报", "漏掉的恰是格式最规范、最危险的伪造 DOI", RED),
]
yy = 2.15
for big, desc, col in stats:
    text(s, Inches(7.2), Inches(yy), Inches(1.95), Inches(0.66),
         [[(big, 26, True, col)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(9.18), Inches(yy+0.03), Inches(3.45), Inches(0.72),
         [[(desc, 11.5, False, DARK)]], anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05)
    yy += 0.86
box(s, Inches(7.2), Inches(4.7), Inches(5.25), Inches(0.34), fill=RGBColor(0xF7,0xEC,0xEA), rounded=True)
text(s, Inches(7.35), Inches(4.7), Inches(5.0), Inches(0.34),
     [[("结论：没有外部证据，模型无法可靠区分“真”与“逼真”", 12, True, RED)]],
     anchor=MSO_ANCHOR.MIDDLE)
# 底部：背景量级（真实文献）
box(s, Inches(0.6), Inches(5.28), Inches(12.15), Inches(1.9), fill=RGBColor(0xEE,0xF2,0xF8), rounded=True)
text(s, Inches(0.9), Inches(5.38), Inches(11.6), Inches(0.34),
     [[("问题的量级（公开文献，非自测）", 13.5, True, NAVY)]])
bg = [
    ("> 70%", "受访研究者曾尝试却无法复现他人的实验", "Nature 2016  reproducibility survey, n=1576"),
    ("1 万+", "2023 年撤稿论文数创历史纪录，撤稿库累计约 5.5 万条", "Nature 2023；Retraction Watch / Crossref"),
    ("18%", "GPT-4 生成的引用为编造，另有 24% 真实引用有实质错误", "Sci Rep 2023;13:14045"),
]
bx = 0.6
for i, (num, desc, src) in enumerate(bg):
    left = Inches(0.78 + i*4.02)
    box(s, left, Inches(5.78), Inches(3.86), Inches(1.3), fill=WHITE, line=LINE, rounded=True)
    text(s, left+Inches(0.2), Inches(5.88), Inches(3.5), Inches(0.5),
         [[(num, 24, True, RED)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, left+Inches(0.2), Inches(6.38), Inches(3.5), Inches(0.5),
         [[(desc, 11, True, DARK)]], line_spacing=1.05)
    text(s, left+Inches(0.2), Inches(6.82), Inches(3.55), Inches(0.24),
         [[(src, 8.5, False, GRAY)]])

# ---------- 第 3 页：方案 ----------
s = prs.slides.add_slide(BLANK)
header(s, 3, "方案：三层核查 + 证据留痕",
       "创新点是工作流与工程约束，而不是更大的模型")
steps = [
    ("输入\n参考文献", "整批引用一次提交", BLUE),
    ("① DOI 真伪", "Crossref 实时请求\nHTTP 200 / 404", GREEN),
    ("② 题录比对", "年份/作者/标题\n期刊/卷期页", GREEN),
    ("③ 撤稿识别", "标题 RETRACTED\n撤稿通知关联", GREEN),
    ("④ 方法学复算", "沙箱真实执行\nscipy 统计检验", GREEN),
    ("结构化报告", "结论 + 证据 URL\n+ 机器可读 JSON", NAVY),
]
n = len(steps)
cw = Inches(1.78); ch = Inches(1.75); gap = Inches(0.20)
total = int(cw)*n + int(gap)*(n-1)
startx = (int(SW)-total)//2
yy = Inches(2.25)
for i, (t, d, col) in enumerate(steps):
    l = Emu(startx + i*(int(cw)+int(gap)))
    box(s, l, yy, cw, ch, fill=col, rounded=True)
    text(s, l, yy+Inches(0.18), cw, Inches(0.75),
         [[(line, 15, True, WHITE)] for line in t.split("\n")],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=1, line_spacing=1.0)
    text(s, l, yy+Inches(0.98), cw, Inches(0.7),
         [[(line, 10.5, False, RGBColor(0xE8,0xEE,0xF7))] for line in d.split("\n")],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=0, line_spacing=1.05)
    if i < n-1:
        ax_ = Emu(int(l)+int(cw)+Emu(20000))
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, ax_, yy+Inches(0.72),
                                int(gap)-Emu(40000), Inches(0.3))
        ar.fill.solid(); ar.fill.fore_color.rgb = GRAY; ar.line.fill.background()
        ar.shadow.inherit = False
# 原则
box(s, Inches(0.6), Inches(4.55), Inches(5.95), Inches(2.1), fill=LIGHT, rounded=True)
text(s, Inches(0.88), Inches(4.75), Inches(5.4), Inches(0.4),
     [[("设计原则一 · 强制取证", 15, True, NAVY)]])
text(s, Inches(0.88), Inches(5.2), Inches(5.45), Inches(1.3),
     [[("每条引用必须联网查询 Crossref，禁止凭记忆作答；", 13, False, DARK)],
      [("HTTP 状态、来源 URL、沙箱复算脚本全部留痕，可逐条复核。", 13, False, DARK)]],
     line_spacing=1.2)
box(s, Inches(6.78), Inches(4.55), Inches(5.95), Inches(2.1), fill=LIGHT, rounded=True)
text(s, Inches(7.06), Inches(4.75), Inches(5.4), Inches(0.4),
     [[("设计原则二 · 人机协同", 15, True, NAVY)]])
text(s, Inches(7.06), Inches(5.2), Inches(5.45), Inches(1.3),
     [[("不确定即标记 suspect 并交人工复核，不武断下结论；", 13, False, DARK)],
      [("定位为审稿 / 作者自检助手，不替代同行评议。", 13, False, DARK)]],
     line_spacing=1.2)

# ---------- 第 4 页：两个主结果 ----------
s = prs.slides.add_slide(BLANK)
header(s, 4, "两个主结果：联网是能力闸门，流程固化可复现的过程约束",
       "48 条独立测试集；三方对照（离线 / 普通联网 / 专家工作流），SSE 审计确认公平")
# 左：主结果① 标签 + F1 图
box(s, Inches(0.55), Inches(1.6), Inches(5.55), Inches(0.36), fill=NAVY, rounded=True)
text(s, Inches(0.55), Inches(1.6), Inches(5.55), Inches(0.36),
     [[("主结果① 能力闸门：一联网，F1 0.62→1.0、误报 23→0", 12.5, True, WHITE)]],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
s.shapes.add_picture(str(fig1), Inches(0.6), Inches(2.05), width=Inches(5.45))

# 右：主结果② 标签 + 过程指标卡
GREEN_L = RGBColor(0xEC, 0xF4, 0xEF)
box(s, Inches(6.35), Inches(1.6), Inches(6.45), Inches(0.36), fill=GREEN, rounded=True)
text(s, Inches(6.35), Inches(1.6), Inches(6.45), Inches(0.36),
     [[("主结果② 过程约束：专家工作流相对普通 Agent 的可审计增益", 12.5, True, WHITE)]],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
proc = [
    ("平均工具调用 / 轮", "7 轮均值，路径更短、token 更省", "8.3", "12.4"),
    ("违禁写入长期记忆", "普通 Agent 被禁仍调用 save_memory", "0 次", "1 次"),
    ("最终 JSON 输出", "固定 schema，便于无人值守解析", "末轮固定", "1 次错位"),
    ("检查覆盖与留痕", "专家强制 C1-C4/M1-M5 全流程，留 HTTP 状态、来源、脚本", "全流程", "基础取证"),
]
yt = 2.08
for name, note, expv, ordv in proc:
    box(s, Inches(6.35), Inches(yt), Inches(6.45), Inches(0.93), fill=LIGHT, rounded=True)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.35), Inches(yt),
                             Inches(0.08), Inches(0.93))
    bar.fill.solid(); bar.fill.fore_color.rgb = GREEN; bar.line.fill.background()
    bar.shadow.inherit = False
    # 左栏：指标名 + 说明
    text(s, Inches(6.58), Inches(yt+0.1), Inches(3.05), Inches(0.36),
         [[(name, 12.5, True, NAVY)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(6.58), Inches(yt+0.5), Inches(3.1), Inches(0.38),
         [[(note, 9.5, False, GRAY)]], anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0)
    # 右栏：专家（绿）/ 普通（蓝）两行，标签与值独立文本框对齐
    text(s, Inches(9.7), Inches(yt+0.13), Inches(0.55), Inches(0.32),
         [[("专家", 11, False, GRAY)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(10.3), Inches(yt+0.08), Inches(2.45), Inches(0.38),
         [[(expv, 13.5, True, GREEN)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(9.7), Inches(yt+0.53), Inches(0.55), Inches(0.32),
         [[("普通", 11, False, GRAY)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(10.3), Inches(yt+0.48), Inches(2.45), Inches(0.38),
         [[(ordv, 13.5, True, BLUE)]], anchor=MSO_ANCHOR.MIDDLE)
    yt += 1.02

# 底部：诚实解读
box(s, Inches(0.55), Inches(6.16), Inches(12.25), Inches(1.26), fill=RGBColor(0xEE,0xF2,0xF8), rounded=True)
text(s, Inches(0.8), Inches(6.21), Inches(11.9), Inches(0.28),
     [[("如何读这两个结果：诚实、不设弱对手", 12, True, NAVY)]])
text(s, Inches(0.8), Inches(6.5), Inches(11.95), Inches(0.9),
     [[("· H1 成立：联网是硬闸门，F1 0.62→1.0、误报 23→0；H2 阴性：强模型上专家流程不额外提高 F1，不宣称更准。", 10, False, DARK)],
      [("· 专家流程是提示词/工作流层约束（非代码级强制）；右侧过程指标为 n=7 对 n=7 的小样本观测，“0 次/1 次”是观察到的事件，未做统计检验，不作为显著结论。", 10, False, DARK)],
      [("· 撤稿、统计复算、2026 冷门撤稿限定任务同输入对照均判对；局限：仅单模型、n=48（Wilson 下界 0.926）、弱模型增益待验。", 10, False, DARK)]],
     line_spacing=1.05, space_after=1)

# ---------- 第 5 页：交付与演示 ----------
s = prs.slides.add_slide(BLANK)
header(s, 5, "真实可复现：打开公开链接即见全过程",
       "免登录只读回放，完整保留沙箱执行轨迹与最终报告")
cards = [
    ("主演示 · 一屏四态", "4 条引用分别命中：真实放行 / 404 篡改 DOI / 年份错配 / STAP 撤稿",
     "sciencepal.ai/share/ee4068d7-07e5-4a27-9af7-1f3c50fedcaa"),
    ("案例 A · 撤稿识别", "识别被当正常引用的 STAP 论文，定位官方撤稿通知 DOI",
     "sciencepal.ai/share/f6f8746c-3350-48f1-ac58-d0150e135ac1"),
    ("案例 B · 统计复算", "沙箱 scipy 复算发现 p 值与数据矛盾：报告 0.03/0.04，实算 0.206/0.138",
     "sciencepal.ai/share/8de1f3cc-cde0-41ad-a2b5-b3b9af5a004b"),
]
cw = Inches(3.95); ch = Inches(2.2); gap = Inches(0.18)
startx = int(Inches(0.6))
for i, (t, d, link) in enumerate(cards):
    l = Emu(startx + i*(int(cw)+int(gap)))
    box(s, l, Inches(2.0), cw, ch, fill=WHITE, line=LINE, rounded=True)
    box(s, l, Inches(2.0), cw, Inches(0.14), fill=GREEN)
    text(s, l+Inches(0.22), Inches(2.24), cw-Inches(0.44), Inches(0.55),
         [[(t, 15.5, True, NAVY)]], line_spacing=1.0)
    text(s, l+Inches(0.22), Inches(2.82), cw-Inches(0.44), Inches(0.82),
         [[(d, 11.5, False, DARK)]], line_spacing=1.12)
    text(s, l+Inches(0.22), Inches(3.74), cw-Inches(0.38), Inches(0.42),
         [[(link, 9, False, BLUE)]], line_spacing=1.0)
# 复现材料 + 未来
box(s, Inches(0.6), Inches(4.5), Inches(5.95), Inches(2.3), fill=LIGHT, rounded=True)
text(s, Inches(0.88), Inches(4.7), Inches(5.4), Inches(0.4),
     [[("随附可复现材料", 15, True, NAVY)]])
text(s, Inches(0.88), Inches(5.15), Inches(5.5), Inches(1.6),
     [[("· 代码仓库：评测集生成 / 跑批 / 评分 / 审计全脚本", 12.5, False, DARK)],
      [("· 一键复现：run_batch + run_naive → export → audit", 12.5, False, DARK)],
      [("· 三方对照技术报告、逐条结果、12 run SSE 审计、Layer-2 案例", 12.5, False, DARK)],
      [("· 原创性与资源使用声明", 12.5, False, DARK)]],
     line_spacing=1.18, space_after=4)
box(s, Inches(6.78), Inches(4.5), Inches(5.95), Inches(2.3), fill=LIGHT, rounded=True)
text(s, Inches(7.06), Inches(4.7), Inches(5.4), Inches(0.4),
     [[("未来工作", 15, True, NAVY)]])
text(s, Inches(7.06), Inches(5.15), Inches(5.5), Inches(1.6),
     [[("· 接入 Retraction Watch / Crossref Event Data", 12.5, False, DARK)],
      [("· 整稿批量审稿与投稿前自检插件", 12.5, False, DARK)],
      [("· 扩展多学科统计 / 图表复算与图像查伪", 12.5, False, DARK)],
      [("· 引用可信度评分与期刊工作流集成", 12.5, False, DARK)]],
     line_spacing=1.18, space_after=4)

out = ASSETS / "科研论文核查员.pptx"
prs.save(str(out))
print("已生成:", out)
print("图表:", fig1, fig2)
