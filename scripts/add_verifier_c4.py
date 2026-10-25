"""给核查 Agent 的阶段一补充/更新 C4 撤稿状态检查（幂等）。

DOI 有效（HTTP 200）不等于文献可安全引用：已撤稿论文仍解析为 200。
不同出版社标注方式不同：Springer/Nature 用标题前缀 "RETRACTED ARTICLE:"，
Cambridge 等用标题后缀 "- RETRACTED"，部分用 relation 指向撤稿通知。
"""
import re
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config

key, base = get_config()
aid = "b5834007-2e4a-4c08-b9de-c4707c31e136"
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

C4 = (
    "- C4 撤稿状态（DOI 有效不等于可安全引用，已撤稿论文 Crossref 仍返回 HTTP 200）："
    "对每条文献检查 Crossref 返回的标题是否带撤稿标记——包括开头的 “RETRACTED ARTICLE:” / “RETRACTED:” 前缀、"
    "结尾的 “- RETRACTED” 后缀，或标题中独立出现的 RETRACTED / RETRACTION / WITHDRAWN 字样（注意排除标题本身在讨论某主题的正常用法）；"
    "同时查看 relation / update-to 字段是否存在指向撤稿通知（retraction notice，has-retraction 等关系）的记录，"
    "或期刊页面明确标注 Retraction/Withdrawn。命中即 verdict=confirm，issue 写明撤稿状态与撤稿通知 DOI/URL；"
    "未发现撤稿标记则记为未撤稿，不得臆断。"
)

c = httpx.Client(timeout=30)
g = c.get(f"{base}/agents/{aid}", headers=H).json()
p = g["system_prompt"]

if "C4 撤稿状态" in p:
    start = p.find("- C4 撤稿状态")
    end = p.find("不得臆断。", start)
    assert start != -1 and end != -1, "定位旧 C4 失败"
    end += len("不得臆断。")
    p = p[:start] + C4 + p[end:]
    action = "更新"
else:
    anchor = "无法访问的被引文献标“无法访问”，不臆断。"
    assert anchor in p, "未找到 C3 锚点"
    p = p.replace(anchor, anchor + "\n" + C4)
    action = "新增"

r = c.put(f"{base}/agents/{aid}", headers=H, json={"system_prompt": p})
print("PUT HTTP", r.status_code, "|", action)
rp = r.json().get("system_prompt", "")
print("含 C4:", "C4 撤稿状态" in rp)
print("覆盖结尾标记:", "- RETRACTED" in rp)
print("更新后长度:", len(rp))
c.close()
