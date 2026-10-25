"""Layer-2 定性案例 B：方法学/统计审查（可复算的合成测试稿件）。
稿件为明确标注的虚构教学片段，植入若干典型方法学问题（多重比较未校正、样本量不足、
统计复算错误、因果语言过强、选择性报告）。Agent 需在沙箱实际复算并逐条定位。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config, load_env, project_root
from runner import run_job
from sp_client import SPClient

PROMPT = """以下是一段【虚构的、用于测试论文核查能力的模拟稿件（synthetic test manuscript）】，
单位、药品与数据均为虚构，不涉及任何真实研究。请对其做方法学/统计审查（M1 研究设计、
M2 样本量与功效、M3 统计方法、M4 数据-结论复算、M5 选择性报告/因果表述）。
要求：对所有统计结论在沙箱中用 Python 实际复算（可 pip install scipy），指出问题、严重程度
（high/medium/low）、对应证据，并给出修改建议。末尾输出 JSON：
{"methodology_findings":[{"id","category","severity","description","evidence","recommendation"}]}

--- 模拟稿件（虚构） ---
标题：Drug-X 对原发性高血压的降压疗效：单中心开放标签研究

方法：连续纳入某门诊 24 名高血压患者，按就诊顺序分为三组（每组 n=8）：安慰剂、低剂量 Drug-X、
高剂量 Drug-X。疗程 4 周。测量指标包括收缩压（SBP）、舒张压、心率、肝肾功能、血脂、生活质量评分。
研究未做样本量/功效分析，未设盲，未注册方案。

结果（4 周时 SBP 较基线下降值，mean±SD，mmHg）：
- 安慰剂组：5.2 ± 3.1
- 低剂量组：7.8 ± 3.5
- 高剂量组：7.5 ± 3.8

统计：作者对三组之间的主要终点"两两进行独立样本 t 检验"，未做多重比较校正。
报告称："高剂量组 SBP 下降优于安慰剂组（t 检验，p=0.03），差异有统计学意义；
低剂量组亦优于安慰剂组（p=0.04）。"

结论（原文）："Drug-X 导致血压显著下降，疗效确切，建议在临床高血压患者中全面推广。"

补充：研究共测量了 6 个疗效/安全指标，正文仅报告了上述达显著性的 SBP 结果，其余未显著指标
（舒张压、心率、肝肾功能、血脂、生活质量）"数据未显示"，未提供数值。
"""


def main() -> None:
    load_env()
    key, base = get_config()
    agent_id = os.environ["VERIFIER_AGENT_ID"]
    outdir = project_root() / "results" / "layer2"
    outdir.mkdir(parents=True, exist_ok=True)
    with SPClient(key, base) as client:
        res = run_job(client, agent_id, PROMPT, save_dir=project_root() / "output" / "runs")
    (outdir / "layer2b_methodology.json").write_text(
        json.dumps({"case": "methodology_review_synthetic", "run_id": res["run_id"],
                    "status": res["status"], "n_tool_calls": len(res["tool_calls"]),
                    "final_text": res["final_text"], "json_result": res["json_result"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("status:", res["status"], "| tools:", len(res["tool_calls"]))
    print("=" * 70)
    print(res["final_text"][:4000])


if __name__ == "__main__":
    main()
