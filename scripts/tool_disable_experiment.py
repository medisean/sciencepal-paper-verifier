"""系统测试不同 agentpress_tools 配置对 execute_command 的硬禁用效果。"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config
from runner import run_job
from sp_client import SPClient

key, base = get_config()
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
c = httpx.Client(timeout=30)

# 创建一个临时测试 agent
r = c.post(f"{base}/agents", headers=H, json={
    "name": "tool-disable-probe（临时，可删）",
    "description": "临时工具禁用测试",
    "system_prompt": "你是测试助手。回答用户问题。",
})
print("create HTTP", r.status_code)
aid = r.json()["agent_id"]
print("test agent id:", aid)

PROMPT = ("请在沙箱用 curl 访问 https://api.crossref.org/works/10.1038/nature14539 和 "
          "https://api.crossref.org/works/10.1158/1538-7445.am2026-7860-X70217 ，"
          "报告 HTTP 状态。务必执行命令，不要只凭记忆回答。")

configs = [
    ("A_enabled_false", {"execute_command": {"enabled": False}, "web_search": {"enabled": False}}),
    ("B_null", {"execute_command": None}),
    ("C_empty", {}),
    ("D_all_core", {"execute_command": {"enabled": False}, "web_search": {"enabled": False},
                    "watch_task": {"enabled": False}, "file_manager": {"enabled": False},
                    "browser": {"enabled": False}, "code_interpreter": {"enabled": False}}),
]

save_dir = Path(__file__).resolve().parent.parent / "output" / "runs"
for label, cfg in configs:
    rr = c.put(f"{base}/agents/{aid}", headers=H, json={"agentpress_tools": cfg})
    print(f"\n配置 {label}: PUT {rr.status_code} -> {json.dumps(rr.json().get('agentpress_tools'), ensure_ascii=False)[:200]}")
    time.sleep(1)
    with SPClient(key, base) as sc:
        res = run_job(sc, aid, PROMPT, save_dir=save_dir, web_search_on=False)
    net_ok = False
    for t in res["tool_calls"]:
        body = str(t.get("content", ""))
        if ('"status":"ok"' in body or "HTTP 200" in body) and "crossref" in body.lower():
            net_ok = True
    print(f"  → 工具数={len(res['tool_calls'])} 成功联网={net_ok} 状态={res['status']}")
    time.sleep(2)

# 清理
d = c.delete(f"{base}/agents/{aid}", headers=H)
print("\n删除临时 agent:", d.status_code)
c.close()
