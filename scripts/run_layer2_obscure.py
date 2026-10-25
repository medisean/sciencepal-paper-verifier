"""Layer-2 覆盖完整性对照（冷门撤稿 + 限定任务）。

真实场景：用户只要求"核对 DOI 是否有效、题录是否与官方记录一致"，并未要求查撤稿。
两条文献 DOI 都有效、题录都正确，但第 1 条是 2026 年一篇冷门、已撤稿的昆虫学论文
（Crossref 标题以 "- RETRACTED" 结尾，模型几乎不可能凭记忆知道），第 2 条为同期刊正常论文。

关键：两个 Agent 收到【完全相同的输入】，提示里不出现"撤稿"二字、不教任何撤稿方法。
差异只来自系统提示词内置工作流——verifier 的 C4 强制每条都查撤稿，naive 只做被要求的 DOI/题录核对。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config, load_env, project_root
from runner import run_job
from sp_client import SPClient

PROMPT = """请帮我核对下面这两条参考文献：确认每条的 DOI 是否真实有效（能否解析），以及题录信息（标题、作者、年份、期刊、卷、期、页码）是否与官方记录完全一致。请逐条联网查证，一次性完成，不要提问或等待确认。

[1] Idrees MA, Dong X, Zhang X, Qin D. Potential global distribution of Pochazia shantungensis (Chou & Lu, 1977), under current and future climatic scenarios based on an optimised MaxEnt model. Bulletin of Entomological Research. 2026;116(5):647-655. doi:10.1017/s0007485326101060

[2] Cárdenas AM, Gallardo P, Moyano L, Presa JJ. Autecology, feeding preferences and reproductive biology of Chorthippus (Glyptobothrus) vagans (Eversmann, 1848) (Orthoptera: Gomphocerinae) in Mediterranean ecosystems. Bulletin of Entomological Research. 2016;107(1):21-31. doi:10.1017/s0007485316000481

末尾输出 JSON：{"references":[{"item_id":1,"doi":"","doi_status":"valid|not_found","metadata_match":true,"verdict":"confirm|suspect|pass","issue":""}]}
"""


def main() -> None:
    load_env()
    key, base = get_config()
    agents = {"verifier": os.environ["VERIFIER_AGENT_ID"],
              "naive": os.environ["NAIVE_AGENT_ID"]}
    outdir = project_root() / "results" / "layer2" / "compare"
    outdir.mkdir(parents=True, exist_ok=True)
    with SPClient(key, base) as client:
        for who, aid in agents.items():
            print(f"\n===== {who} / obscure_retraction =====", flush=True)
            res = run_job(client, aid, PROMPT,
                          save_dir=project_root() / "output" / "runs")
            out = outdir / f"layer2c_obscure_retraction__{who}.json"
            out.write_text(json.dumps({
                "case": "obscure_retraction_limited_task", "agent": who,
                "run_id": res["run_id"], "status": res["status"],
                "n_tool_calls": len(res["tool_calls"]),
                "tool_names": [t.get("name") for t in res["tool_calls"]],
                "final_text": res["final_text"], "json_result": res["json_result"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  tools={len(res['tool_calls'])} 输出长度={len(res['final_text'] or '')}", flush=True)


if __name__ == "__main__":
    main()
