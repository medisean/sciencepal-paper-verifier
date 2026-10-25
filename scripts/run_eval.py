"""对单个评测 bundle 跑一个 Agent，保存原始结果（评分由 score_eval.py 完成）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_config, load_env, project_root
from runner import run_job
from sp_client import SPClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="benchmark json 路径")
    ap.add_argument("--agent-env", default="VERIFIER_AGENT_ID", help="读哪个环境变量作为 agent_id")
    ap.add_argument("--model", default="", help="可选模型 id，如 platform::deepseek-v4-pro")
    ap.add_argument("--tag", default="verifier", help="结果标签，如 verifier / baseline")
    ap.add_argument("--offline", action="store_true", help="发起时 web_search_on=False，用于纯模型基线")
    args = ap.parse_args()

    load_env()
    agent_id = os.environ.get(args.agent_env, "").strip()
    assert agent_id, f"环境变量 {args.agent_env} 为空"

    bundle_path = Path(args.bundle)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    print(f"bundle: {bundle_path.name}  n={bundle['n']}  tag={args.tag}  agent={agent_id[:8]}  offline={args.offline}")

    api_key, base = get_config()
    save_dir = project_root() / "output" / "runs"
    with SPClient(api_key, base) as client:
        result = run_job(
            client,
            agent_id=agent_id,
            prompt=bundle["prompt"],
            model_name=args.model or None,
            save_dir=save_dir,
            web_search_on=False if args.offline else None,
        )

    out = {
        "bundle": bundle_path.name,
        "tag": args.tag,
        "agent_id": agent_id,
        "model": args.model or "auto",
        "thread_id": result["thread_id"],
        "run_id": result["run_id"],
        "status": result["status"],
        "error": result["error"],
        "usage": result["usage"],
        "n_tool_calls": len(result["tool_calls"]),
        "tool_names": [t.get("name") for t in result["tool_calls"]],
        "final_text": result["final_text"],
        "json_result": result["json_result"],
    }
    out_path = project_root() / "output" / "eval" / f"{bundle_path.stem}__{args.tag}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("status:", result["status"], "| 工具调用:", out["tool_names"])
    jr = result["json_result"]
    if jr and isinstance(jr.get("references"), list):
        print("解析出 references 条数:", len(jr["references"]))
    else:
        print("⚠ 未解析到 JSON references")
    print("已保存:", out_path)


if __name__ == "__main__":
    main()
