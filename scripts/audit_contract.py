"""回溯审计：把当前交付契约套到**所有已保存的历史结果**上（不联网、不耗配额）。

回答两个问题：
1) 新契约（S 结构 / C 覆盖 / E 证据 / E3 指向 / E4 域名 / V 自洽）在本作品已有产物上是否成立？
2) 哪些组（离线基线 / 普通联网 / 专家 / guardrail）在三方对照里本就不满足契约？

这既是自检，也是"契约不是事后编出来的"的证据：它被应用到了契约定稿之前跑出来的数据上。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_schema
from common import project_root

ROOT = project_root()
OUT = ROOT / "results" / "guardrail"


def bundle_for(case: str) -> dict | None:
    for p in (ROOT / "data" / "eval" / f"{case}.json",
              ROOT / "data" / "eval" / "adversarial" / f"{case}.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def collect() -> list[dict]:
    rows = []
    for p in sorted((ROOT / "output" / "eval").glob("*.json")):
        if p.name.startswith("._"):
            continue
        case = p.stem.rsplit("__", 1)[0]
        tag = p.stem.rsplit("__", 1)[-1]
        b = bundle_for(case)
        if not b:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows.append({"group": tag, "case": case, "bundle": b,
                     "json_result": d.get("json_result"), "source": str(p.relative_to(ROOT))})
    for p in sorted((ROOT / "results" / "guardrail").glob("*__*.json")):
        if p.name.startswith(("._", "summary", "fault_injection", "contract_audit")):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if "error" in d:
            continue
        b = bundle_for(d.get("case", ""))
        if not b:
            continue
        rows.append({"group": d.get("mode", "?"), "case": d["case"], "bundle": b,
                     "json_result": d.get("json_result"), "source": str(p.relative_to(ROOT))})
    return rows


def main() -> None:
    rows = collect()
    out = []
    for r in rows:
        expect = len(r["bundle"]["items"])
        dois = {it["item_id"]: it.get("doi") for it in r["bundle"]["items"]}
        errs = report_schema.validate(r["json_result"], expect, dois) if r["json_result"] is not None \
            else ["S: 未找到可解析的 JSON 代码块"]
        codes: dict[str, int] = {}
        for e in errs:
            code = e.split(":", 1)[0].strip()
            if code:
                codes[code] = codes.get(code, 0) + 1
        out.append({"group": r["group"], "case": r["case"], "source": r["source"],
                    "compliant": not errs, "classes": report_schema.summarize(errs),
                    "codes": codes,
                    "n_errors": len(errs), "errors": errs[:6]})

    by_group: dict[str, dict] = {}
    for r in out:
        g = by_group.setdefault(r["group"], {"n": 0, "compliant": 0})
        g["n"] += 1
        g["compliant"] += int(r["compliant"])

    summary = {"groups": by_group, "rows": out}
    (OUT / "contract_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                             encoding="utf-8")

    md = ["# 交付契约回溯审计（自动生成）", "",
          "把当前契约套到契约定稿之前跑出的历史结果上，检查其成立性。", "",
          "| 组 | 样本 | 合规 | 不合规主要原因 |", "|---|---|---|---|"]
    for g, v in sorted(by_group.items()):
        cls: dict[str, int] = {}
        for r in out:
            if r["group"] == g:
                for k, n in (r.get("codes") or {}).items():
                    cls[k] = cls.get(k, 0) + n
        main_cls = ", ".join(f"{k}×{n}" for k, n in sorted(cls.items(), key=lambda x: -x[1])) or "-"
        md.append(f"| {g} | {v['n']} | {v['compliant']}/{v['n']} | {main_cls} |")
    md += ["", "## 逐条", "", "| 组 | case | 合规 | 错误数 | 来源 |", "|---|---|---|---|---|"]
    for r in out:
        md.append(f"| {r['group']} | {r['case']} | {'✓' if r['compliant'] else '✗'} | "
                  f"{r['n_errors']} | `{r['source']}` |")
    (OUT / "CONTRACT_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
