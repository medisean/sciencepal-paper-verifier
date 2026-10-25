"""重放 output/runs 下的 SSE 原始事件，对每个评测 run 生成网络访问审计。
目的：
- 证明 baseline（纯模型）在整个 run 中未获得任何外部数据（命令被平台拒绝 / 未尝试）；
- 证明 verifier（核查 Agent）实际联网核查。
输出 results/audit_report.json 与 results/audit_report.md（可入库，output/ 本身被 gitignore）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import parse_events
from run_batch import audit_run, _tool_body

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "output" / "runs"
EVAL = ROOT / "output" / "eval"
RESULTS = ROOT / "results"
TEST_SEEDS = [7, 123, 2024, 2025]

# 成功联网的强证据：HTTP 状态 + 学术元数据字段（脚本已把 Crossref 响应解析为 TITLE/AUTHORS 等）
META_RE = re.compile(r"\bTITLE\s*:|\bAUTHORS\s*:|\bJOURNAL\s*:|\btitle\s*:|\bcontainer\s*:", re.I)

BLOCKED_RE = re.compile(
    r"tool_unavailable|\"runtime\"\s*:\s*\"blocked\"|reason_code\"?\s*:\s*\"permission\"|Enable these tools",
    re.I,
)
# 真实外部数据返回的特征（Crossref HTTP 状态/元数据/落盘结果）
NETDATA_RE = re.compile(
    r"api\.crossref|crossref\.org|semantic[-\s]?scholar|api\.openalex",
    re.I,
)
HTTP_OK_RE = re.compile(r"HTTP\s*200|HTTP\s*404|\"status\"\s*:\s*\"ok\"|'status'\s*:\s*'ok'", re.I)


def audit_sse(run_id: str) -> dict:
    files = list(RUNS.glob(run_id[:8] + "*.jsonl"))
    if not files:
        return {"run_id": run_id, "missing_jsonl": True}
    fp = files[0]
    events = [json.loads(line) for line in fp.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    parsed = parse_events(events)
    # 统一复用 run_batch.audit_run 的联网识别（含 302、异步批量、Crossref 字段）
    verdict = audit_run(parsed)
    tools = []
    for t in parsed.get("tool_calls", []):
        body = _tool_body(t)
        blocked = bool(BLOCKED_RE.search(body))
        tools.append({"name": t.get("name", "?"), "blocked": blocked,
                      "external_data_returned": False,
                      "excerpt": body[:180].replace("\n", " ")})
    return {
        "run_id": run_id,
        "jsonl": fp.name,
        "tool_calls": verdict["tool_attempts"],
        "external_data_returned": verdict["network_access"],
        "blocked_attempts": verdict["blocked_attempts"],
        "tools": tools,
    }


def main() -> None:
    records = []
    for tag in ("baseline", "naive", "verifier"):
        for s in TEST_SEEDS:
            f = EVAL / f"layer1_seed{s}_n12__{tag}.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            a = audit_sse(r["run_id"])
            records.append({
                "seed": r["bundle"], "tag": tag, "run_id": r["run_id"],
                "thread_id": r.get("thread_id"), "status": r.get("status"),
                "expected": "offline" if tag == "baseline" else "online",
                "tool_calls": a["tool_calls"],
                "external_data_returned": a["external_data_returned"],
                "blocked_attempts": a["blocked_attempts"],
                "tools": a.get("tools", []),
            })

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "audit_report.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 离线/联网审计报告（SSE 原始事件重放）", "",
             "对每个评测 run 重放 `output/runs/{run_id}.jsonl` 原始工具事件，判定其是否实际获得外部数据。",
             "三方对照：`baseline`（关闭 execute_command/web_search，应全程离线）、`naive`（普通联网 Agent，工具全开，应联网）、`verifier`（专家核查工作流，应联网）。",
             ""]
    lines.append("| seed | agent | 期望 | 工具调用 | 工具被拒次数 | 实际获得外部数据 | run_id |")
    lines.append("|---|---|---|---|---|---|---|")
    for rec in records:
        lines.append(
            f"| {rec['seed']} | {rec['tag']} | {rec['expected']} | {rec['tool_calls']} | "
            f"{rec['blocked_attempts']} | {'是' if rec['external_data_returned'] else '否'} | {rec['run_id'][:8]} |")
    lines += ["", "## 基线（baseline）被拒证据摘录", ""]
    for rec in records:
        if rec["tag"] != "baseline":
            continue
        blocked = [t for t in rec["tools"] if t["blocked"]]
        lines.append(f"### seed {rec['seed']}（工具调用 {rec['tool_calls']} 次，"
                     f"获得外部数据={'是' if rec['external_data_returned'] else '否'}）")
        if not rec["tools"]:
            lines.append("- 模型未发起任何工具调用，直接以自身知识作答（纯离线）。")
        for t in blocked:
            lines.append(f"- 工具 `{t['name']}` 被拒：`{t['excerpt'][:150]}`")
        if not blocked and rec["tools"]:
            for t in rec["tools"]:
                lines.append(f"- 工具 `{t['name']}`：`{t['excerpt'][:150]}`")
        lines.append("")
    (RESULTS / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("审计结论：")
    for rec in records:
        ok = (rec["external_data_returned"] == (rec["expected"] == "online"))
        print(f"  seed{rec['seed']} {rec['tag']:9s} 期望{rec['expected']:6s} "
              f"工具{rec['tool_calls']:2d} 被拒{rec['blocked_attempts']} "
              f"外部数据={'是' if rec['external_data_returned'] else '否'} {'✓' if ok else '✗ 需检查'}")
    print("\n已写出 results/audit_report.json / audit_report.md")


if __name__ == "__main__":
    main()
