"""D0 链路探测：用核查 Agent 跑一个单 DOI 任务，dump SSE 事件结构，跑通发起→流式→终态。"""
import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_config, project_root
from sp_client import SPClient

PROMPT = "请核查这个 DOI 是否真实存在：10.1038/nature14539。简短返回标题、作者、年份、HTTP 状态与证据 URL，并在末尾给出你实际执行的联网命令。"


def main() -> None:
    api_key, base = get_config()
    agent_id = os.environ.get("VERIFIER_AGENT_ID", "").strip()
    if not agent_id:
        # 从 .env 读
        from common import load_env
        load_env()
        agent_id = os.environ.get("VERIFIER_AGENT_ID", "").strip()
    assert agent_id, "VERIFIER_AGENT_ID 未配置"

    out_dir = project_root() / "output"
    out_dir.mkdir(exist_ok=True)
    raw_path = out_dir / "probe_events.jsonl"

    with SPClient(api_key, base) as client:
        run = client.initiate(agent_id, PROMPT)
        thread_id = run.get("thread_id")
        run_id = run.get("agent_run_id")
        print("thread_id:", thread_id)
        print("run_id   :", run_id)
        assert run_id, f"未创建 run：{run}"

        event_types = collections.Counter()
        sample_keys: dict[str, set] = {}
        assistant_text_parts: list[str] = []

        with raw_path.open("w", encoding="utf-8") as f:
            for event, payload in client.stream(run_id):
                f.write(json.dumps({"event": event, "data": payload}, ensure_ascii=False) + "\n")
                event_types[event or "(none)"] += 1
                keys = sample_keys.setdefault(event or "(none)", set())
                if isinstance(payload, dict):
                    keys.update(payload.keys())

                # 粗略提取可能的文本/工具字段
                if isinstance(payload, dict):
                    for k in ("text", "content", "delta", "message", "tool_name", "name", "type"):
                        v = payload.get(k)
                        if k in ("text", "delta", "content") and isinstance(v, str) and len(v) > 20:
                            assistant_text_parts.append(v)

        print("\n事件类型计数：", dict(event_types))
        print("\n各事件 payload 字段：")
        for ev, keys in sample_keys.items():
            print(f"  {ev}: {sorted(keys)}")

        status = client.get_run(run_id)
        print("\n终态：", json.dumps({k: status.get(k) for k in
              ("status", "error", "thread_id", "agent_run_id")}, ensure_ascii=False))
        print("\n原始事件已写入：", raw_path)


if __name__ == "__main__":
    main()
