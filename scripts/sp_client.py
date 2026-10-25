"""SciencePal HTTP 客户端（绕开 SDK 0.2.2 的 agents.list 解析 bug，直接处理 SSE）。

只做四件事：发起任务、读取流式事件、查询状态、列 Agent。
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import httpx


class SPClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 600):
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SPClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def list_agents(self) -> dict[str, Any]:
        r = self._client.get(self.base + "/agents", headers=self.headers)
        r.raise_for_status()
        return r.json()

    def initiate(
        self,
        agent_id: str,
        prompt: str,
        model_name: str | None = None,
        stream: bool = True,
        web_search_on: bool | None = None,
    ) -> dict[str, Any]:
        data = {
            "agent_id": agent_id,
            "prompt": prompt,
            "stream": "true" if stream else "false",
            "agent_select_type": "manual",
        }
        if model_name:
            data["model_name"] = model_name
        if web_search_on is not None:
            data["web_search_on"] = "true" if web_search_on else "false"
        r = self._client.post(self.base + "/agent/initiate", headers=self.headers, data=data)
        r.raise_for_status()
        return r.json()

    def stream(self, run_id: str) -> Iterator[tuple[str | None, Any]]:
        """逐行解析 SSE，yield (event_name, payload)。"""
        url = self.base + f"/agent-run/{run_id}/stream"
        with self._client.stream("GET", url, headers=self.headers) as r:
            r.raise_for_status()
            event: str | None = None
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        yield event, json.loads(payload)
                    except json.JSONDecodeError:
                        yield event, {"_raw": payload}
                    event = None

    def get_run(self, run_id: str) -> dict[str, Any]:
        r = self._client.get(self.base + f"/agent-run/{run_id}", headers=self.headers)
        r.raise_for_status()
        return r.json()
