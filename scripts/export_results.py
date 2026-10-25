"""把最终 test 集（seed 7/123/2024/2025，共48条）的指标与逐条对照导出为可入库的 results/。"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_eval import score, prf

ROOT = Path(__file__).resolve().parent.parent
SEEDS = [7, 123, 2024, 2025]
TASKS = ["hallucinated_doi_detection", "metadata_error_detection", "any_issue_detection"]
TASK_CN = {"hallucinated_doi_detection": "幻觉DOI检测",
           "metadata_error_detection": "元数据错误检测",
           "any_issue_detection": "任意问题检测"}


def main() -> None:
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    agg = {m: {k: {x: 0 for x in ("tp", "fp", "fn", "tn")} for k in TASKS}
           for m in ("verifier", "baseline")}
    per_item = []

    for s in SEEDS:
        bundle = json.loads((ROOT / f"data/eval/layer1_seed{s}_n12.json").read_text(encoding="utf-8"))
        gold = {it["item_id"]: it for it in bundle["items"]}
        preds = {}
        for m in ("verifier", "baseline"):
            res = json.loads((ROOT / f"output/eval/layer1_seed{s}_n12__{m}.json").read_text(encoding="utf-8"))
            rep = score(bundle, res)
            for k in TASKS:
                for x in ("tp", "fp", "fn", "tn"):
                    agg[m][k][x] += rep[k][x]
            refs = {int(r["item_id"]): r for r in (res.get("json_result") or {}).get("references", [])
                    if str(r.get("item_id", "")).isdigit()}
            preds[m] = refs

        for iid, g in sorted(gold.items()):
            row = {
                "seed": s, "item_id": iid, "gold_label": g["label"],
                "doi": g["doi"], "gold_doi_status": g["doi_status"],
                "gold_metadata_match": g["metadata_match"],
            }
            for m in ("verifier", "baseline"):
                p = preds[m].get(iid, {})
                row[f"{m}_doi_status"] = p.get("doi_status", "missing")
                row[f"{m}_metadata_match"] = p.get("metadata_match")
                row[f"{m}_verdict"] = p.get("verdict", "missing")
            per_item.append(row)

    metrics = {m: {k: prf(**agg[m][k]) for k in TASKS} for m in agg}
    (out / "metrics_summary.json").write_text(
        json.dumps({"n_total": len(per_item), "seeds": SEEDS, "metrics": metrics},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    with (out / "metrics_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["方法", "任务", "精确率P", "召回率R", "F1", "特异度Specificity",
                    "准确率Accuracy", "TP", "FP", "FN", "TN"])
        for m in ("baseline", "verifier"):
            for k in TASKS:
                d = metrics[m][k]
                w.writerow([m, TASK_CN[k], d["precision"], d["recall"], d["f1"],
                            d["specificity"], d["accuracy"], d["tp"], d["fp"], d["fn"], d["tn"]])

    with (out / "per_item_results.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        cols = ["seed", "item_id", "gold_label", "doi", "gold_doi_status", "gold_metadata_match",
                "verifier_doi_status", "verifier_metadata_match", "verifier_verdict",
                "baseline_doi_status", "baseline_metadata_match", "baseline_verdict"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(per_item)

    print(f"n={len(per_item)} 已导出 results/metrics_summary.json / .csv / per_item_results.csv")
    print("\n=== 指标汇总 ===")
    print(f"{'任务':<16}{'方法':<10}{'P':>7}{'R':>7}{'F1':>7}{'Spec':>7}")
    for k in TASKS:
        for m in ("baseline", "verifier"):
            d = metrics[m][k]
            print(f"{TASK_CN[k]:<16}{m:<10}{d['precision']:>7.3f}{d['recall']:>7.3f}"
                  f"{d['f1']:>7.3f}{d['specificity']:>7.3f}")


if __name__ == "__main__":
    main()
