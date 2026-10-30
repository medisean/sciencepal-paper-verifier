"""命令行入口：带 guardrail 的参考文献核查，或离线回放已保存的 run。

两种用法：

1) 真跑（需要 SCIENCEPAL_API_KEY 与当日配额）
   python3 scripts/verify_refs.py --input refs.txt --out report.json
   python3 scripts/verify_refs.py --input refs.txt --trace-check   # 额外校验"结论必须有取证痕迹"

2) 离线回放（不联网、不耗配额，用于复核证据）
   python3 scripts/verify_refs.py --replay output/runs/<run_id>.jsonl
   回放会重新跑一遍交付契约校验，打印同一份判定表，因此评委可以拿任意一条
   已保存的 SSE 轨迹，验证"这条结论在当时是否合规"。

输入格式：每行一条参考文献；空行与 # 开头的行忽略。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_schema
from common import get_config, load_env
from guardrail import GuardedRunner
from runner import parse_events

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\]\)\"'，。]+")


def read_refs(path: Path) -> list[str]:
    refs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            refs.append(line)
    return refs


def build_prompt(refs: list[str]) -> str:
    return (
        "下面是某论文稿件的参考文献列表。请逐条核查：① 每条的 DOI 是否真实存在"
        "（必须在沙箱中实际联网调用 Crossref，记录 HTTP 状态）；② 题录信息（作者、年份、标题、期刊、卷期页）"
        "是否与该 DOI 的真实元数据逐字段一致（任一字段不一致即 metadata_match=false）。\n\n"
        + "\n".join(f"[{i}] {r}" for i, r in enumerate(refs, 1))
        + "\n\n只输出一个 ```json 代码块，字段固定为 references[].{item_id, doi_status, metadata_match, "
          "verdict, confidence, evidence_url, issue}。正常用 pass，DOI 不存在或题录有误用 confirm，不确定用 suspect。"
    )


def render(payload: dict | None, errors: list[str]) -> str:
    lines = []
    refs = (payload or {}).get("references") or []
    if refs:
        lines.append(f"{'#':>3}  {'doi_status':<12}{'match':<8}{'verdict':<10}{'evidence':<10}issue")
        for r in refs:
            ev = "有" if str(r.get("evidence_url") or "").strip() else "缺"
            lines.append(
                f"{str(r.get('item_id')):>3}  {str(r.get('doi_status')):<12}"
                f"{str(r.get('metadata_match')):<8}{str(r.get('verdict')):<10}{ev:<10}"
                f"{str(r.get('issue') or '')[:40]}")
    lines.append("")
    if errors:
        lines.append(f"交付契约：不合规（{len(errors)} 项）")
        for e in errors[:10]:
            lines.append("  - " + e)
    else:
        lines.append("交付契约：合规（结构 / 覆盖 / 证据 / 自洽 全部通过）")
    return "\n".join(lines)


def replay(path: Path) -> int:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict) \
                and "type" in obj["data"]:
            events.append({"event": obj.get("event"), "data": obj["data"]})
        else:
            events.append({"event": None, "data": obj})
    parsed = parse_events(events)
    payload = parsed.get("json_result")
    errors = report_schema.validate(payload) if payload is not None else ["S: 未找到可解析的 JSON 代码块"]
    print(f"回放文件：{path}")
    print(f"事件数：{len(events)}  工具调用：{len(parsed.get('tool_calls', []))}  报告JSON：{'有' if payload else '无'}")
    print(render(payload, errors))
    return 0 if not errors else 1


def live(args) -> int:
    refs = read_refs(Path(args.input))
    if not refs:
        print("输入为空", file=sys.stderr)
        return 2
    load_env()
    key, base = get_config()
    dois = [m.group(0).rstrip(".") for r in refs for m in DOI_RE.finditer(r)]
    g = GuardedRunner(key, base, args.agent_id, expect_items=len(refs),
                      max_repairs=args.max_repairs, expect_dois=dois,
                      trace_check=args.trace_check, save_dir=Path(args.runs_dir))
    try:
        out = g.run(build_prompt(refs))
    finally:
        g.close()
    print(render(out.json_result, out.errors))
    print(f"\n轮次 {len(out.rounds)}｜拦截 {out.n_stops}｜修复 {out.n_repairs}｜"
          f"耗时 {out.wall_seconds}s｜tokens {out.usage.get('total_tokens')}")
    if out.interventions:
        print("干预记录：")
        for iv in out.interventions:
            print(f"  - {iv['kind']}: {str(iv['detail'])[:100]}")
    if args.out:
        Path(args.out).write_text(json.dumps({
            "run": out.as_dict(), "contract_errors": out.errors,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写出：", args.out)
    return 0 if not out.errors else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="参考文献文本文件（每行一条）")
    ap.add_argument("--replay", help="回放已保存的 SSE jsonl（离线，不耗配额）")
    ap.add_argument("--out", default=None)
    ap.add_argument("--run-id", dest="agent_id", default=None, help="Agent ID（默认取 .env 的 VERIFIER_AGENT_ID）")
    ap.add_argument("--max-repairs", type=int, default=2)
    ap.add_argument("--trace-check", action="store_true")
    ap.add_argument("--runs-dir", default="output/runs")
    args = ap.parse_args()
    if args.agent_id is None:
        import os
        load_env()
        args.agent_id = os.environ.get("VERIFIER_AGENT_ID")
    if args.replay:
        return replay(Path(args.replay))
    if args.input:
        return live(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
