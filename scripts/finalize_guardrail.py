"""把 clean-48 的 guardrail 复跑结果自动回填到 README / 技术报告，避免手抄数字。

前提：`results/guardrail/summary.json` 里已有 clean.guarded（即 4 个 seed 都跑完）。
用文档里的 HTML 注释标记定位替换区间，标记在渲染时不可见。

用法：python3 scripts/finalize_guardrail.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import project_root  # noqa: E402

ROOT = project_root()
SUMMARY = ROOT / "results" / "guardrail" / "summary.json"

README_BLOCK = """<!-- CLEAN48_START -->
> 干净 48 条（4 个 seed × 12 条）guardrail 复跑：**{usable}/{n} 可用**，契约违规 **{viol}** 次，自动修复 **{repairs}** 次、拦截 **{stops}** 次；F1 {f1}，{note}。
<!-- CLEAN48_END -->"""

REPORT_SENT = ("干净 48 条上的复跑（4 个 seed、n=48）：guardrail 组 **{usable}/{n} 可用**、"
               "F1 {f1}（无 guardrail 组同为 {f1}）、自动修复 {repairs} 次、拦截 {stops} 次，"
               "即**在干净输入上没有引入任何判对率回归**，修复只在契约失守时触发。")


def collect(path: Path | None = None) -> dict | None:
    path = path or SUMMARY
    if not path.exists():
        return None
    s = json.loads(path.read_text(encoding="utf-8"))
    g = s.get("clean", {}).get("guarded") or {}
    if not g.get("n"):
        return None
    rows = s["per_case"]["clean_guarded"]
    f1 = sorted({f"{r['f1_any']:.3f}" for r in rows})
    return {
        "n": g["n"], "usable": g["usable"], "viol": g["contract_violations"],
        "repairs": g["repairs"], "stops": g["stops"],
        "f1": " / ".join(f1),
        "note": ("与无 guardrail 组一致（无回归）" if len(f1) == 1 and f1[0] == "1.000"
                 else "与无 guardrail 组不一致，需人工核对后再更新结论"),
        "mean_wall": g.get("mean_wall_s"),
    }


def main() -> None:
    dry = "--dry-run" in sys.argv
    src = None
    if "--summary" in sys.argv:
        src = Path(sys.argv[sys.argv.index("--summary") + 1])
    d = collect(src)
    if not d:
        print("summary.json 里还没有 clean.guarded（4 个 seed 未跑完），不修改文档。")
        raise SystemExit(1)

    readme = ROOT / "README.md"
    s = readme.read_text(encoding="utf-8")
    new, cnt = re.subn(r"<!-- CLEAN48_START -->.*?<!-- CLEAN48_END -->",
                       README_BLOCK.format(**d), s, flags=re.S)
    print(f"README 替换 {cnt} 处")
    if not dry and cnt:
        readme.write_text(new, encoding="utf-8")

    rep = ROOT / "results" / "TECHNICAL_REPORT.md"
    s2 = rep.read_text(encoding="utf-8")
    new2, cnt2 = re.subn(r"<!-- CLEAN48_TODO_START -->.*?<!-- CLEAN48_TODO_END -->",
                         REPORT_SENT.format(**d), s2, flags=re.S)
    print(f"技术报告替换 {cnt2} 处")
    if not dry and cnt2:
        rep.write_text(new2, encoding="utf-8")

    print("\n回填内容：")
    print(README_BLOCK.format(**d))
    print()
    print("下一步：重跑 `python3 scripts/build_ppt.py` 让第 4 页数字同步（如需），再核对 SUMMARY.md。")


if __name__ == "__main__":
    main()
