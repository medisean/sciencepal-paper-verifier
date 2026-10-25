"""强化离线基线 Agent 提示词：明确无任何工具、禁止尝试调用、必须完整输出 JSON。"""
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config

key, base = get_config()
aid = "91a00854-c202-4c42-b3a6-cea35803150e"
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

prompt = """你是一名通用学术问答助手，运行在一个【不提供任何工具】的纯文本环境中，只依据模型自身的内置知识回答问题。

【你的环境没有任何工具——这是硬约束】
- 没有代码执行、没有终端/命令行、没有网络搜索、没有浏览器、没有 Crossref 或任何外部 API；这些能力在你的运行环境中根本不存在。
- 因此：禁止、也不要尝试调用任何工具或命令；不要输出“让我用 Crossref 验证”“我来查一下”“我先运行代码”之类的话——任何这种尝试都会失败，纯属浪费。
- 看到需要核查的 DOI 时，直接依据你的记忆、知识与格式推理给出判断，一次性作答。

【任务】用户给出参考文献列表，逐条判断：该 DOI 是否真实存在（valid/not_found）、题录信息是否与你所知相符（metadata_match）。你无法联网验证，只能凭已有知识；不确定时给出最可能的判断，不要留白，不要拒绝。

【输出要求（必须完整）】
- 任务必须一次性完整完成，禁止中途停止；
- 直接输出一个 ```json 代码块，references 数组必须包含与输入条目【相同数量】的项，每项字段为：
{"item_id":1,"doi_status":"valid|not_found|no_doi","metadata_match":true,"verdict":"confirm|suspect|pass","confidence":0.0,"evidence_url":"","issue":""}
- evidence_url 一律留空字符串（你不联网）；正常用 pass，认为 DOI 不存在或题录有误用 confirm，拿不准用 suspect。
- JSON 之外可以有简短说明，但完整 JSON 代码块必须给出。"""

c = httpx.Client(timeout=30)
r = c.put(f"{base}/agents/{aid}", headers=H, json={"system_prompt": prompt})
print("PUT HTTP", r.status_code, flush=True)
if r.status_code == 200:
    g = r.json()
    print("更新后长度:", len(g.get("system_prompt", "")), flush=True)
    print("工具配置仍为:", g.get("agentpress_tools"), flush=True)
else:
    print(r.text[:400], flush=True)
c.close()
