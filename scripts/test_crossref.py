import httpx
import json
import sys

H = {"User-Agent": "SciencePalHackathon/0.1 (mailto:test@example.com)"}

try:
    r = httpx.get("https://api.crossref.org/works/10.1038/nature14539", headers=H, timeout=30)
    print("单篇:", r.status_code)
    m = r.json()["message"]
    print("标题:", m.get("title"))
    print("reference 字段:", "reference" in m, "| 数:", len(m.get("reference", [])))
except Exception as e:
    print("单篇失败:", type(e).__name__, e)
    sys.exit(1)

r2 = httpx.get(
    "https://api.crossref.org/works",
    params={
        "query": "machine learning clinical prediction",
        "filter": "type:journal-article",
        "rows": 3,
        "select": "DOI,title,author,is-referenced-by-count,reference",
    },
    headers=H,
    timeout=30,
)
print("\n检索:", r2.status_code)
for it in r2.json()["message"]["items"]:
    refs = it.get("reference", [])
    print("DOI:", it.get("DOI"), "| refs:", len(refs), "| 标题:", (it.get("title") or ["?"])[0][:50])
    if refs:
        print("  样例:", json.dumps(refs[0], ensure_ascii=False)[:300])
