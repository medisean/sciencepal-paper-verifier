"""核查报告「输出契约」（v1）与零依赖校验器。

设计目的：把"模型自觉遵守 schema"升级为"代码判定是否遵守"。
校验分四类，任一类失败都返回可读错误，供 guardrail 生成定向修复指令：

  S 结构——JSON 可解析、必填字段齐全、类型正确、枚举合法、confidence ∈ [0,1]
  C 覆盖——references 必须覆盖输入全部条目（item_id 恰好等于 1..N，不多不少）
  E 证据——doi_status 为 valid/not_found 时必须给出 evidence_url（禁止无证据放行/判错）
  V 判定——verdict 与 doi_status/metadata_match 自洽（不一致即视为契约冲突）

只依赖标准库，便于评审与复现。
"""
from __future__ import annotations

from typing import Any

DOI_STATUS = ("valid", "not_found", "no_doi")
VERDICT = ("confirm", "suspect", "pass")
CLAIM_SUPPORT = ("support", "related", "no_evidence", "inaccessible")
RISK = ("high", "medium", "low")

REF_REQUIRED = {
    "item_id": int,
    "doi_status": str,
    "metadata_match": bool,
    "verdict": str,
    "confidence": (int, float),
    "evidence_url": str,
}
TASK_REQUIRED = {"id": str, "check": str, "verdict": str}


def _typename(v: Any) -> str:
    return type(v).__name__


EVIDENCE_HOSTS = ("api.crossref.org", "doi.org", "dx.doi.org", "api.openalex.org",
                  "eutils.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov")


