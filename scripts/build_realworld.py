"""构造"真实已发表论文的参考文献表"用例：检验模型在真实书目上的误报率。

做法（全部可复现，不依赖人工标注）：
1. 取若干真实论文（有 Crossref 参考文献表的 DOI）；
2. 把每条被引文献"按引用方出版社登记的字段"拼成一条参考文献（就是读者在论文里看到的那一行）；
3. 用被引 DOI 自己的 Crossref 记录做金标准，只把**年份不一致**判为 mismatch（年份无歧义；
   期刊缩写、标题截断等噪声太大，一律不判错）；
4. 输出与 Layer-1 同格式的 bundle，可直接用 run_guardrail_eval.py 跑、用 score_eval 打分。

用途：Layer-1 的 48 条是构造数据，本用例回答"真实书目上会不会乱报"。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import project_root  # noqa: E402

ROOT = project_root()
OUT_DIR = ROOT / "data" / "eval"
H = {"User-Agent": "SciencePalHackathonRealworld/1.0 (mailto:research@example.com)"}
API = "https://api.crossref.org/works/"

# 有参考文献表、且条目较多的真实论文（生物医学 / 临床方向）
SOURCE_DOIS = ["10.3390/jcm13195917", "10.1177/0145721714551992"]


def get(client: httpx.Client, doi: str, tries: int = 3) -> dict | None:
    for i in range(tries):
        try:
            r = client.get(API + doi, headers=H)
            if r.status_code == 200:
                return r.json()["message"]
            if r.status_code == 404:
                return None
        except httpx.HTTPError:
            pass
        time.sleep(1 + i)
    return None


def year_of(m: dict) -> int | None:
    for k in ("issued", "published-print", "published-online"):
        p = (m.get(k) or {}).get("date-parts") or []
        if p and p[0] and p[0][0]:
            return int(p[0][0])
    return None


def citation_of(ref: dict, cited: dict | None) -> str:
    author = ref.get("author") or ref.get("editor") or ""
    year = ref.get("year") or ""
    title = ref.get("article-title") or ref.get("volume-title") or ""
    journal = ref.get("journal-title") or ""
    vol = ref.get("volume") or ""
    page = ref.get("first-page") or ref.get("page") or ""
    doi = ref.get("DOI") or ""
    s = f"{author} ({year}). {title}. {journal}"
    if vol:
        s += f", {vol}"
    if page:
        s += f", {page}"
    s += f". doi: {doi}"
    return " ".join(s.split())


def main() -> None:
    items = []
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for src in SOURCE_DOIS:
            host = get(c, src)
            if not host:
                print("跳过（无记录）:", src)
                continue
            refs = host.get("reference") or []
            print(f"\n源论文 {src}: {len(refs)} 条参考文献")
            kept = 0
            for ref in refs:
                doi = (ref.get("DOI") or "").lower()
                if not doi:
                    continue
                cited = get(c, doi)
                if not cited:
                    continue
                ry, cy = ref.get("year"), year_of(cited)
                if not ry or not cy:
                    continue
                try:
                    mismatch = int(ry) != int(cy)
                except (TypeError, ValueError):
                    continue
                items.append({
                    "item_id": 0, "label": "mismatch" if mismatch else "valid",
                    "doi": doi,
                    "doi_status": "valid",
                    "metadata_match": not mismatch,
                    "citation": citation_of(ref, cited),
                    "year": int(ry),
                    "source": src,
                    "true_year": cy,
                    "mismatch_type": "year" if mismatch else None,
                })
                kept += 1
                time.sleep(0.15)
            print(f"  可核对条目: {kept}")

    for i, it in enumerate(items, 1):
        it["item_id"] = i
    prompt = (
        "下面是一篇真实已发表论文的参考文献列表。请逐条核查：① 每条的 DOI 是否真实存在"
        "（必须在沙箱中实际联网调用 Crossref，记录 HTTP 状态）；② 题录信息（作者、年份、标题、期刊、卷期页码）"
        "是否与该 DOI 的真实元数据逐字段一致（任一字段不一致即 metadata_match=false）。\n\n"
        + "\n".join(f"[{it['item_id']}] {it['citation']}" for it in items)
        + "\n\n只输出一个 ```json 代码块：{\"references\":[{\"item_id\":1,"
          "\"doi_status\":\"valid|not_found|no_doi\",\"metadata_match\":true,"
          "\"verdict\":\"confirm|suspect|pass\",\"confidence\":0.0,"
          "\"evidence_url\":\"\",\"issue\":\"\"}]}。正常用 pass，DOI 不存在或题录有误用 confirm，"
          "不确定用 suspect。注意：期刊名缩写、标题截断属于正常引用习惯，不视为不一致。"
    )
    from collections import Counter
    print("\n标签分布:", dict(Counter(it["label"] for it in items)))
    bundle = {"version": "v1", "layer": "realworld_bibliography", "seed": 0,
              "n": len(items), "source": "Crossref reference lists of published papers",
              "created_for": "SciencePal AI4Science Hackathon 2026",
              "sources": SOURCE_DOIS, "items": items, "prompt": prompt}
    out = OUT_DIR / "realworld_bibliography.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", out.relative_to(ROOT), "| n =", len(items),
          "| mismatch =", sum(1 for it in items if it["label"] == "mismatch"))


if __name__ == "__main__":
    main()
