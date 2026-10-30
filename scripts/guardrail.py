"""运行时 guardrail：把"提示词约束"升级为"代码级强制"。

三个机制，全部在我们的进程里执行，模型无法绕过：

1) 策略拦截（stop）：逐事件监视 SSE 流，一旦发现被禁工具（save_memory / 反问 / 浏览器接管等），
   立刻调用 POST /agent-run/{id}/stop 中断该 run，并下发定向纠正指令后续跑同一 thread。
2) 交付契约（schema）：最终 JSON 必须通过 report_schema 校验（结构/覆盖/证据/自洽四类）；
   不通过则把具体错误反馈给模型，限次数自动修复（默认 2 轮），仍不通过则标记 degraded。
3) 全程留痕：每轮 run_id、拦截事件、修复轮次、token 用量写入结果文件，可逐条复核。

对上层只暴露 run()，返回结构化结果，便于评测脚本批量调用。
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

import report_schema
from runner import extract_json
from sp_client import SPClient

# 被禁工具：写长期记忆、反问用户、浏览器接管（本任务一律不需要）
DEFAULT_FORBIDDEN = {
    "save_memory": "禁止写入长期记忆",
    "load_memory": "禁止读取长期记忆",
    "search_memory": "禁止检索长期记忆",
    "ask": "禁止向用户反问、等待人工输入",
    "web_browser_takeover": "禁止浏览器接管",
}
# 允许的取证/执行工具（用于统计，不做硬拦截）
DEFAULT_ALLOWED = {
    "execute_command", "watch_task", "check_command_output", "create_file",
    "str_replace_editor", "search_skills", "load_skill", "record_skill_outcome",
    "complete", "web_search", "code_interpreter",
}


@dataclass
class Intervention:
    kind: str          # policy_stop | repair | hard_timeout
    round: int
    detail: str
    run_id: str | None = None
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "round": self.round, "detail": self.detail,
                "run_id": self.run_id, "at": round(self.at, 3)}


@dataclass
class GuardResult:
    thread_id: str
    rounds: list[dict[str, Any]]
    json_result: dict | None
    final_text: str
    errors: list[str]
    interventions: list[dict[str, Any]]
    first_pass_valid: bool
    n_repairs: int
    n_stops: int
    degraded: bool
    wall_seconds: float
    usage: dict[str, Any]
    tool_counts: dict[str, int]
    tool_contents: list[str]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class GuardedRunner:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        agent_id: str,
        *,
        expect_items: int | None = None,
        max_repairs: int = 2,
        forbidden: dict[str, str] | None = None,
        run_timeout: float = 900.0,
        save_dir: Path | None = None,
        model_name: str | None = None,
        web_search_on: bool | None = None,
        expect_dois: list[str] | None = None,
        trace_check: bool = False,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.agent_id = agent_id
        self.expect_items = expect_items
        self.max_repairs = max_repairs
        self.forbidden = forbidden or DEFAULT_FORBIDDEN
        self.run_timeout = run_timeout
        self.save_dir = save_dir
        self.model_name = model_name
        self.web_search_on = web_search_on
        # 声明-轨迹一致性校验：每条引用必须在工具输出里留下真实取证痕迹
        self.expect_dois = expect_dois or []
        self.trace_check = trace_check
        # item_id -> DOI，供 E3/E4（证据指向性）使用
        self._doi_map = {i + 1: d for i, d in enumerate(self.expect_dois) if d}
        self._ctl = httpx.Client(timeout=60)
        self._sp = SPClient(api_key, self.base)

    # ---------- 底层 ----------
    def _post(self, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        return self._ctl.post(self.base + path, headers=self.headers, json=payload or {})

    def _stop(self, run_id: str) -> bool:
        try:
            r = self._post(f"/agent-run/{run_id}/stop")
            return r.status_code < 400
        except httpx.HTTPError:
            return False

    def _send(self, thread_id: str, content: str) -> None:
        """SDK 契约：message_id 必填（同一次提交重试时复用同一个 id 以免重复落库）。"""
        r = self._post(f"/thread/{thread_id}/messages",
                       {"message_id": str(uuid.uuid4()), "content": content})
        r.raise_for_status()

    def _start(self, thread_id: str) -> str:
        payload: dict[str, Any] = {"agent_id": self.agent_id, "stream": True}
        if self.model_name:
            payload["model_name"] = self.model_name
        if self.web_search_on is not None:
            payload["web_search_on"] = self.web_search_on
        r = self._post(f"/thread/{thread_id}/agent/start", payload)
        r.raise_for_status()
        return r.json()["agent_run_id"]

    def _drain(self, run_id: str, round_idx: int
               ) -> tuple[list[dict[str, Any]], str, dict[str, Any], dict[str, Any]]:
        """读取一轮 SSE：返回 (事件, 最终文本, 用量, 是否被拦截)。"""
        events: list[dict[str, Any]] = []
        q: queue.Queue = queue.Queue()
        stop_flag = {"stopped": False, "reason": ""}

        def worker() -> None:
            try:
                for ev, payload in self._sp.stream(run_id):
                    q.put(("ev", payload))
            except Exception as exc:  # noqa: BLE001 - 流异常要如实记录
                q.put(("err", repr(exc)))
            finally:
                q.put(("end", None))

        threading.Thread(target=worker, daemon=True).start()
        deadline = time.time() + self.run_timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._stop(run_id)
                stop_flag.update(stopped=True, reason="hard_timeout")
                break
            try:
                kind, payload = q.get(timeout=min(5.0, remaining))
            except queue.Empty:
                continue
            if kind == "end":
                break
            if kind == "err":
                events.append({"type": "stream_error", "detail": payload})
                break
            events.append(payload if isinstance(payload, dict) else {"_raw": payload})
            if isinstance(payload, dict) and payload.get("type") == "tool":
                content = payload.get("content")
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
                        content = {}
                name = (content or {}).get("name") if isinstance(content, dict) else None
                if name in self.forbidden and not stop_flag["stopped"]:
                    t_stop = time.time()
                    self._stop(run_id)
                    stop_flag.update(stopped=True, reason=f"{name}: {self.forbidden[name]}",
                                     latency_ms=round((time.time() - t_stop) * 1000, 1),
                                     tool=name)
                    # 停止后只再等一小段时间把流读干，避免卡死
                    deadline = min(deadline, time.time() + 20.0)
                    continue

        # 统计最终文本与用量
        final_text = ""
        usage: dict[str, Any] = {}
        for e in events:
            if e.get("type") == "assistant_response_end":
                c = e.get("content")
                if isinstance(c, str):
                    try:
                        c = json.loads(c)
                    except json.JSONDecodeError:
                        c = {}
                msg = ((c.get("choices") or [{}])[0] or {}).get("message", {}) or {}
                if isinstance(msg.get("content"), str) and msg["content"].strip():
                    final_text = msg["content"]
                if c.get("usage"):
                    usage = c["usage"]
        self._log_events(run_id, events)
        return events, final_text, usage, stop_flag

    def _log_events(self, run_id: str, events: list[dict[str, Any]]) -> None:
        if not self.save_dir:
            return
        self.save_dir.mkdir(parents=True, exist_ok=True)
        path = self.save_dir / f"{run_id}.jsonl"
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8")

    # ---------- 主流程 ----------
    def run(self, prompt: str) -> GuardResult:
        t0 = time.time()
        r = self._ctl.post(
            self.base + "/agent/initiate",
            headers={"Authorization": self.headers["Authorization"]},
            data={
                "agent_id": self.agent_id,
                "prompt": prompt,
                "stream": "true",
                "agent_select_type": "manual",
                **({"model_name": self.model_name} if self.model_name else {}),
                **({"web_search_on": "true" if self.web_search_on else "false"}
                   if self.web_search_on is not None else {}),
            },
        )
        r.raise_for_status()
        thread_id = r.json()["thread_id"]
        run_id = r.json()["agent_run_id"]

        rounds: list[dict[str, Any]] = []
        interventions: list[dict[str, Any]] = []
        tool_counts: dict[str, int] = {}
        tool_contents: list[str] = []
        total_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
        final_text = ""
        payload: dict | None = None
        errors: list[str] = []
        repair_idx = 0
        stops = 0
        first_pass_valid = False
        pending_message: str | None = None

        while True:
            events, text, usage, stop_info = self._drain(run_id, len(rounds))
            was_stopped = bool(stop_info.get("stopped"))
            if text:
                final_text = text
            for e in events:
                if e.get("type") == "tool":
                    c = e.get("content")
                    if isinstance(c, str):
                        try:
                            c = json.loads(c)
                        except json.JSONDecodeError:
                            c = {}
                    nm = (c or {}).get("name") if isinstance(c, dict) else None
                    if nm:
                        tool_counts[nm] = tool_counts.get(nm, 0) + 1
                    tool_contents.append(str(c)[:500])
            for k in total_usage:
                total_usage[k] += int((usage or {}).get(k) or 0)

            if was_stopped:
                stops += 1
                interventions.append(Intervention(
                    kind="policy_stop", round=len(rounds),
                    detail=(f"{self._stop_reason(events)}；"
                            f"工具={stop_info.get('tool')}；stop 往返 {stop_info.get('latency_ms')} ms"),
                    run_id=run_id).as_dict())
                pending_message = self._correction_message(events)
                rounds.append({"run_id": run_id, "stopped": True, "tools": len(events)})
                if stops > self.max_repairs + 1:
                    errors = ["策略拦截次数超限，终止"]
                    break
            else:
                payload = extract_json(final_text)
                errors = report_schema.validate(payload, self.expect_items, self._doi_map or None) \
                    if payload is not None else ["S: 未找到可解析的 JSON 代码块"]
                if payload is not None and not errors:
                    errors = self._trace_errors(events)
                rounds.append({
                    "run_id": run_id, "stopped": False,
                    "parsed": payload is not None, "n_errors": len(errors),
                    "errors": errors[:8],
                })
                if not errors:
                    if len(rounds) == 1:
                        first_pass_valid = True
                    break

            # 需要修复：先发消息，再在同一 thread 续跑
            if repair_idx >= self.max_repairs:
                break
            repair_idx += 1
            msg = pending_message or report_schema.repair_instruction(errors, self.expect_items)
            pending_message = None
            interventions.append(Intervention(
                kind="repair" if not was_stopped else "corrective_prompt",
                round=len(rounds), detail=(errors[:3] if errors else "policy"), run_id=run_id).as_dict())
            self._send(thread_id, msg)
            run_id = self._start(thread_id)

        degraded = bool(errors)
        return GuardResult(
            thread_id=thread_id, rounds=rounds, json_result=payload, final_text=final_text,
            errors=errors, interventions=interventions, first_pass_valid=first_pass_valid,
            n_repairs=repair_idx, n_stops=stops, degraded=degraded,
            wall_seconds=round(time.time() - t0, 1), usage=total_usage, tool_counts=tool_counts,
            tool_contents=tool_contents,
        )

    def _trace_errors(self, events: list[dict[str, Any]]) -> list[str]:
        """声明-轨迹一致性：结论必须能在本次 run 的工具输出里找到对应取证痕迹。

        这比 schema 更硬：它不允许"没查过却给出 valid/not_found 结论"。
        """
        if not self.trace_check or not self.expect_dois:
            return []
        text = "\n".join(str(e.get("content", "")) for e in events if e.get("type") == "tool").lower()
        errs: list[str] = []
        for i, doi in enumerate(self.expect_dois, 1):
            if not doi:
                continue
            m = re.search(re.escape(doi.lower()), text)
            if not m:
                errs.append(f"E2: item_id={i} 的 DOI {doi} 未出现在任何工具输出中（该条没有实际联网取证）")
                continue
            window = text[max(0, m.start() - 800): m.end() + 800]
            if not re.search(r"\b(200|404|302)\b", window):
                errs.append(f"E2: item_id={i} 的取证输出中没有可核对的 HTTP 状态码")
        return errs

    def _stop_reason(self, events: list[dict[str, Any]]) -> str:
        for e in events:
            if e.get("type") == "tool":
                c = e.get("content")
                if isinstance(c, str):
                    try:
                        c = json.loads(c)
                    except json.JSONDecodeError:
                        c = {}
                nm = (c or {}).get("name") if isinstance(c, dict) else None
                if nm in self.forbidden:
                    return f"{nm}（{self.forbidden[nm]}）"
        return "policy_violation"

    def _correction_message(self, events: list[dict[str, Any]]) -> str:
        reason = self._stop_reason(events)
        return (
            f"【运行时策略拦截】你刚刚的 {reason} 已被 guardrail 中断，该操作不允许执行。\n"
            "请从当前进度继续完成核查任务：只用 execute_command 在沙箱内联网取证（Crossref），"
            "不要写长期记忆、不要反问用户、不要接管浏览器。\n"
            "若已完成全部条目，请直接输出最终报告与末尾固定 schema 的 ```json 代码块；"
            "已核查过的条目不必重复取证。"
        )

    def close(self) -> None:
        self._ctl.close()
        self._sp.close()
