"""快速验证：web_search_on=False 时，基线 Agent 是否还会用沙箱联网 curl。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config, load_env
from runner import run_job
from sp_client import SPClient

load_env()
api_key, base = get_config()
agent_id = os.environ["GENERAL_AGENT_ID"]

prompt = (
    "请仅凭你的知识判断这两个 DOI 是否真实存在（不要联网）："
    "(1) 10.1038/nature14539  (2) 10.1158/1538-7445.am2026-7860-X70217。"
    "给出你的判断和理由。"
)
with SPClient(api_key, base) as c:
    r = run_job(c, agent_id, prompt, web_search_on=False,
                save_dir=Path(__file__).resolve().parent.parent / "output" / "runs")
print("status:", r["status"])
print("工具调用:", [t["name"] for t in r["tool_calls"]])
print("---- 最终文本（前 1200 字）----")
print(r["final_text"][:1200])
