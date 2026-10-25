"""对 Layer-1 评测结果评分：对齐金标准，计算 DOI 幻觉检测、元数据错误检测、综合检出的指标。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def prf(tp: int, fp: int, fn: int, tn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if tp + fp + fn + tn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def score(bundle: dict, result: dict) -> dict:
    gold = {it["item_id"]: it for it in bundle["items"]}
    refs = ((result.get("json_result") or {}).get("references")) or []
    pred: dict[int, dict] = {}
    for r in refs:
        try:
            iid = int(r.get("item_id"))
        except (TypeError, ValueError):
            continue
        pred[iid] = r

    rows = []
    # 任务A：DOI 幻觉（正例 = gold doi_status == not_found）
    A = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    # 任务B：元数据错误（正例 = gold metadata_match == False）
    B = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    # 任务C：任意问题（正例 = gold label != valid）
    C = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for iid, g in sorted(gold.items()):
        p = pred.get(iid)
        # 预测值
        pred_doi = (p or {}).get("doi_status", "missing")
        pred_meta = (p or {}).get("metadata_match", None)
        verdict = (p or {}).get("verdict", "missing")

        # 任务 A
        gold_pos = g["doi_status"] == "not_found"
        pred_pos = str(pred_doi).lower() == "not_found"
        # 任务 B
        gold_b = g["metadata_match"] is False
        pred_b = pred_meta is False
        # 任务 C（任意异常，suspect 也算 flagged）
        gold_c = g["label"] != "valid"
        pred_c = pred_pos or pred_b or str(verdict).lower() in ("confirm", "suspect")

        for cm, gp, pp in ((A, gold_pos, pred_pos), (B, gold_b, pred_b), (C, gold_c, pred_c)):
            if gp and pp:
                cm["tp"] += 1
            elif (not gp) and pp:
                cm["fp"] += 1
            elif gp and (not pp):
                cm["fn"] += 1
            else:
                cm["tn"] += 1

        rows.append({
            "item_id": iid, "gold": g["label"],
            "pred_doi": pred_doi, "pred_meta": pred_meta, "verdict": verdict,
            "correct_A": gold_pos == pred_pos,
            "correct_B": g["metadata_match"] == pred_meta if pred_meta is not None else False,
            "issue": (p or {}).get("issue", ""),
        })

    return {
        "bundle": bundle.get("seed"),
        "n": len(gold),
        "n_pred": len(pred),
        "missing": sorted(set(gold) - set(pred)),
        "hallucinated_doi_detection": prf(**A),
        "metadata_error_detection": prf(**B),
        "any_issue_detection": prf(**C),
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--result", required=True)
    args = ap.parse_args()

    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    rep = score(bundle, result)

    print(f"bundle seed={rep['bundle']}  n={rep['n']}  预测条数={rep['n_pred']}  漏检编号={rep['missing']}")
    for task in ("hallucinated_doi_detection", "metadata_error_detection", "any_issue_detection"):
        m = rep[task]
        print(f"\n【{task}】 P={m['precision']} R={m['recall']} F1={m['f1']} "
              f"Spec={m['specificity']} Acc={m['accuracy']}  (tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']})")
    print("\n逐条明细：")
    for r in rep["rows"]:
        flag = "✓" if (r["correct_A"] and r["correct_B"]) else "✗"
        print(f"  {flag} [{r['item_id']:2d}] gold={r['gold']:9s} pred_doi={str(r['pred_doi']):10s} "
              f"pred_meta={str(r['pred_meta']):5s} verdict={r['verdict']}")


if __name__ == "__main__":
    main()
