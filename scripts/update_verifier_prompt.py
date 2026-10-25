"""强化核查 Agent 提示词：C2 逐字段严格比对 + ref_id 编号对齐。"""
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_config

key, base = get_config()
aid = "b5834007-2e4a-4c08-b9de-c4707c31e136"
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

c = httpx.Client(timeout=30)
g = c.get(f"{base}/agents/{aid}", headers=H).json()
p = g["system_prompt"]

old_c2 = "- C2 元数据匹配：核对 DOI 解析出的标题、作者、期刊、年份、卷期页码与论文所写是否一致；关键字段不一致即元数据错误（confirm/suspect）。"
new_c2 = (
    "- C2 元数据匹配（必须逐字段严格比对，禁止只看 DOI 能解析就放行）：把该 DOI 在 Crossref 返回的真实记录与引用所写逐项比对——"
    "①年份：以 Crossref 的 issued.date-parts 年份为准（在线优先/正式见刊或有多个年份时，取与该出版类型对应的发表年份），与引用年份必须一致；"
    "②作者：第一作者姓氏及作者数量/顺序；③标题：核心标题词（忽略大小写、标点与多余空格）；④期刊/来源名；⑤卷 volume、期 issue、页码/文章号。"
    "任一字段不一致，metadata_match 必须填 false、verdict=confirm，并在 issue 中写明“字段名：真实值→引用值”。"
    "严禁因 HTTP 200/DOI 可解析就判 metadata_match=true：DOI 真实但题录被篡改（尤其是年份/作者/期刊被改）同样是必须报告的错误。"
)
assert old_c2 in p, "未找到 C2 原文"
p = p.replace(old_c2, new_c2)

p = p.replace('{"ref_id": 1,', '{"item_id": 1,')

r = c.put(f"{base}/agents/{aid}", headers=H, json={"system_prompt": p})
print("PUT HTTP", r.status_code, flush=True)
if r.status_code == 200:
    print("更新后长度:", len(r.json().get("system_prompt", "")), flush=True)
    print("含强化C2:", "逐字段严格比对" in r.json().get("system_prompt", ""), flush=True)
else:
    print(r.text[:400], flush=True)
c.close()
