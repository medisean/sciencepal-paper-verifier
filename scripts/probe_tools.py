import httpx
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config

key, base = get_config()
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
aid = "91a00854-c202-4c42-b3a6-cea35803150e"

c = httpx.Client(timeout=30)
r = c.get(f"{base}/agents/{aid}", headers=H)
print("GET HTTP", r.status_code, flush=True)
g = r.json()
print("keys:", list(g.keys()), flush=True)
print("agentpress_tools:", json.dumps(g.get("agentpress_tools"), ensure_ascii=False), flush=True)
print("tool_profile:", g.get("tool_profile"), "runtime:", g.get("runtime_agent_type"), flush=True)

attempts = [
    {"execute_command": False, "web_search": False, "file_manager": False},
    {"execute_command": {"enabled": False}, "web_search": {"enabled": False}},
]
for att in attempts:
    try:
        rr = c.put(f"{base}/agents/{aid}", headers=H, json={"agentpress_tools": att})
        print("\nPUT", json.dumps(att, ensure_ascii=False)[:70], "-> HTTP", rr.status_code, flush=True)
        if rr.status_code == 200:
            print("回显:", json.dumps(rr.json().get("agentpress_tools"), ensure_ascii=False)[:300], flush=True)
        else:
            print("错误:", rr.text[:300], flush=True)
    except Exception as e:
        print("异常:", repr(e), flush=True)
c.close()