def _host(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def validate(payload: Any, expect_items: int | None = None,
             expect_dois: dict[int, str] | None = None) -> list[str]:
    """返回错误列表；空列表表示完全合规。

    expect_dois 给出时，额外校验"证据 URL 的指向性"：
      E3 —— evidence_url 必须包含该条目的 DOI（否则是"贴了个链接但没指向这条"）
      E4 —— evidence_url 的域名必须在权威来源白名单内
    """
    errs: list[str] = []
    if not isinstance(payload, dict):
        return [f"S: 顶层必须是 JSON 对象，实际是 {_typename(payload)}"]

    refs = payload.get("references")
    if not isinstance(refs, list):
        errs.append(f"S: references 必须是数组，实际是 {_typename(refs)}")
        refs = []

    seen: list[int] = []
    for i, r in enumerate(refs):
        where = f"references[{i}]"
        if not isinstance(r, dict):
            errs.append(f"S: {where} 必须是对象，实际是 {_typename(r)}")
            continue
        for field, typ in REF_REQUIRED.items():
            if field not in r:
                errs.append(f"S: {where} 缺少必填字段 {field}")
            elif not isinstance(r[field], typ) or (isinstance(r[field], bool) and typ is not bool):
                errs.append(f"S: {where}.{field} 类型错误（期望 {typ}，实际 {_typename(r[field])}）")
        ds = r.get("doi_status")
        if isinstance(ds, str) and ds not in DOI_STATUS:
            errs.append(f"S: {where}.doi_status='{ds}' 不在枚举 {DOI_STATUS} 内")
        vd = r.get("verdict")
        if isinstance(vd, str) and vd not in VERDICT:
            errs.append(f"S: {where}.verdict='{vd}' 不在枚举 {VERDICT} 内")
        cs = r.get("claim_support")
        if cs is not None and isinstance(cs, str) and cs not in CLAIM_SUPPORT:
            errs.append(f"S: {where}.claim_support='{cs}' 不在枚举 {CLAIM_SUPPORT} 内")
        conf = r.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            if not 0.0 <= float(conf) <= 1.0:
                errs.append(f"S: {where}.confidence={conf} 超出 [0,1]")
        try:
            seen.append(int(r.get("item_id")))
        except (TypeError, ValueError):
            errs.append(f"S: {where}.item_id 不是整数")

        # E 证据
        if ds in ("valid", "not_found"):
            url = r.get("evidence_url")
            if not isinstance(url, str) or not url.strip():
                errs.append(
                    f"E: {where}(item_id={r.get('item_id')}) doi_status={ds} 但没有 evidence_url，"
                    f"属于无证据结论"
                )

        # E3/E4 证据指向性（需要金标准 DOI）
        if expect_dois and r.get("item_id") in expect_dois and ds in ("valid", "not_found"):
            want = str(expect_dois[r["item_id"]]).lower()
            url = r.get("evidence_url") or ""
            if not url.strip():
                pass                       # 空 URL 已由 E 报告，不重复计为 E3
            elif want and want not in url.lower():
                errs.append(f"E3: {where}(item_id={r.get('item_id')}) evidence_url 未包含该条 DOI {want}")
            host = _host(url)
            if url.strip() and host and host not in EVIDENCE_HOSTS:
                errs.append(f"E4: {where} evidence_url 域名 {host} 不在权威来源白名单")

        # V 判定自洽
        mm = r.get("metadata_match")
        if ds == "not_found" and mm is True:
            errs.append(f"V: {where} doi_status=not_found 却 metadata_match=true，自相矛盾")
        if mm is False and vd == "pass":
            errs.append(f"V: {where} metadata_match=false 却 verdict=pass，自相矛盾")

    # C 覆盖
    if expect_items is not None:
        missing = sorted(set(range(1, expect_items + 1)) - set(seen))
        extra = sorted(set(seen) - set(range(1, expect_items + 1)))
        dup = sorted({x for x in seen if seen.count(x) > 1})
        if missing:
            errs.append(f"C: 缺少条目 item_id={missing}（必须覆盖 1..{expect_items} 全部）")
        if extra:
            errs.append(f"C: 出现越界条目 item_id={extra}（输入只有 1..{expect_items}）")
        if dup:
            errs.append(f"C: 条目重复 item_id={dup}")

    # 其余字段
    if "overall_risk" in payload and payload["overall_risk"] not in RISK:
        errs.append(f"S: overall_risk='{payload['overall_risk']}' 不在枚举 {RISK} 内")
    tasks = payload.get("methodology")
    if tasks is not None:
        if not isinstance(tasks, list):
            errs.append(f"S: methodology 必须是数组，实际是 {_typename(tasks)}")
        else:
            for i, t in enumerate(tasks):
                if not isinstance(t, dict):
                    errs.append(f"S: methodology[{i}] 必须是对象")
                    continue
                for field in TASK_REQUIRED:
                    if field not in t:
                        errs.append(f"S: methodology[{i}] 缺少字段 {field}")
                if isinstance(t.get("verdict"), str) and t["verdict"] not in VERDICT:
                    errs.append(f"S: methodology[{i}].verdict 不在枚举 {VERDICT} 内")
    return errs


def summarize(errs: list[str]) -> dict[str, int]:
    """按 S/C/E/V 四类归类计数。"""
    out = {"S": 0, "C": 0, "E": 0, "V": 0}
    for e in errs:
        k = e.split(":", 1)[0].strip()
        if not k:
            continue
        root = k[0]                      # E3/E4 归入 E，便于按类汇总
        if root in out:
            out[root] += 1
    return out


SCHEMA_HINT = (
    '{"references":[{"item_id":1,"raw_citation":"","doi":"","doi_status":"valid|not_found|no_doi",'
    '"metadata_match":true,"claim_support":"support|related|no_evidence|inaccessible",'
    '"verdict":"confirm|suspect|pass","confidence":0.0,"evidence_url":"","issue":""}],'
    '"methodology":[{"id":"M1-1","location":"","check":"M1","description":"","evidence":"",'
    '"verdict":"confirm|suspect|pass","confidence":0.0}],"overall_risk":"high|medium|low","top_issues":[]}'
)


def repair_instruction(errs: list[str], expect_items: int | None) -> str:
    """把校验错误转成给模型的定向修复指令（不改任务，只修格式/契约）。"""
    head = "【输出契约校验失败】你上一条回复的 JSON 未通过自动校验，错误如下："
    body = "\n".join(f"{i+1}) {e}" for i, e in enumerate(errs[:12]))
    tail = (
        "\n请立即修正：只重新输出一个 ```json 代码块，内容为完整报告 JSON（不是补丁），"
        "字段与枚举严格按下述 schema，不要重复核查过程、不要解释。\n" + SCHEMA_HINT
    )
    if expect_items:
        tail += (
            f"\nreferences 必须恰好 {expect_items} 条、item_id 依次为 1..{expect_items}；"
            "doi_status 为 valid 或 not_found 的条目必须填 evidence_url。"
        )
    return head + "\n" + body + tail


JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SciencePal 论文核查报告 v1",
    "type": "object",
    "required": ["references"],
    "properties": {
        "references": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "required": ["item_id", "doi_status", "metadata_match", "verdict",
                             "confidence", "evidence_url"],
                "properties": {
                    "item_id": {"type": "integer", "minimum": 1},
                    "raw_citation": {"type": "string"},
                    "doi": {"type": "string"},
                    "doi_status": {"enum": list(DOI_STATUS)},
                    "metadata_match": {"type": "boolean"},
                    "claim_support": {"enum": list(CLAIM_SUPPORT)},
                    "verdict": {"enum": list(VERDICT)},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_url": {"type": "string"},
                    "issue": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
        "methodology": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "check", "verdict"],
                "properties": {
                    "id": {"type": "string"}, "location": {"type": "string"},
                    "check": {"type": "string"}, "description": {"type": "string"},
                    "evidence": {"type": "string"}, "verdict": {"enum": list(VERDICT)},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "overall_risk": {"enum": list(RISK)},
        "top_issues": {"type": "array", "items": {"type": "string"}},
    },
}


def emit_schema(path) -> None:
    import json
    from pathlib import Path
    Path(path).write_text(json.dumps(JSON_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if "--emit-schema" in sys.argv:
        out = sys.argv[sys.argv.index("--emit-schema") + 1]
        emit_schema(out)
        print("schema written:", out)
    else:
        print(__doc__)
