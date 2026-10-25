"""只回归 verifier（用于提示词改动后确认 Layer-1 仍 F1=1.0），不重跑 baseline。"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config, load_env, project_root
from run_batch import run_one, ensure_bundle
from score_eval import score
from sp_client import SPClient

SEEDS = [7, 123, 2024, 2025]
N = 12


def main() -> None:
    load_env()
    key, base = get_config()
    vid = os.environ["VERIFIER_AGENT_ID"]
    reps, audits = [], []
    with SPClient(key, base) as client:
        for s in SEEDS:
            bp = ensure_bundle(N, s, False)
            b = json.loads(bp.read_text(encoding="utf-8"))
            rv = run_one(client, vid, bp, "verifier", offline=False)
            reps.append(score(b, rv)); audits.append(rv.get("audit"))
            print(f"seed{s} 审计={rv.get('audit')}", flush=True)
    from run_batch import merge
    m = merge(reps)
    print("\n===== verifier C4 回归（n=%d）=====" % sum(r["n"] for r in reps))
    for task, mm in m.items():
        print(f"  {task:30s} P={mm['precision']:.3f} R={mm['recall']:.3f} F1={mm['f1']:.3f} "
              f"(tp{mm['tp']} fp{mm['fp']} fn{mm['fn']} tn{mm['tn']})")
    out = project_root() / "output" / "eval" / "regress_verifier_c4.json"
    out.write_text(json.dumps({"verifier": m, "audit": audits}, ensure_ascii=False, indent=2))
    print("已保存:", out)


if __name__ == "__main__":
    main()
