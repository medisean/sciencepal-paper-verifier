"""第三组对照（naive 普通联网 Agent）跑批：对同一批测试集跑工具全开但无核查工作流的 Agent。

预期：审计显示它确实联网（network_access=True），但因缺少强制逐字段/撤稿/复算的工作流，
在元数据错配、撤稿等任务上仍会出错——用于把增益归因于"核查工作流"而非"平台联网"。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_config, load_env, project_root
from run_batch import ensure_bundle, run_one, merge
from score_eval import score
from sp_client import SPClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[7, 123, 2024, 2025])
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    load_env()
    api_key, base = get_config()
    naive_id = os.environ["NAIVE_AGENT_ID"]

    if args.fresh:
        for s in args.seeds:
            f = project_root() / "output" / "eval" / f"layer1_seed{s}_n{args.n}__naive.json"
            if f.exists():
                f.unlink()
        print("已清空 naive 旧结果", flush=True)

    bundles = [ensure_bundle(args.n, s, False) for s in args.seeds]
    reps, audits = [], []
    with SPClient(api_key, base) as client:
        for bp in bundles:
            print(f"\n===== {bp.name} (naive) =====", flush=True)
            b = json.loads(bp.read_text(encoding="utf-8"))
            rn = run_one(client, naive_id, bp, "naive", offline=False)
            reps.append(score(b, rn))
            audits.append(rn.get("audit"))
            print(f"    naive 审计={rn.get('audit')}", flush=True)
            if not rn.get("audit", {}).get("network_access"):
                print("    [注意] 该 run 未检测到联网取证，可能退化为凭记忆作答", flush=True)

    summary = {"naive": merge(reps), "audit": audits,
               "n_total": sum(rep["n"] for rep in reps)}
    out = project_root() / "output" / "eval" / f"summary_naive_seeds{'-'.join(map(str,args.seeds))}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n================ naive 汇总（n=%d）================" % summary["n_total"])
    for task, m in summary["naive"].items():
        print(f"  {task:30s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
              f"Spec={m['specificity']:.3f} Acc={m['accuracy']:.3f} (tp{m['tp']} fp{m['fp']} fn{m['fn']} tn{m['tn']})")
    print("\n已保存:", out)


if __name__ == "__main__":
    main()
