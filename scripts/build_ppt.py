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

# ---------- 第 2 页：痛点 ----------
s = prs.slides.add_slide(BLANK)
header(s, 2, "问题：模型凭记忆无法可靠识别引用幻觉",
       "纯模型离线基线在 48 条金标准上的实测表现")
# 左：问题
box(s, Inches(0.6), Inches(1.95), Inches(6.0), Inches(4.9), fill=LIGHT, rounded=True)
text(s, Inches(0.9), Inches(2.15), Inches(5.5), Inches(0.45),
     [[("为什么需要外部证据", 17, True, NAVY)]])
probs = [
    ("编造 DOI", "大模型撰写/审查文献时会“编造”参考文献，且 DOI 格式高度逼真，肉眼难辨。"),
    ("题录错配", "真实 DOI 配错作者、年份、期刊或卷期页，张冠李戴却看似规范。"),
    ("撤稿未披露", "被撤稿论文仍被当作正常文献引用，污染证据链。"),
    ("人工成本高", "逐条查库、核对、查撤稿极耗时，审稿与自查难以规模化。"),
]
yy = 2.72
for t, d in probs:
    box(s, Inches(0.92), Inches(yy+0.06), Inches(0.14), Inches(0.14), fill=RED)
    text(s, Inches(1.2), Inches(yy-0.05), Inches(5.15), Inches(0.95),
         [[(t+"　", 14, True, DARK), (d, 12.5, False, GRAY)]], line_spacing=1.08)
    yy += 1.02
# 右：实证
box(s, Inches(6.9), Inches(1.95), Inches(5.85), Inches(4.9), fill=WHITE, line=LINE, rounded=True)
text(s, Inches(7.2), Inches(2.15), Inches(5.3), Inches(0.45),
     [[("实测：纯模型只能猜“格式规律”", 17, True, NAVY)]])
