"""Layer-2 定性案例 A：撤稿论文识别。
构造一个"被当作正常引用、但实际已撤稿"的文献（STAP 细胞，Crossref 标题含 RETRACTED ARTICLE），
加一篇正常对照，让核查 Agent 联网判定是否撤稿。结果保存到 results/layer2/。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config, load_env, project_root
from runner import run_job
from sp_client import SPClient

PROMPT = """请逐条核查下列参考文献，除了 DOI 有效性与题录一致性外，**额外检查每篇文献是否已被撤稿（retracted）**。
撤稿判定依据（必须联网查证，不得凭记忆）：
- Crossref 返回的标题以 "RETRACTED ARTICLE:" 或 "RETRACTED:" 开头；
- 或 relation 字段存在指向撤稿通知（retraction notice）的更新关系；
- 或期刊/出版社页面明确标注 Retraction/Withdrawn。
对撤稿文献给出 verdict=confirm 并说明撤稿状态与证据 URL；正常文献 verdict=ok。
末尾输出 JSON：{"references":[{"item_id","doi","doi_status","metadata_match","retracted":true/false,"verdict","evidence_url","issue"}]}

[1] Obokata H, Wakayama T, Sasai Y, et al. Stimulus-triggered fate conversion of somatic cells into pluripotency. Nature. 2014;505(7485):641-647. doi:10.1038/nature12968

[2] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444. doi:10.1038/nature14539
"""


def main() -> None:
    load_env()
    key, base = get_config()
    agent_id = os.environ["VERIFIER_AGENT_ID"]
    outdir = project_root() / "results" / "layer2"
    outdir.mkdir(parents=True, exist_ok=True)
    with SPClient(key, base) as client:
        res = run_job(client, agent_id, PROMPT, save_dir=project_root() / "output" / "runs")
    (outdir / "layer2a_retraction.json").write_text(
        json.dumps({"case": "retraction_detection", "run_id": res["run_id"],
                    "status": res["status"], "n_tool_calls": len(res["tool_calls"]),
                    "final_text": res["final_text"], "json_result": res["json_result"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("status:", res["status"], "| tools:", len(res["tool_calls"]))
    print("="*70)
    print(res["final_text"][:3000])


if __name__ == "__main__":
    main()
