"""汇总三组 Agent 在 Layer-1（48 条）与 Layer-2（3 个案例）上的过程可靠性指标。

指标：
- 工具调用总数 / 取证工具数 / 非预期工具数（save_memory、ask、浏览器接管、skill 搜索等）
- 最终 JSON 是否出现在最后一条完整助手消息（输出位置稳定性）
- 最终 JSON 是否可解析、schema 是否完整
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "output" / "runs"
EVAL = ROOT / "eval" if False else ROOT / "output" / "eval"

FORENSIC = {"execute_command", "watch_task", "check_command_output"}
UNEXPECTED = {"save_memory", "ask", "web_browser_takeover", "search_skills",
              "load_skill", "record_skill_outcome", "web_search"}

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def load_run(run_id: str):
    p = RUNS / f"{run_id}.jsonl"
    if not p.exists():
        return None
    return [json.loads(l) for l in p.read_text().splitlines()]


def analyze(events):
    from collections import Counter
    names = Counter()
    final_texts = []
    last_msg = None
    for e in events:
        d = e.get("data", {})
        if not isinstance(d, dict):
            continue
        t = d.get("type")
        c = d.get("content")
        if isinstance(c, str):
            try:
                c = json.loads(c)
            except Exception:
                c = {}
        if not isinstance(c, dict):
            continue
        if t == "tool":
            names[c.get("name")] += 1
        elif t == "assistant_response_end":
            choice = (c.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            if isinstance(msg.get("content"), str) and msg["content"].strip():
                last_msg = msg["content"]
                final_texts.append(msg["content"])
    total = sum(names.values())
    forensic = sum(v for k, v in names.items() if k in FORENSIC)
    unexpected = {k: v for k, v in names.items() if k in UNEXPECTED}
    # JSON 位置：最后一条消息是否含 JSON 代码块
    json_in_last = bool(last_msg and JSON_BLOCK_RE.search(last_msg))
    json_anywhere = any(JSON_BLOCK_RE.search(x) for x in final_texts)
    return {
        "total_tool_calls": total,
        "forensic_tool_calls": forensic,
        "unexpected_tool_calls": unexpected,
        "unexpected_count": sum(unexpected.values()),
        "json_in_last_message": json_in_last,
        "json_only_in_earlier_message": (not json_in_last) and json_anywhere,
    }


def run_row(eval_file: Path):
    d = json.loads(eval_file.read_text())
    rid = d.get("run_id")
    events = load_run(rid)
    a = analyze(events) if events else {}
    a["run_id"] = rid
    a["has_json_result"] = d.get("json_result") is not None
    return a


def main():
    groups = {"verifier": [], "naive": [], "baseline": []}
    for seed in [7, 123, 2024, 2025]:
        for tag in groups:
            f = EVAL / f"layer1_seed{seed}_n12__{tag}.json"
            if f.exists():
                groups[tag].append(("layer1_seed%d" % seed, run_row(f)))
    # Layer-2 三案例
    l2 = ROOT / "results" / "layer2" / "compare"
    for f in sorted(l2.glob("*.json")):
        if f.name.startswith("._"):
            continue
        d = json.loads(f.read_bytes().decode("utf-8", errors="replace"))
        who = d.get("agent")
        events = load_run(d.get("run_id"))
        a = analyze(events) if events else {}
        a["run_id"] = d.get("run_id")
        a["has_json_result"] = d.get("json_result") is not None
        if who in groups:
            groups[who].append((d.get("case"), a))

    summary = {}
    for who, rows in groups.items():
        print("=" * 70)
        print(who.upper(), f"({len(rows)} runs)")
        tot = [r["total_tool_calls"] for _, r in rows]
        unexp = sum(r["unexpected_count"] for _, r in rows)
        early = sum(1 for _, r in rows if r.get("json_only_in_earlier_message"))
        json_ok = sum(1 for _, r in rows if r.get("has_json_result"))
        for name, r in rows:
            print(f"  {name:42s} tools={r['total_tool_calls']:>3} "
                  f"非预期={r['unexpected_count']} {r['unexpected_tool_calls'] or ''}"
                  f"{' JSON在中间轮!' if r.get('json_only_in_earlier_message') else ''}")
        vals = tot or [0]
        summary[who] = {
            "n_runs": len(rows),
            "tool_calls_mean": round(sum(vals) / len(vals), 2),
            "tool_calls_min": min(vals), "tool_calls_max": max(vals),
            "unexpected_tool_calls_total": unexp,
            "runs_with_json_not_in_last_message": early,
            "runs_with_parsable_json": json_ok,
        }
        print(f"  -> 工具均值 {summary[who]['tool_calls_mean']} "
              f"[{summary[who]['tool_calls_min']}-{summary[who]['tool_calls_max']}]，"
              f"非预期调用合计 {unexp}，JSON 不在末轮 {early} 次，可解析 {json_ok}/{len(rows)}")
    out = ROOT / "results" / "process_reliability.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n已保存:", out)


if __name__ == "__main__":
    main()
