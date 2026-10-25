"""运行一次核查任务并解析结果：发起 → 收集 SSE → 提取最终报告 / JSON / 工具证据。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sp_client import SPClient

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _load_content(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("content")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def parse_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """把原始 SSE 事件解析为最终报告、JSON 结果、工具调用证据与用量。"""
    assistant_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    final_text: str | None = None
    usage: dict[str, Any] = {}
    status_seen: list[str] = []

    for e in events:
        d = e.get("data", {})
        if not isinstance(d, dict):
            continue
        t = d.get("type")
        c = _load_content(d)

        if t == "status":
            status_seen.append(c.get("status_type", ""))
        elif t == "assistant" and isinstance(c.get("content"), str):
            assistant_parts.append(c["content"])
        elif t == "tool":
            tool_calls.append({
                "name": c.get("name"),
                "content": c.get("content"),
                "success": json.loads(d.get("metadata", "{}")).get("tool_success")
                if isinstance(d.get("metadata"), str) else None,
            })
        elif t == "assistant_response_end":
            choice = (c.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            if isinstance(msg.get("content"), str) and msg["content"].strip():
                final_text = msg["content"]  # 以最后一个完整消息为准
            if c.get("usage"):
                usage = c["usage"]

    if final_text is None:
        final_text = "".join(assistant_parts)

    json_result = extract_json(final_text)
    return {
        "final_text": final_text,
        "json_result": json_result,
        "tool_calls": tool_calls,
        "usage": usage,
        "status_path": status_seen,
    }


def extract_json(text: str) -> dict[str, Any] | None:
    """从报告中提取最后一个 ```json 代码块；失败则尝试裸花括号。"""
    blocks = JSON_BLOCK_RE.findall(text)
    for block in reversed(blocks):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    # 退化：尝试定位最后一个最外层 { ... }
    m = re.search(r"(\{[\s\S]*\})", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def run_job(
    client: SPClient,
    agent_id: str,
    prompt: str,
    model_name: str | None = None,
    save_dir: Path | None = None,
    web_search_on: bool | None = None,
) -> dict[str, Any]:
    run = client.initiate(agent_id, prompt, model_name=model_name, web_search_on=web_search_on)
    thread_id = run.get("thread_id")
    run_id = run.get("agent_run_id")
    if not run_id:
        raise RuntimeError(f"未创建 run：{run}")

    raw_events: list[dict[str, Any]] = []
    for event, payload in client.stream(run_id):
        raw_events.append({"event": event, "data": payload})

    final_status = client.get_run(run_id)
    parsed = parse_events(raw_events)

    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / f"{run_id}.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in raw_events),
            encoding="utf-8",
        )

    return {
        "thread_id": thread_id,
        "run_id": run_id,
        "status": final_status.get("status"),
        "error": final_status.get("error"),
        **parsed,
    }
