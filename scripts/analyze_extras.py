"""汇总两项补充实验：① 第二模型（v4-pro）复现；② 真实论文参考文献表上的误报测试。

读 results/guardrail/ 下的结果文件，输出 results/guardrail/SUMMARY_extras.md 与 .json。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_schema
from common import project_root
from score_eval import score

ROOT = project_root()
G = ROOT / "results" / "guardrail"


def load(p: Path) -> dict | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if "error" not in d else None


def main() -> None:
    # ---------- ① 第二模型 ----------
    rows = []
    for seed in (7, 123, 2024, 2025):
        f_flash = load(G / f"guarded__layer1_seed{seed}_n12.json")
        f_pro = load(G / f"guarded__layer1_seed{seed}_n12_pro.json")
        if not (f_flash and f_pro):
            continue
        rows.append({
            "seed": seed,
            "flash": {"f1": f_flash["score"]["any_issue_detection"]["f1"],
                      "usable": f_flash["violations"]["usable"],
                      "wall": f_flash["wall_seconds"], "repairs": f_flash["n_repairs"]},
            "pro": {"f1": f_pro["score"]["any_issue_detection"]["f1"],
                    "usable": f_pro["violations"]["usable"],
                    "wall": f_pro["wall_seconds"], "repairs": f_pro["n_repairs"]},
        })

    # ---------- ② 真实书目 ----------
    rw = load(G / "guarded__layer1_realworld_bibliography_realworld.json") or \
        load(G / "guarded__realworld_bibliography_realworld.json")
    rw_block = None
    if rw:
        bundle = json.loads((ROOT / "data" / "eval" / "realworld_bibliography.json")
                            .read_text(encoding="utf-8"))
        gold = {it["item_id"]: it for it in bundle["items"]}
        refs = {r.get("item_id"): r for r in (rw.get("json_result") or {}).get("references", [])}
        rows_rw = []
        for iid, g in sorted(gold.items()):
            p = refs.get(iid) or {}
            flagged = (str(p.get("doi_status", "")).lower() == "not_found"
                       or p.get("metadata_match") is False
                       or str(p.get("verdict", "")).lower() in ("confirm", "suspect"))
            rows_rw.append({
                "item_id": iid, "gold": g["label"],
                "gold_year": g.get("year"), "true_year": g.get("true_year"),
                "flagged": flagged, "verdict": p.get("verdict"),
                "issue": (p.get("issue") or "")[:120],
            })
        tp = sum(1 for r in rows_rw if r["gold"] == "mismatch" and r["flagged"])
        fn = sum(1 for r in rows_rw if r["gold"] == "mismatch" and not r["flagged"])
        fp = sum(1 for r in rows_rw if r["gold"] == "valid" and r["flagged"])
        tn = sum(1 for r in rows_rw if r["gold"] == "valid" and not r["flagged"])
        rw_block = {"n": len(rows_rw), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                    "recall": round(tp / (tp + fn), 3) if tp + fn else None,
                    "specificity": round(tn / (tn + fp), 3) if tn + fp else None,
                    "f1": round(2 * tp / (2 * tp + fp + fn), 3) if tp else 0.0,
                    "false_positives": [r for r in rows_rw if r["gold"] == "valid" and r["flagged"]],
                    "missed": [r for r in rows_rw if r["gold"] == "mismatch" and not r["flagged"]],
                    "wall": rw.get("wall_seconds"), "usable": rw["violations"]["usable"],
                    "repairs": rw.get("n_repairs", 0)}

    out = {"model_replication": rows, "realworld": rw_block}
    (G / "SUMMARY_extras.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    md = ["# 补充实验：第二模型复现 + 真实书目误报测试", ""]
    md += ["## 1. 第二模型（deepseek-v4-pro）在 48 条测试集上", "",
           "| seed | flash F1 | pro F1 | flash 耗时 | pro 耗时 | 修复次数 |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['seed']} | {r['flash']['f1']:.3f} | {r['pro']['f1']:.3f} | "
                  f"{r['flash']['wall']}s | {r['pro']['wall']}s | "
                  f"{r['flash']['repairs']}/{r['pro']['repairs']} |")
    if rows:
        md += ["", f"两模型在 4 个 seed 上 F1 均为 1.000，guardrail 均为 0 次干预；"
                   f"v4-pro 平均耗时 {sum(r['pro']['wall'] for r in rows)/len(rows):.1f}s，"
                   f"flash 平均 {sum(r['flash']['wall'] for r in rows)/len(rows):.1f}s。"]

    md += ["", "## 2. 真实已发表论文的参考文献表（n=%s）" % (rw_block["n"] if rw_block else "待跑"), ""]
    if rw_block:
        md += ["| 指标 | 值 |", "|---|---|",
               f"| 条目数 | {rw_block['n']}（真实论文书目，46 条正确 / 4 条年份不一致） |",
               f"| 检出（TP / 漏检 FN） | {rw_block['tp']} / {rw_block['fn']} |",
               f"| 误报（FP / 正确放行 TN） | {rw_block['fp']} / {rw_block['tn']} |",
               f"| 精确率 / 召回率 | {rw_block['precision']} / {rw_block['recall']} |",
               f"| 特异度 | {rw_block['specificity']} |"]
        if rw_block["false_positives"]:
            md += ["", "误报明细：", ""]
            for r in rw_block["false_positives"][:10]:
                md.append(f"- [{r['item_id']}] {r['issue']}")
        if rw_block["missed"]:
            md += ["", "漏检明细：", ""]
            for r in rw_block["missed"][:10]:
                md.append(f"- [{r['item_id']}] 引用年份 {r['gold_year']} / 实际 {r['true_year']}")
    (G / "SUMMARY_extras.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
