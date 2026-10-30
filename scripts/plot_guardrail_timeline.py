"""把一次真实拦截画成时间线：核查 → 越权调用 → stop → 纠正 → 续跑 → 合规交付。

数据源是这次 run 的原始 SSE（output/runs/*.jsonl），不是示意图：
横轴是事件自带的 created_at，纵轴只有两条泳道（被拦截轮 / 续跑轮）。
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import project_root  # noqa: E402

ROOT = project_root()
FIG = ROOT / "results" / "figures"
CASE = ROOT / "results" / "guardrail" / "guarded__adv_memory_write_seed7.json"

for f in ["PingFang SC", "Arial Unicode MS", "Heiti SC", "STHeiti"]:
    try:
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

NAVY, GREEN, RED, GRAY, BLUE = "#1B3A6B", "#2E8B57", "#C0392B", "#8A9099", "#4F6B9A"


def load(run_id: str) -> list[dict]:
    p = ROOT / "output" / "runs" / f"{run_id}.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def t0(events: list[dict]) -> dt.datetime | None:
    for e in events:
        s = e.get("created_at")
        if s:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return None


def stamp(e: dict) -> dt.datetime | None:
    s = e.get("created_at")
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def tool_name(e: dict) -> str | None:
    if e.get("type") != "tool":
        return None
    c = e.get("content")
    if isinstance(c, str):
        try:
            c = json.loads(c)
        except json.JSONDecodeError:
            return None
    return (c or {}).get("name") if isinstance(c, dict) else None


def main() -> None:
    meta = json.loads(CASE.read_text(encoding="utf-8"))
    stopped_run, final_run = meta["rounds"][0]["run_id"], meta["rounds"][1]["run_id"]
    ev1, ev2 = load(stopped_run), load(final_run)
    start = t0(ev1)
    end1 = max(s for s in (stamp(e) for e in ev1) if s)
    end2 = max(s for s in (stamp(e) for e in ev2) if s)
    off = lambda x: (x - start).total_seconds()  # noqa: E731

    fig, ax = plt.subplots(figsize=(11.2, 3.5))
    lanes = {1: 1.0, 0: 0.0}
    for lane, label in ((1, "第 1 轮（被拦截）"), (0, "第 2 轮（纠正后续跑）")):
        ax.axhline(lanes[lane], color="#E6EAF0", lw=14, zorder=0)
        ax.text(-3.0, lanes[lane], label, ha="right", va="center", fontsize=10, color=NAVY)

    # 第 1 轮：逐条取证
    xs, labels = [], []
    for e in ev1:
        n = tool_name(e)
        if n in ("execute_command", "watch_task"):
            s = stamp(e)
            if s:
                xs.append(off(s))
                labels.append(n)
    first = min(xs) if xs else 0
    last_tool = max(xs) if xs else 0
    ax.scatter(xs, [lanes[1]] * len(xs), s=42, color=BLUE, zorder=3, label="逐条 curl / 读取输出")
    ax.plot([first, last_tool], [lanes[1]] * 2, color=BLUE, lw=2, zorder=2)
    n_exec = sum(1 for e in ev1 if tool_name(e) == "execute_command")
    ax.text((first + last_tool) / 2, lanes[1] + 0.22,
            f"12 条引用逐条联网核验（{n_exec} 次批量命令）",
            ha="center", fontsize=9.5, color=BLUE)

    # 越权调用与 stop
    for e in ev1:
        if tool_name(e) == "save_memory":
            s = stamp(e)
            if s:
                ax.scatter([off(s)], [lanes[1]], marker="D", s=90, color=RED, zorder=4,
                           label="save_memory（被禁）")
                ax.axvline(off(s), color=RED, ls="--", lw=1.2, zorder=1)
                ax.annotate(f"stop 往返 {meta['interventions'][0]['detail'].split('往返 ')[-1]}",
                            xy=(off(s), lanes[1]), xytext=(off(s) - 26, lanes[1] - 0.42),
                            fontsize=9, color=RED,
                            arrowprops=dict(arrowstyle="->", color=RED, lw=1))
    ax.text(off(end1), lanes[1] - 0.42, "运行被中断", fontsize=9, color=RED)

    # 第 2 轮
    stamps2 = [x for x in (stamp(e) for e in ev2) if x]
    s2, e2 = (min(stamps2), max(stamps2)) if stamps2 else (None, None)
    if s2 and e2:
        ax.plot([off(s2), off(e2)], [lanes[0]] * 2, color=GREEN, lw=3, zorder=2)
        ax.scatter([off(s2)], [lanes[0]], s=60, color=GREEN, zorder=3, label="纠正指令 → 续跑")
        ax.scatter([off(e2)], [lanes[0]], marker="*", s=260, color=GREEN, zorder=4,
                   label="交付契约通过（12/12 · F1 1.000）")

    ax.set_xlim(-22, off(end2) + 6)
    ax.set_ylim(-0.85, 1.55)
    ax.set_yticks([])
    ax.set_xlabel("距 run 开始的时间（秒，取自 SSE 事件的 created_at）", fontsize=9.5)
    ax.set_title("一次真实拦截的全过程：核验 → 越权调用 → 拦截 → 纠正 → 合规交付",
                 fontsize=12.5, fontweight="bold", color=NAVY, pad=10)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left", ncol=4,
              bbox_to_anchor=(0.0, 1.02))
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    out = FIG / "guardrail_timeline.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print("saved:", out, "| 两轮起止:", round(off(end1), 1), "s /", round(off(end2), 1), "s")


if __name__ == "__main__":
    main()
