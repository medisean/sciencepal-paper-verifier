"""把 guardrail 对照结果画成图（无需联网，读 results/guardrail/summary.json）。

左：6 例注入下的交付可用数与契约违规数
右：代价（平均 token / 平均墙钟）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

for f in ["PingFang SC", "Arial Unicode MS", "Heiti SC", "STHeiti"]:
    try:
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

RED = "#C0392B"
GREEN = "#2E8B57"
GRAY = "#8A9099"


def main() -> None:
    s = json.loads((ROOT / "results" / "guardrail" / "summary.json").read_text(encoding="utf-8"))
    adv = s["adversarial"]
    u, g = adv["unguarded"], adv["guarded"]
    n = u["n"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    labels = ["交付可用", "契约违规"]
    uv = [u["usable"], u["contract_violations"]]
    gv = [g["usable"], g["contract_violations"]]
    x = range(len(labels))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], uv, w, label="无 guardrail", color=RED)
    b2 = ax.bar([i + w / 2 for i in x], gv, w, label="有 guardrail", color=GREEN)
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.12,
                    f"{int(r.get_height())}", ha="center", fontsize=11, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, n + 1.2)
    ax.set_ylabel(f"run 数（共 {n} 例注入）", fontsize=10)
    ax.set_title("稿件注入下的交付契约", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    ax = axes[1]
    metrics = ["平均 token (k)", "平均墙钟 (s)"]
    uv = [u["total_tokens"] / n / 1000, u["mean_wall_s"]]
    gv = [g["total_tokens"] / n / 1000, g["mean_wall_s"]]
    # 两个量纲不同，分开归一化展示（以无 guardrail 为 1.0）
    rel_u = [1.0, 1.0]
    rel_g = [gv[0] / uv[0], gv[1] / uv[1]]
    x = range(len(metrics))
    b1 = ax.bar([i - w / 2 for i in x], rel_u, w, label="无 guardrail", color=GRAY)
    b2 = ax.bar([i + w / 2 for i in x], rel_g, w, label="有 guardrail", color=GREEN)
    for bars, vals in ((b1, uv), (b2, gv)):
        for r, v in zip(bars, vals):
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.03,
                    f"{v:.0f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylim(0, max(rel_g) * 1.35)
    ax.set_ylabel("相对无 guardrail 的倍数", fontsize=10)
    ax.set_title("代价：修复要重发上下文", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    fig.tight_layout()
    out = FIG / "guardrail_compare.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print("saved:", out)


if __name__ == "__main__":
    main()
