"""
Layer-1 引用真实性核查 benchmark 生成器 v2
- 跨年份（2018-2025）普通期刊论文池，避免会议摘要/未来年份占比过高
- 三类金标准：valid（真实DOI+真实元数据）/ not_found（过去年份、后缀被篡改、已实测404）
  / mismatch（真实DOI+错误元数据：年份/作者标题/期刊，类型均衡）
- 比例约 56% valid / 22% not_found / 22% mismatch
用法：python3 scripts/build_benchmark.py --n 48 --seed 7 --out data/eval/layer1_seed7_n48.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import httpx

CROSSREF = "https://api.crossref.org/works"
HEADERS = {"User-Agent": "SciencePalHackathonBenchmark/1.0 (mailto:research@example.com)"}

# 跨年份、以期刊为主的生物医学 AI 检索（避免只命中 2026 会议摘要）
QUERIES = [
    "machine learning clinical outcome prediction 2022",
    "deep learning medical diagnosis 2021",
    "artificial intelligence risk stratification 2023",
    "neural network patient prognosis 2020",
    "machine learning clinical outcome prediction 2024",
    "deep learning disease classification 2019",
    "AI clinical decision support 2025",
    "machine learning biomarker prediction 2023",
]

ABSTRACT_BAD = re.compile(r"\babstract\b|proceedings|annual meeting|supplement|conference", re.I)


def fetch_papers(client: httpx.Client, per_query: int = 40) -> list[dict]:
    seen, papers = set(), []
    for q in QUERIES:
        items = []
        for attempt in range(3):
            try:
                r = client.get(
                    CROSSREF,
                    params={"query.bibliographic": q, "rows": per_query, "select":
                            "DOI,title,author,container-title,published,issued,type,volume,issue,page,publisher,ISSN"},
                    timeout=30,
                )
                items = r.json().get("message", {}).get("items", [])
                break
            except Exception as e:
                if attempt == 2:
                    print(f"检索失败 {q}: {e}")
                time.sleep(1.5 * (attempt + 1))
        for it in items:
            doi = it.get("DOI", "").lower()
            title = (it.get("title") or [""])[0]
            container = (it.get("container-title") or [""])[0]
            if not doi or not title:
                continue
            if doi in seen:
                continue
            if it.get("type") != "journal-article":
                continue
            if ABSTRACT_BAD.search(title) or ABSTRACT_BAD.search(container):
                continue
            # 必须有至少一个带姓氏的作者，避免 Anon 占位
            if not any(a.get("family") for a in it.get("author", [])):
                continue
            year = year_of(it)
            if year is None or year < 2015 or year > 2025:
                continue
            seen.add(doi)
            papers.append(it)
        time.sleep(0.8)
    return papers


def year_of(it: dict) -> int | None:
    for key in ("issued", "published", "published-print", "published-online"):
        dp = it.get(key, {}).get("date-parts", [[None]])
        if dp and dp[0] and dp[0][0]:
            return int(dp[0][0])
    return None


def cite_authors(it: dict) -> str:
    authors = it.get("author", [])
    names = []
    for a in authors[:4]:
        fam = a.get("family", "")
        given = a.get("given", "")
        ini = "".join(w[0] for w in given.replace(".", " ").split() if w) + "."
        names.append(f"{fam} {ini}".strip())
    if not names:
        return "Anon"
    if len(authors) > 4:
        names.append("et al.")
    return ", ".join(names)


def format_citation(it: dict, doi_override: str | None = None,
                    title_override: str | None = None,
                    year_override: int | None = None,
                    journal_override: str | None = None) -> str:
    title = title_override or (it.get("title") or [""])[0]
    authors = cite_authors(it)
    year = year_override or year_of(it)
    journal = journal_override or (it.get("container-title") or [""])[0]
    vol = it.get("volume", "")
    issue = it.get("issue", "")
    page = it.get("page", "")
    doi = doi_override or it.get("DOI", "")
    parts = [f"{authors} ({year}). {title}."]
    loc = journal
    if vol:
        loc += f", {vol}"
    if issue:
        loc += f", {issue}"
    if page:
        loc += f", {page}"
    loc = loc.strip(", ")
    return f"{''.join(parts)} {loc}. doi: {doi}"


def doi_status(client: httpx.Client, doi: str) -> int:
    try:
        r = client.get(f"{CROSSREF}/{doi}", headers=HEADERS, timeout=20)
        return r.status_code
    except Exception:
        return 0


def make_fake_doi(real_doi: str, rng: random.Random) -> str:
    """同前缀、同格式、同年份，仅篡改后缀数字/字母，使其 404（不引入未来年份）。"""
    cands = []
    # 形如 ...2022.109552 的纯数字尾
    m = re.search(r"(\d{4,})$", real_doi)
    if m:
        seg = m.group(1)
        for _ in range(6):
            newnum = str(int(seg) + rng.randint(4000, 90000))
            cands.append(real_doi[: m.start(1)] + newnum)
    # 通用：在末尾改字母数字
    for _ in range(6):
        suffix = rng.choice(["X999", "X751", "Z042", "Q888"]) + str(rng.randint(10, 99))
        cands.append(real_doi.rstrip(".-/") + "-" + suffix)
    return cands[0] if cands else real_doi + "-X9"


def find_verified_fake(client: httpx.Client, real_doi: str, rng: random.Random) -> str | None:
    for _ in range(10):
        cand = make_fake_doi(real_doi, rng)
        if cand == real_doi:
            continue
        if doi_status(client, cand) == 404:
            return cand
        time.sleep(0.2)
    return None


def mutate_title(title: str, rng: random.Random) -> str:
    """替换标题中的一个核心实词为领域外的词（含义明确改变），不做易被当作良性截断的删词。"""
    words = title.split()
    stop = {"using", "with", "based", "study", "analysis", "between", "clinical",
            "results", "patient", "patients", "learning", "model", "models", "prediction"}
    cand = [i for i, w in enumerate(words)
            if len(w.strip(".,:;?-").lower()) > 5 and w.strip(".,:;?-").lower() not in stop]
    replacements = ["Quantum", "Blockchain", "Nanoparticle", "Metabolomic",
                    "Wearable", "Robotic", "Cryptographic", "Astrophysical"]
    if cand:
        idx = rng.choice(cand)
        words[idx] = rng.choice(replacements)
    else:
        words.append(rng.choice(replacements))
    return " ".join(words)


def mutate_author(it: dict) -> str:
    authors = it.get("author", [])
    if len(authors) >= 2:
        authors = authors[1:] + authors[:1]
    dummy = dict(it)
    dummy["author"] = authors
    return cite_authors(dummy)


def build(n: int, seed: int) -> dict:
    rng = random.Random(seed)
    with httpx.Client(headers=HEADERS) as client:
        pool = fetch_papers(client)
        print(f"真实论文池（普通期刊，2015-2025）: {len(pool)} 篇")
        if len(pool) < n:
            raise RuntimeError(f"论文池不足：{len(pool)} < {n}")
        rng.shuffle(pool)

        n_not_found = round(n * 0.22)
        n_mismatch = round(n * 0.22)
        n_valid = n - n_not_found - n_mismatch

        # not_found 源：优先 DOI 尾部为纯数字、便于同格式篡改的（Elsevier 风格）
        nf_candidates = [it for it in pool if re.search(r"\d{4,}$", it["DOI"].lower())]
        rng.shuffle(nf_candidates)
        # mismatch 源：作者数>=2 的普通期刊
        mm_candidates = [it for it in pool if len(it.get("author", [])) >= 2]
        rng.shuffle(mm_candidates)

        items = []
        used = set()
        iid = 0

        # 1) not_found
        nf = 0
        for it in nf_candidates:
            if nf >= n_not_found:
                break
            if it["DOI"] in used:
                continue
            fake = find_verified_fake(client, it["DOI"], rng)
            if not fake:
                continue
            used.add(it["DOI"])
            iid += 1
            cite = format_citation(it, doi_override=fake)
            items.append({
                "item_id": iid, "label": "not_found", "doi": fake,
                "doi_status": "not_found", "metadata_match": False,
                "error_type": "hallucinated_doi", "citation": cite,
                "real_doi": it["DOI"], "year": year_of(it),
            })
            nf += 1
            time.sleep(0.2)

        # 2) mismatch
        mm = 0
        mm_types = ["year", "author_title", "journal"]
        for it in mm_candidates:
            if mm >= n_mismatch:
                break
            if it["DOI"] in used:
                continue
            mtype = mm_types[mm % 3]
            kw = {}
            detail = ""
            if mtype == "year":
                real_y = year_of(it)
                new_y = real_y + rng.choice([-3, -2, 2, 3, 4])
                kw["year_override"] = new_y
                detail = f"年份 {real_y}→{new_y}"
            elif mtype == "author_title":
                kw["title_override"] = mutate_title(it["title"][0], rng)
                detail = "标题/作者被改"
            else:
                kw["journal_override"] = "The Journal of Clinical Research Reports"
                detail = "期刊名被改"
            used.add(it["DOI"])
            iid += 1
            cite = format_citation(it, **kw)
            items.append({
                "item_id": iid, "label": "mismatch", "doi": it["DOI"],
                "doi_status": "valid", "metadata_match": False,
                "mismatch_type": mtype, "detail": detail,
                "citation": cite, "real_year": year_of(it),
            })
            mm += 1

        # 3) valid
        vv = 0
        for it in pool:
            if vv >= n_valid:
                break
            if it["DOI"] in used:
                continue
            used.add(it["DOI"])
            iid += 1
            items.append({
                "item_id": iid, "label": "valid", "doi": it["DOI"],
                "doi_status": "valid", "metadata_match": True,
                "citation": format_citation(it), "year": year_of(it),
            })
            vv += 1

    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["item_id"] = i
    prompt = (
        "下面是某生物医学论文稿件的参考文献列表。请逐条核查：① 每条的 DOI 是否真实存在"
        "（必须在沙箱中实际联网调用 Crossref，记录 HTTP 状态）；② 题录信息（作者、年份、标题、期刊、卷期页码）"
        "是否与该 DOI 的真实元数据逐字段一致（任一字段不一致即 metadata_match=false）。\n\n"
        + "\n".join(f"[{it['item_id']}] {it['citation']}" for it in items)
        + "\n\n只输出一个 ```json 代码块：{\"references\":[{\"item_id\":1,"
          "\"doi_status\":\"valid|not_found|no_doi\",\"metadata_match\":true,"
          "\"verdict\":\"confirm|suspect|pass\",\"confidence\":0.0,"
          "\"evidence_url\":\"\",\"issue\":\"\"}]}。正常用 pass，DOI 不存在或题录有误用 confirm，不确定用 suspect。"
    )
    from collections import Counter
    print("标签分布:", dict(Counter(it["label"] for it in items)))
    print("mismatch 类型:", dict(Counter(it.get("mismatch_type") for it in items if it["label"] == "mismatch")))
    return {
        "version": "v2", "layer": "layer1_doi_metadata", "seed": seed, "n": len(items),
        "source": "Crossref REST API", "created_for": "SciencePal AI4Science Hackathon 2026",
        "items": items, "prompt": prompt,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    bundle = build(args.n, args.seed)
    out = Path(args.out) if args.out else \
        Path(__file__).resolve().parent.parent / "data" / "eval" / f"layer1_seed{args.seed}_n{args.n}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已写入:", out)


if __name__ == "__main__":
    main()
