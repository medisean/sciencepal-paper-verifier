"""guardrail 状态机的离线确定性测试（不消耗任何平台配额、不联网）。

用假的事件流与假的平台客户端驱动 GuardedRunner.run()，验证四条关键路径：
  S1 首次即合规      → 不修复、不拦截、first_pass_valid=True
  S2 出现被禁工具    → 触发 stop（且 stop 在纠正前发生），纠正后续跑并合规
  S3 首次无 JSON     → 触发一次定向修复，二轮合规
  S4 修满仍不合规    → 标记 degraded，修复次数等于上限

这组测试回答"机制是否按设计执行"，与在线实验的"模型多久失守"是两个问题。
用法：python3 scripts/test_guardrail_offline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guardrail import GuardedRunner  # noqa: E402

GOOD = {
    "references": [
        {"item_id": i, "doi_status": "valid", "metadata_match": True, "verdict": "pass",
         "confidence": 0.9, "evidence_url": f"https://api.crossref.org/works/10.1/{i}"}
        for i in (1, 2, 3)
    ],
    "overall_risk": "low",
}
GOOD_TEXT = "核查完成。\n```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
BAD_TEXT = "我按 CSV 格式给出结果：\n1,valid,pass\n2,valid,pass"


class FakeCtl:
    """记录控制面调用顺序（stop / messages / start）。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def post(self, url, **kw):
        self.calls.append(url.split("/api")[-1])
        outer = self

        class R:
            status_code = 200

            def json(self):
                return {"thread_id": "t1", "agent_run_id": "r0"}

            def raise_for_status(self):
                pass

        return R()

    def close(self) -> None:
        pass


class ScriptedRunner(GuardedRunner):
    """把 SSE 流换成脚本化的轮次。"""

    def __init__(self, rounds, **kw):
        super().__init__("k", "https://example.invalid/api", "aid", expect_items=3, **kw)
        self._script = list(rounds)
        self._ctl = FakeCtl()
        self.seen_stops: list[str] = []

    def _drain(self, run_id, round_idx):
        spec = self._script.pop(0)
        events = [{"type": "tool", "content": json.dumps({"name": n})} for n in spec.get("tools", [])]
        stop_info = {"stopped": spec.get("stopped", False),
                     "tool": spec.get("tool"), "latency_ms": 12.0}
        if stop_info["stopped"]:      # 真实实现里由 _drain 内部触发 stop
            self._stop(run_id)
        return events, spec.get("text", ""), {"total_tokens": 100}, stop_info

    def _stop(self, run_id):
        self.seen_stops.append(run_id)
        self._ctl.calls.append(f"/agent-run/{run_id}/stop")  # 与真实实现一样走控制面
        return True


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  {'✓' if cond else '✗'} {name}{(' — ' + detail) if detail and not cond else ''}")
    return cond


def main() -> int:
    ok = True

    # S1 首次即合规
    r = ScriptedRunner([{"text": GOOD_TEXT}])
    out = r.run("p")
    ok &= check("S1 不修复", out.n_repairs == 0)
    ok &= check("S1 不拦截", out.n_stops == 0)
    ok &= check("S1 first_pass_valid", out.first_pass_valid is True)
    ok &= check("S1 交付合规", not out.errors and out.json_result is not None)

    # S2 被禁工具 → stop → 纠正 → 合规
    r = ScriptedRunner([
        {"text": "", "tools": ["execute_command", "save_memory"], "stopped": True, "tool": "save_memory"},
        {"text": GOOD_TEXT},
    ])
    out = r.run("p")
    ok &= check("S2 拦截 1 次", out.n_stops == 1)
    ok &= check("S2 stop 在 messages 之前",
                r._ctl.calls.index("/agent-run/r0/stop") <
                [i for i, c in enumerate(r._ctl.calls) if c.startswith("/thread/")][0],
                str(r._ctl.calls))
    ok &= check("S2 纠正并续跑", any(c.startswith("/thread/") for c in r._ctl.calls))
    ok &= check("S2 最终合规", not out.errors)
    ok &= check("S2 干预记录 2 条", len(out.interventions) == 2, str(out.interventions))

    # S3 首次不合规 → 一次修复
    r = ScriptedRunner([{"text": BAD_TEXT}, {"text": GOOD_TEXT}])
    out = r.run("p")
    ok &= check("S3 修复 1 次", out.n_repairs == 1)
    ok &= check("S3 first_pass_valid=False", out.first_pass_valid is False)
    ok &= check("S3 最终合规", not out.errors)

    # S4 修满仍不合规 → degraded
    r = ScriptedRunner([{"text": BAD_TEXT}, {"text": BAD_TEXT}, {"text": BAD_TEXT}])
    out = r.run("p")
    ok &= check("S4 degraded", out.degraded is True)
    ok &= check("S4 修复次数=上限(2)", out.n_repairs == 2, str(out.n_repairs))

    # S5 声明-轨迹一致性（E2）：结论必须能在工具输出里找到取证痕迹
    g = ScriptedRunner([])
    g.trace_check = True
    g.expect_dois = ["10.1/abc", "10.1/def"]
    hit = [{"type": "tool", "content": "=== 10.1/abc ===\nHTTP:200\n=== 10.1/def ===\nHTTP:404"}]
    miss = [{"type": "tool", "content": "=== 10.1/abc ===\nHTTP:200"}]
    ok &= check("S5 有痕迹不报错", g._trace_errors(hit) == [])
    ok &= check("S5 缺痕迹被拦", any("10.1/def" in e for e in g._trace_errors(miss)))
    g.trace_check = False
    ok &= check("S5 关闭时不拦截", g._trace_errors(miss) == [])

    print("\n全部通过" if ok else "\n存在失败用例")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
