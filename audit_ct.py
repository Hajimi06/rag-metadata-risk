"""Step 1 审计（临床试验域）：NCT 标识符缺失率 —— 修正版。

修正点（上一版 44% 是伪影）：
1. 只取 type=RESULT 的 reference（试验自己的结果发表，申办方手动链接，真实信号）；
   DERIVED 是「从 PubMed 里的 NCT 反推」的循环链接，BACKGROUND 是背景引用，均不测缺失。
2. efetch 加重试（代理抖动 + 429 退避）。
3. 报告 RESULT-only 的缺失/错链率 + Wilson CI。
"""

import json
import math
import os
import re
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CT_URL = "https://clinicaltrials.gov/api/v2/studies"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
UA = {"User-Agent": "metadatarag-research/0.1"}

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "data", "audit_ct")


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def get_json_retry(url, params, retries=4):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  [warn] fetch retry {attempt + 1} ({url.split('/')[-1]}): {e}")
            time.sleep(1 + attempt)
    raise RuntimeError("unreachable")


def pull_studies_with_refs(n_target, query="diabetes", max_pages=60):
    studies = []
    page_token = None
    for _ in range(max_pages):
        params = {"query.term": query, "pageSize": 100, "format": "json"}
        if page_token:
            params["pageToken"] = page_token
        data = get_json_retry(CT_URL, params)
        for s in data.get("studies", []):
            ps = s["protocolSection"]
            refs = ps.get("referencesModule", {}).get("references", [])
            if refs:
                studies.append(s)
                if len(studies) >= n_target:
                    return studies
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.3)
    return studies


def find_result_ref(refs):
    for ref in refs:
        if ref.get("type") == "RESULT" and ref.get("pmid"):
            return ref
    return None


def check_nct(pmid, nct, retries=4):
    for attempt in range(retries):
        try:
            r = requests.get(EFETCH, params={"db": "pubmed", "id": pmid, "retmode": "xml"},
                             headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue
            r.raise_for_status()
            xml = r.text
            has_ct = "<DataBankName>ClinicalTrials.gov</DataBankName>" in xml
            ncts = re.findall(r"<AccessionNumber>(NCT\d+)</AccessionNumber>", xml)
            return has_ct, ncts
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("unreachable")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    n_target = 1000
    studies = pull_studies_with_refs(n_target)
    print(f"collected {len(studies)} studies with references")

    rows = []
    no_result = 0
    for i, s in enumerate(studies):
        ps = s["protocolSection"]
        nct = ps["identificationModule"]["nctId"]
        refs = ps["referencesModule"]["references"]
        ref = find_result_ref(refs)
        if ref is None:
            no_result += 1
            continue
        pmid = ref["pmid"]
        try:
            has_ct, ncts = check_nct(pmid, nct)
        except Exception as e:
            print(f"  [warn] efetch {pmid} failed after retries: {e}")
            time.sleep(1)
            continue
        status = "match" if (has_ct and nct in ncts) else ("missing" if not has_ct else "mismatch")
        rows.append({"nct": nct, "pmid": pmid, "status": status, "pubmed_ncts": ncts})
        if (i + 1) % 50 == 0:
            print(f"  progress {i + 1}/{len(studies)} (result_refs={len(rows)})")
        time.sleep(0.35)

    with open(os.path.join(OUT_DIR, "audit_ct2_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    n = len(rows)

    def rate(pred):
        k = sum(1 for r in rows if pred(r))
        lo, hi = wilson_ci(k, n)
        return {"count": k, "rate": round(k / n, 3) if n else None, "ci95": [round(lo, 3), round(hi, 3)]}

    summary = {
        "n_studies": len(studies),
        "n_with_result_ref": n,
        "n_no_result_ref": no_result,
        "nct_match": rate(lambda r: r["status"] == "match"),
        "nct_error_mismatch": rate(lambda r: r["status"] == "mismatch"),  # 错误=错链（指向错误试验）
        "nct_missing": rate(lambda r: r["status"] == "missing"),  # 缺失=完整性，非错误
    }
    with open(os.path.join(OUT_DIR, "audit_ct2_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== SUMMARY (RESULT refs only) ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n=== mismatch 样例 ===")
    for r in rows:
        if r["status"] == "mismatch":
            print(f"- {r['nct']} -> {r['pmid']}: pubmed_ncts={r['pubmed_ncts']}")


if __name__ == "__main__":
    main()
