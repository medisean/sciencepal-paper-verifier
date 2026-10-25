"""创建第三组对照 Agent：普通联网学术助手。

与核查 Agent（verifier）的区别：
- 工具同样全开（execute_command + web_search 可用），因此能联网、能执行命令；
- 但系统提示词只给一个朴素任务描述，不规定专家核查工作流
  （不强制 Crossref、不要求逐字段比对、不要求撤稿 relation 检查、不要求统计复算）。

它回答的是评委会追问的问题："如果只是让一个能上网的通用 Agent 来查，效果一样吗？"
输出 schema 与 verifier 保持一致，仅用于让评分脚本可对齐。
"""
import sys
import json
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config

key, base = get_config()
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

NAIVE_PROMPT = """你是一名学术助手，运行环境提供一个可联网的终端（可执行 curl 等命令）。用户会直接给你一批参考文献，请立即动手、一次性完成全部核查。

【最高原则】
1. 不得仅凭记忆或常识判断。对每条参考文献，都要在终端实际执行命令联网核实（例如用 curl 请求 DOI 解析地址 https://doi.org/{DOI} 看返回状态，或访问学术数据库 / 联网搜索），并记录实际访问的 URL。
2. 现在就从第一条引用的第一条终端命令开始执行，逐条完成。禁止使用 ask、浏览器接管等任何向用户提问或等待确认的工具，也不要请求授权，直接执行。
3. 全部条目一次性完成，不要中途停止。
4. 不要保存或读取任何记忆（禁止调用 save_memory、load_memory 等记忆工具），不做与本次核查无关的事，最终只输出核查结果与 JSON。

【任务】
逐条核查：DOI 是否真实存在；题录信息（作者、年份、标题、期刊/卷期页）是否正确；有无其他明显问题。具体查哪些来源、怎么查由你判断，但必须实际联网取证。

【输出】
全部完成后，输出一个 ```json 代码块，references 数组必须包含与输入条目【相同数量】的项，每项字段为：
{"item_id":1,"doi_status":"valid|not_found|no_doi","metadata_match":true,"verdict":"confirm|suspect|pass","confidence":0.0,"evidence_url":"","issue":""}
- 正常无误用 pass；确认 DOI 不存在或题录有问题用 confirm，并在 issue 里写明；拿不准用 suspect。
- 有联网取证时，把来源 URL 填进 evidence_url。"""

c = httpx.Client(timeout=30)

# 先检查是否已存在（按名字），避免重复创建
r = c.get(f"{base}/agents", headers=H)
r.raise_for_status()
data = r.json()
items = data if isinstance(data, list) else data.get("agents") or data.get("data") or []
existing = next((a for a in items if "普通联网" in (a.get("name") or "")), None)

body = {
    "name": "普通联网学术助手（工作流对照）",
    "description": "工具全开、可联网可执行，但不加载专家核查工作流，作为对照：验证增益来自核查工作流而非平台联网本身。",
    "system_prompt": NAIVE_PROMPT,
    "runtime_agent_type": "general",
}

if existing:
    aid = existing["agent_id"]
    print("已存在，仅更新提示词（绝不改动工具配置）：", aid, flush=True)
    r = c.put(f"{base}/agents/{aid}", headers=H, json={"system_prompt": NAIVE_PROMPT})
else:
    r = c.post(f"{base}/agents", headers=H, json=body)
    print("POST /agents HTTP", r.status_code, flush=True)
    assert r.status_code in (200, 201), r.text[:600]
    aid = r.json().get("agent_id") or r.json().get("id")
    print("新 Agent（创建时不设工具，默认与平台一致全开）：", aid, flush=True)

# 回读确认
g = c.get(f"{base}/agents/{aid}", headers=H).json()
print("\n=== 回读确认 ===")
print("agent_id:", g.get("agent_id"))
print("name:", g.get("name"))
print("runtime:", g.get("runtime_agent_type"))
print("tools:", json.dumps(g.get("agentpress_tools"), ensure_ascii=False))
print("\n请把下面这行写入 .env：")
print(f"NAIVE_AGENT_ID={aid}")
c.close()