stats = [
    ("0.62", "幻觉 DOI 检测 F1 仅为 0.62，误报 8 次、漏报 3 次", RED),
    ("8 次误报", "用臆想的“期刊 DOI 格式规则”冤枉真实文献", RED),
    ("3 次漏报", "漏掉的恰是格式最规范、最危险的伪造 DOI", RED),
]
yy = 2.78
for big, desc, col in stats:
    text(s, Inches(7.2), Inches(yy), Inches(2.0), Inches(0.7),
         [[(big, 30, True, col)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(9.25), Inches(yy+0.05), Inches(3.3), Inches(0.85),
         [[(desc, 12.5, False, DARK)]], anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.1)
    yy += 1.15
box(s, Inches(7.2), Inches(6.05), Inches(5.25), Inches(0.62), fill=RGBColor(0xF7,0xEC,0xEA), rounded=True)
text(s, Inches(7.35), Inches(6.05), Inches(5.0), Inches(0.62),
     [[("结论：没有外部证据，模型无法可靠区分“真”与“逼真”", 12.5, True, RED)]],
     anchor=MSO_ANCHOR.MIDDLE)

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

# ---------- 第 4 页：结果 ----------
s = prs.slides.add_slide(BLANK)
header(s, 4, "结果：联网是决定性闸门（F1 0.62→1.0），专家流程固化确定性",
       "48 条独立测试集；三方对照（离线 / 普通联网 / 专家工作流），SSE 审计确认公平")
s.shapes.add_picture(str(fig1), Inches(0.55), Inches(2.0), width=Inches(5.5))
# 表格（三方 F1）
rows = [["检测任务", "离线基线", "普通联网", "专家工作流"],
        ["幻觉 DOI", "0.62", "1.00", "1.00"],
        ["题录错配", "0.82", "1.00", "1.00"],
        ["任意问题", "0.82", "1.00", "1.00"]]
tl, tt, tw_, th = Inches(7.35), Inches(2.1), Inches(5.4), Inches(2.5)
COLW = [Inches(1.62), Inches(1.26), Inches(1.26), Inches(1.26)]
COLR = [None, RED, BLUE, GREEN]
tbl = s.shapes.add_table(4, 4, tl, tt, tw_, th).table
for c in range(4):
    tbl.columns[c].width = COLW[c]
for r in range(4):
    for c in range(4):
        cell = tbl.cell(r, c)
        cell.text = rows[r][c]
        para = cell.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
        run = para.runs[0]
        run.font.size = Pt(12.5 if r == 0 else 14)
        run.font.name = FONT; _set_ea(run)
        run.font.bold = (r == 0 or c > 0)
        run.font.color.rgb = WHITE if r == 0 else (COLR[c] if c > 0 else DARK)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if r == 0 else (LIGHT if r % 2 else WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
# 右侧结论框
box(s, Inches(7.35), Inches(4.95), Inches(5.4), Inches(1.18), fill=RGBColor(0xEC,0xF4,0xEF), rounded=True)
text(s, Inches(7.6), Inches(4.98), Inches(5.0), Inches(1.14),
     [[("两个联网方法均 0 误报 / 0 漏报", 13.5, True, GREEN)],
      [("离线基线：合计 23 次误报、7 次漏报", 12, True, RED)],
      [("强模型上专家流程无额外 F1 增益，价值在确定性", 11, True, NAVY)]],
     anchor=MSO_ANCHOR.MIDDLE, space_after=2, line_spacing=1.12)
# 方法学严谨性
box(s, Inches(0.55), Inches(6.35), Inches(12.2), Inches(1.0), fill=LIGHT, rounded=True)
text(s, Inches(0.8), Inches(6.42), Inches(12.0), Inches(0.3),
     [[("对照严谨性与诚实结论", 13, True, NAVY)]])
text(s, Inches(0.8), Inches(6.72), Inches(11.9), Inches(0.6),
     [[("· 增设工具全开、能联网但不给专家流程的普通 Agent 作对照，防止稻草人基线；撤稿、统计复算、2026 冷门撤稿限定任务同输入对照，两个联网 Agent 都能做对。", 11, False, DARK)],
      [("· 专家流程差异在过程：平均工具调用更少、无长期记忆污染、JSON 稳定可解析；全流程留证据、可审计。局限：仅单模型、n=48，弱模型增益待验。", 11, False, DARK)]],
     line_spacing=1.1, space_after=2)

# ---------- 第 5 页：交付与演示 ----------
s = prs.slides.add_slide(BLANK)
header(s, 5, "真实可复现：打开公开链接即见全过程",
       "免登录只读回放，完整保留沙箱执行轨迹与最终报告")
cards = [
    ("主演示 · 一屏四态", "4 条引用分别命中：真实放行 / 404 篡改 DOI / 年份错配 / STAP 撤稿",
     "sciencepal.ai/share/ee4068d7…"),
    ("案例 A · 撤稿识别", "识别被当正常引用的 STAP 论文，定位官方撤稿通知 DOI",
     "sciencepal.ai/share/f6f8746c…"),
    ("案例 B · 统计复算", "沙箱 scipy 复算发现 p 值与数据矛盾：报告 0.03/0.04，实算 0.206/0.138",
     "sciencepal.ai/share/8de1f3cc…"),
]
cw = Inches(3.95); ch = Inches(2.2); gap = Inches(0.18)
startx = int(Inches(0.6))
for i, (t, d, link) in enumerate(cards):
    l = Emu(startx + i*(int(cw)+int(gap)))
    box(s, l, Inches(2.0), cw, ch, fill=WHITE, line=LINE, rounded=True)
    box(s, l, Inches(2.0), cw, Inches(0.14), fill=GREEN)
    text(s, l+Inches(0.22), Inches(2.28), cw-Inches(0.44), Inches(0.6),
         [[(t, 15.5, True, NAVY)]], line_spacing=1.0)
    text(s, l+Inches(0.22), Inches(2.92), cw-Inches(0.44), Inches(0.95),
         [[(d, 12, False, DARK)]], line_spacing=1.15)
    text(s, l+Inches(0.22), Inches(3.82), cw-Inches(0.44), Inches(0.35),
         [[(link, 10.5, False, BLUE)]])
# 复现材料 + 未来
box(s, Inches(0.6), Inches(4.5), Inches(5.95), Inches(2.3), fill=LIGHT, rounded=True)
text(s, Inches(0.88), Inches(4.7), Inches(5.4), Inches(0.4),
     [[("随附可复现材料", 15, True, NAVY)]])
text(s, Inches(0.88), Inches(5.15), Inches(5.5), Inches(1.6),
     [[("· 代码仓库：评测集生成 / 跑批 / 评分 / 审计全脚本", 12.5, False, DARK)],
      [("· 一键复现：run_batch → export → audit", 12.5, False, DARK)],
      [("· 技术报告、逐条结果、SSE 审计报告、Layer-2 案例", 12.5, False, DARK)],
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
