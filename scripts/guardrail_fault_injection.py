"""故障注入：验证契约校验器本身的检测能力（与模型行为无关，纯代码）。

做法：取干净跑批里真实产出的合规 JSON，按 6 类真实失败模式各做一处定向破坏，
检查 report_schema.validate 是否必然报错；同时用原始未破坏的输出检查误报率。

这回答的是"检测器有没有用"，与"模型多久失守一次"是两个独立问题，分开报告。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_schema
from common import project_root

ROOT = project_root()
OUT = ROOT / "results" / "guardrail"
SOURCES = ["output/eval/layer1_seed7_n12__verifier.json",
           "output/eval/layer1_seed123_n12__verifier.json",
           "results/guardrail/guarded__layer1_seed7_n12.json"]


def _load() -> list[tuple[str, dict]]:
    out = []
    for rel in SOURCES:
        p = ROOT / rel
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        jr = d.get("json_result")
        if isinstance(jr, dict):
            out.append((rel, jr))
    return out


def mutations(base: dict) -> list[tuple[str, object, str]]:
    """返回 [(失败模式, 破坏后的对象, 期望的错误类别)]。"""
    cases: list[tuple[str, object, str]] = []

    # 1 无 JSON 代码块（模型只写散文）
    cases.append(("no_json_block", None, "S"))

    m = copy.deepcopy(base)
    m["references"][0]["doi_status"] = "maybe"
    cases.append(("bad_enum", m, "S"))

    m = copy.deepcopy(base)
    if m["references"]:
        m["references"].pop()
    cases.append(("coverage_gap", m, "C"))

    m = copy.deepcopy(base)
    for r in m["references"]:
        if r.get("doi_status") == "valid":
            r["evidence_url"] = ""
            break
    cases.append(("missing_evidence", m, "E"))

    m = copy.deepcopy(base)
    for r in m["references"]:
        if r.get("metadata_match") is False:
            r["verdict"] = "pass"
            break
    cases.append(("verdict_contradiction", m, "V"))

    m = copy.deepcopy(base)
    m["results"] = m.pop("references")
    cases.append(("schema_renamed", m, "S"))
    return cases


def main() -> None:
    sources = _load()
    rows, fp_errors = [], []
    for name, base in sources:
        errs = report_schema.validate(base, len(base["references"]))
        fp_errors.append({"source": name, "errors": errs})
        for mode, obj, expect in mutations(base):
            e = report_schema.validate(obj, len(base["references"])) if obj is not None \
                else ["S: 未找到可解析的 JSON 代码块"]
            caught = bool(e)
            cls = report_schema.summarize(e)
            rows.append({
                "source": name, "mode": mode, "caught": caught,
                "expected_class": expect, "classes": cls, "n_errors": len(e),
                "matched_expected": caught and cls.get(expect, 0) > 0,
            })

    total = len(rows)
    caught = sum(r["caught"] for r in rows)
    matched = sum(r["matched_expected"] for r in rows)
    summary = {
        "n_sources": len(sources),
        "n_cases": total,
        "detected": caught,
        "detection_rate": round(caught / total, 3) if total else 0,
        "matched_expected_class": matched,
        "false_positive_sources": sum(1 for f in fp_errors if f["errors"]),
        "per_case": rows,
        "source_errors": fp_errors,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fault_injection.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    print(f"sources={len(sources)} cases={total} detected={caught} "
          f"({summary['detection_rate']:.0%}) class_match={matched}/{total} "
          f"false_positive={summary['false_positive_sources']}")
    for r in rows:
        flag = "✓" if r["matched_expected"] else ("~" if r["caught"] else "✗")
        print(f"  {flag} {r['mode']:22s} expect={r['expected_class']} got={r['classes']}")


if __name__ == "__main__":
    main()
