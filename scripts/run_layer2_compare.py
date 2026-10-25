"""Layer-2 朴素对照：verifier（内置核查工作流）vs naive（普通联网、无专家 SOP）。

关键设计：两个 Agent 收到【完全相同的朴素任务提示】，提示里不教撤稿判定方法、不教统计复算、
不列举 M1-M5 检查项，只像普通用户一样请它们"核查/审查"。差异只来自系统提示词内置的工作流。
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

# 朴素任务：不提示"撤稿"、不教 relation / RETRACTED
RETRACTION_PROMPT = """请核查以下参考文献，逐条联网查证，判断每条是否存在问题（DOI 是否真实、题录是否正确，以及其他任何问题）。可使用联网和代码工具。请一次性完成，不要提问或等待确认。

[1] Obokata H, Wakayama T, Sasai Y, et al. Stimulus-triggered fate conversion of somatic cells into pluripotency. Nature. 2014;505(7485):641-647. doi:10.1038/nature12968

[2] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444. doi:10.1038/nature14539

末尾输出 JSON：{"references":[{"item_id":1,"doi":"","doi_status":"valid|not_found|no_doi","metadata_match":true,"verdict":"confirm|suspect|pass","evidence_url":"","issue":""}]}
"""

# 朴素任务：不提 M1-M5、不要求复算、不提示 p 值有误
METHODOLOGY_PROMPT = """下面是一段论文稿件片段（虚构、用于教学测试）。请审查它在方法和统计上是否有问题，可使用联网和代码工具。请一次性完成，不要提问或等待确认。

--- 模拟稿件（虚构） ---
标题：Drug-X 对原发性高血压的降压疗效：单中心开放标签研究

方法：连续纳入某门诊 24 名高血压患者，按就诊顺序分为三组（每组 n=8）：安慰剂、低剂量 Drug-X、高剂量 Drug-X。疗程 4 周。测量指标包括收缩压（SBP）、舒张压、心率、肝肾功能、血脂、生活质量评分。研究未做样本量/功效分析，未设盲，未注册方案。

结果（4 周时 SBP 较基线下降值，mean±SD，mmHg）：
- 安慰剂组：5.2 ± 3.1
- 低剂量组：7.8 ± 3.5
- 高剂量组：7.5 ± 3.8

统计：作者对三组之间的主要终点"两两进行独立样本 t 检验"，未做多重比较校正。报告称："高剂量组 SBP 下降优于安慰剂组（t 检验，p=0.03），差异有统计学意义；低剂量组亦优于安慰剂组（p=0.04）。"

结论（原文）："Drug-X 导致血压显著下降，疗效确切，建议在临床高血压患者中全面推广。"

补充：研究共测量了 6 个疗效/安全指标，正文仅报告了上述达显著性的 SBP 结果，其余未显著指标（舒张压、心率、肝肾功能、血脂、生活质量）"数据未显示"，未提供数值。

末尾输出 JSON：{"methodology_findings":[{"id":"","category":"","severity":"high|medium|low","description":"","evidence":"","recommendation":""}]}
"""

CASES = [
    ("layer2a_retraction_naiveprompt", RETRACTION_PROMPT),
    ("layer2b_methodology_naiveprompt", METHODOLOGY_PROMPT),
]


def main() -> None:
    load_env()
    key, base = get_config()
    agents = {"verifier": os.environ["VERIFIER_AGENT_ID"],
              "naive": os.environ["NAIVE_AGENT_ID"]}
    outdir = project_root() / "results" / "layer2" / "compare"
    outdir.mkdir(parents=True, exist_ok=True)
    with SPClient(key, base) as client:
        for who, aid in agents.items():
            for name, prompt in CASES:
                print(f"\n===== {who} / {name} =====", flush=True)
                res = run_job(client, aid, prompt,
                              save_dir=project_root() / "output" / "runs")
                out = outdir / f"{name}__{who}.json"
                out.write_text(json.dumps({
                    "case": name, "agent": who, "run_id": res["run_id"],
                    "status": res["status"], "n_tool_calls": len(res["tool_calls"]),
                    "tool_names": [t.get("name") for t in res["tool_calls"]],
                    "final_text": res["final_text"], "json_result": res["json_result"],
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  tools={len(res['tool_calls'])} 输出长度={len(res['final_text'] or '')}", flush=True)


if __name__ == "__main__":
    main()
