"""批量评测（带离线审计）：对每个 seed 跑 verifier（联网）与 baseline（强制离线）。
baseline 审计：解析 SSE 工具事件，若拿到任何真实外部数据（Crossref HTTP 200/404）判定为
polluted 并自动重跑；工具被平台拒绝（blocked/tool_unavailable/permission）视为干净。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_benchmark
from common import get_config, load_env, project_root
from runner import run_job
from score_eval import score, prf
from sp_client import SPClient


def _tool_body(t: dict) -> str:
    """工具 content 可能再包一层 {"output": ...}，统一取出实际文本。"""
    inner = t.get("content", "")
    if isinstance(inner, str):
        try:
            nested = json.loads(inner)
            if isinstance(nested, dict) and "output" in nested:
                return str(nested["output"])
        except json.JSONDecodeError:
            pass
    return str(inner)


def audit_run(result: dict) -> dict:
    """根据工具事件判定该 run 是否实际访问了外部数据。

    关键：execute_command 实际返回 HTTP 200/404 即视为联网成功；
    工具被平台拒绝（blocked/tool_unavailable/permission）绝不会出现 HTTP 状态。"""
    net_hits, blocked = 0, 0
    for t in result.get("tool_calls", []):
        body = _tool_body(t)
        low = body.lower()
        if "http 200" in low or "http 404" in low or '"status":"ok"' in low.replace(" ", ""):
            net_hits += 1
        if "tool_unavailable" in low or '"runtime": "blocked"' in low or '"runtime":"blocked"' in low \
                or '"reason_code": "permission"' in low or '"reason_code":"permission"' in low:
            blocked += 1
    return {"network_access": net_hits > 0, "network_hits": net_hits,
            "blocked_attempts": blocked, "tool_attempts": len(result.get("tool_calls", []))}


def ensure_bundle(n: int, seed: int, regenerate: bool) -> Path:
    p = project_root() / "data" / "eval" / f"layer1_seed{seed}_n{n}.json"
    if regenerate or not p.exists():
        bundle = build_benchmark.build(n, seed)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run_one(client, agent_id, bundle_path: Path, tag, offline: bool, max_retries: int = 3):
    out_path = project_root() / "output" / "eval" / f"{bundle_path.stem}__{tag}.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    for attempt in range(1, max_retries + 1):
        if out_path.exists():
            cached = json.loads(out_path.read_text(encoding="utf-8"))
            if (not offline) or cached.get("audit", {}).get("network_access") is False:
                return cached
            print(f"    [重跑] 缓存的 {tag} 检测到联网，删除重跑", flush=True)
            out_path.unlink()

        result = run_job(
            client, agent_id=agent_id, prompt=bundle["prompt"],
            save_dir=project_root() / "output" / "runs",
            web_search_on=False if offline else None,
        )
        audit = audit_run(result)
        out = {
            "bundle": bundle["seed"], "tag": tag, "run_id": result["run_id"],
            "thread_id": result["thread_id"], "status": result["status"],
            "usage": result["usage"], "n_tool_calls": len(result["tool_calls"]),
            "audit": audit, "final_text": result["final_text"],
            "json_result": result["json_result"],
        }
        if offline and audit["network_access"]:
            print(f"    [污染] {tag} 第{attempt}次仍联网(hits={audit['network_hits']})，重试…", flush=True)
            time.sleep(2)
            continue
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
    # 多次仍污染，保存但标记（供人工判断）
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    [警告] {tag} {max_retries} 次后仍联网，请人工检查", flush=True)
    return out


def merge(results: list[dict]) -> dict:
    totals = {k: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
              for k in ("hallucinated_doi_detection", "metadata_error_detection", "any_issue_detection")}
    for rep in results:
        for k in totals:
            for x in ("tp", "fp", "fn", "tn"):
                totals[k][x] += rep[k][x]
    return {k: prf(**v) for k, v in totals.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[7, 123, 2024, 2025])
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="删除所有 test 结果后完整重跑")
    args = ap.parse_args()

    if args.fresh:
        for s in args.seeds:
            for tag in ("verifier", "baseline"):
                f = project_root() / "output" / "eval" / f"layer1_seed{s}_n{args.n}__{tag}.json"
                if f.exists():
                    f.unlink()
        print("已清空旧 test 结果，完整重跑", flush=True)

    load_env()
    api_key, base = get_config()
    verifier_id = os.environ["VERIFIER_AGENT_ID"]
    baseline_id = os.environ["GENERAL_AGENT_ID"]

    bundles = [ensure_bundle(args.n, s, args.regenerate) for s in args.seeds]
    v_reps, b_reps, audits = [], [], {"verifier": [], "baseline": []}
    with SPClient(api_key, base) as client:
        for bp in bundles:
            print(f"\n===== {bp.name} =====", flush=True)
            b = json.loads(bp.read_text(encoding="utf-8"))
            rv = run_one(client, verifier_id, bp, "verifier", offline=False)
            rb = run_one(client, baseline_id, bp, "baseline", offline=True)
            v_reps.append(score(b, rv))
            b_reps.append(score(b, rb))
            audits["verifier"].append(rv.get("audit"))
            audits["baseline"].append(rb.get("audit"))
            print(f"    verifier 审计={rv.get('audit')}", flush=True)
            print(f"    baseline 审计={rb.get('audit')}", flush=True)

    summary = {"verifier": merge(v_reps), "baseline": merge(b_reps),
               "audit": audits, "n_total": sum(rep["n"] for rep in v_reps)}
    out = project_root() / "output" / "eval" / f"summary_seeds{'-'.join(map(str,args.seeds))}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n================ 汇总（n=%d）================" % summary["n_total"])
    for method in ("baseline", "verifier"):
        print(f"\n## {method}  审计: {audits[method]}")
        for task, m in summary[method].items():
            print(f"  {task:30s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
                  f"Spec={m['specificity']:.3f} Acc={m['accuracy']:.3f} (tp{m['tp']} fp{m['fp']} fn{m['fn']} tn{m['tn']})")
    print("\n已保存:", out)


if __name__ == "__main__":
    main()
