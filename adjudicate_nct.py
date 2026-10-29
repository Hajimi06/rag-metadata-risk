"""NCT 错链人工裁决：拉取 6 个 mismatch 案例两侧标题/摘要/条件，供人工判断真错链 vs 多试验发表伪影。

对每个 mismatch（NCT X 的 RESULT 引用指向 PMID Y，但 PMID Y 的 DataBankList 列出的是 NCT Z）：
- 拉 NCT X 的 officialTitle/briefTitle/conditions（CT.gov v2 API）
- 拉 PMID Y 的 title/abstract/DataBankList（efetch PubMed XML）
判断：PMID Y 是否真的报告 NCT X 的结果。
输出 data/audit_ct/nct_mismatch_adjudication.json
"""

import json
import os
import re
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "metadatarag-research/0.1"}
CT_URL = "https://clinicaltrials.gov/api/v2/studies"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "data", "audit_ct", "audit_ct2_analysis.json")
OUT = os.path.join(ROOT, "data", "audit_ct", "nct_mismatch_adjudication.json")


def get_retry(url, params=None, retries=6, timeout=40):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            last = e
            wait = 2 + attempt * 2
            print(f"  [retry {attempt + 1}/{retries}] {e.__class__.__name__}, sleep {wait}s")
            time.sleep(wait)
    raise last


def fetch_nct(nct):
    r = get_retry(f"{CT_URL}/{nct}", params={"format": "json"})
    d = r.json()
    ps = d["protocolSection"]
    ident = ps.get("identificationModule", {})
    cond = ps.get("conditionsModule", {}).get("conditions", [])
    return {
        "nct": nct,
        "official_title": ident.get("officialTitle") or "",
        "brief_title": ident.get("briefTitle") or "",
        "conditions": cond,
    }


def fetch_pmid(pmid):
    r = get_retry(EFETCH, params={"db": "pubmed", "id": pmid, "retmode": "xml"})
    xml = r.text
    title = ""
    m = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", xml, re.S)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    abstract = ""
    m = re.search(r"<Abstract>(.*?)</Abstract>", xml, re.S)
    if m:
        abstract = re.sub(r"<[^>]+>", "", m.group(1))
        abstract = re.sub(r"\s+", " ", abstract).strip()
    ncts = re.findall(r"<AccessionNumber>(NCT\d+)</AccessionNumber>", xml)
    return {"pmid": pmid, "title": title, "abstract": abstract, "pubmed_ncts": ncts}


def main():
    with open(SRC, encoding="utf-8") as f:
        rows = json.load(f)
    mismatches = [r for r in rows if r["status"] == "mismatch"]
    print(f"adjudicating {len(mismatches)} mismatch cases")

    out = []
    for i, r in enumerate(mismatches):
        nct, pmid = r["nct"], r["pmid"]
        print(f"\n[{i + 1}/{len(mismatches)}] NCT {nct} -> PMID {pmid} (pubmed said {r['pubmed_ncts']})")
        try:
            ct = fetch_nct(nct)
        except Exception as e:
            print(f"  [warn] NCT fetch failed: {e}")
            ct = {"nct": nct, "official_title": "", "brief_title": "", "conditions": []}
        time.sleep(0.3)
        try:
            pm = fetch_pmid(pmid)
        except Exception as e:
            print(f"  [warn] PMID fetch failed: {e}")
            pm = {"pmid": pmid, "title": "", "abstract": "", "pubmed_ncts": []}
        time.sleep(0.35)
        out.append({**r, "nct_info": ct, "pmid_info": pm})

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n=== side-by-side ===")
    for o in out:
        print(f"\nNCT {o['nct']}: {o['nct_info']['brief_title'] or o['nct_info']['official_title'][:100]}")
        print(f"  cond: {o['nct_info']['conditions'][:3]}")
        print(f"PMID {o['pmid']}: {o['pmid_info']['title'][:120]}")
        print(f"  pubmed_ncts: {o['pmid_info']['pubmed_ncts']}")
        print(f"  abstract: {o['pmid_info']['abstract'][:250]}")
    print(f"\nwritten: {OUT}")


if __name__ == "__main__":
    main()
