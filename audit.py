"""Step 1 正式审计：分层随机 n=1000，OpenAlex(源) vs Crossref(金标准) 三字段错误率。

- 分层：5 个出版年份层 × 200 随机样本（OpenAlex `sample` 参数）。
- 复用 analyze_disagreement 的分类函数（归一化 + 匹配）。
- 错误率带 Wilson 95% CI，并按层给出字段级错误率。
- 断点续传：crossref/ 已存在的 DOI 跳过；网络失败不落盘、下次重试。
输出 data/audit/audit_summary.json 与 data/audit/audit_analysis.json。
"""

import json
import math
import os
import re
import sys
import time

import requests

import analyze_disagreement as lib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAILTO = "research@example.com"  # TODO 换成真实邮箱
UA = {"User-Agent": "metadatarag-research/0.1 (mailto:%s)" % MAILTO}
OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIT_DIR = os.path.join(ROOT, "data", "audit")
CROSSREF_DIR = os.path.join(AUDIT_DIR, "crossref")

BINS = [
    ("pre-1990", "", "1989-12-31"),
    ("1990-1999", "1990-01-01", "1999-12-31"),
    ("2000-2009", "2000-01-01", "2009-12-31"),
    ("2010-2019", "2010-01-01", "2019-12-31"),
    ("2020+", "2020-01-01", ""),
]
SAMPLE_PER_BIN = 200


def safe_doi(doi):
    return re.sub(r'[<>:"/\\|?*]', "_", doi)


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pull_openalex():
    os.makedirs(CROSSREF_DIR, exist_ok=True)
    sample_path = os.path.join(AUDIT_DIR, "openalex_audit.json")
    if os.path.exists(sample_path):
        with open(sample_path, encoding="utf-8") as f:
            works = json.load(f)
        print(f"reuse existing sample: {len(works)} works")
        return works
    works = []
    for label, frm, to in BINS:
        filters = ["has_doi:true", "type:article"]
        if frm:
            filters.append(f"from_publication_date:{frm}")
        if to:
            filters.append(f"to_publication_date:{to}")
        params = {"filter": ",".join(filters), "sample": SAMPLE_PER_BIN, "per-page": SAMPLE_PER_BIN, "mailto": MAILTO}
        r = requests.get(OPENALEX_URL, params=params, headers=UA, timeout=60)
        r.raise_for_status()
        res = r.json().get("results", [])
        for w in res:
            w["_bin"] = label
        works.extend(res)
        print(f"bin {label}: got {len(res)}")
        time.sleep(0.3)

    seen = {}
    for w in works:
        doi = (w.get("doi") or "").lower()
        if doi and doi not in seen:
            seen[doi] = w
    works = list(seen.values())

    with open(os.path.join(AUDIT_DIR, "openalex_audit.json"), "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)
    print(f"total unique works: {len(works)}")
    return works


def fetch_crossref(doi):
    for attempt in range(3):
        try:
            r = requests.get(f"{CROSSREF_URL}/{doi}", params={"mailto": MAILTO}, headers=UA, timeout=30)
            if r.status_code == 200:
                return "ok", r.json()
            if r.status_code == 404:
                return "notfound", None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return "error", None


def fetch_all(works):
    ok = nf = err = skip = 0
    for i, w in enumerate(works):
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        path = os.path.join(CROSSREF_DIR, safe_doi(doi) + ".json")
        if os.path.exists(path):
            skip += 1
        else:
            status, data = fetch_crossref(doi)
            if status == "ok":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                ok += 1
            elif status == "notfound":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"status": "notfound"}, f)
                nf += 1
            else:
                err += 1
            time.sleep(0.12)
        if (i + 1) % 100 == 0:
            print(f"  fetch {i + 1}/{len(works)}  (ok={ok} nf={nf} err={err} skip={skip})")
    print(f"fetch done: ok={ok} notfound={nf} error={err} skip={skip}")
    return ok, nf, err


def extract_cr_authors(msg):
    out = []
    for a in msg.get("author", []):
        given = a.get("given") or ""
        family = a.get("family") or ""
        if given or family:
            out.append(" ".join((given + " " + family).split()))
        elif a.get("name"):
            out.append(a["name"])
    return out


def analyze(works):
    rows = []
    for w in works:
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        path = os.path.join(CROSSREF_DIR, safe_doi(doi) + ".json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            cr = json.load(f)
        if cr.get("status") == "notfound":
            continue
        msg = cr.get("message", {})
        oa_authors = [
            (a.get("author") or {}).get("display_name") or ""
            for a in w.get("authorships", [])
        ]
        cr_authors = extract_cr_authors(msg)
        oa_venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        cr_venue = (msg.get("container-title") or [""])[0] if msg.get("container-title") else ""
        oa_year = w.get("publication_year")

        a_bucket, uoa, ucr, oa_grp, cr_grp = lib.classify_author(oa_authors, cr_authors)
        rows.append({
            "doi": doi, "_bin": w.get("_bin"),
            "title": (w.get("title") or "")[:80],
            "venue": lib.classify_venue(oa_venue, cr_venue),
            "author": a_bucket,
            "year": lib.classify_year(oa_year, lib.cr_years(msg)),
            "oa_venue": oa_venue, "cr_venue": cr_venue,
            "unmatched_oa_authors": uoa, "unmatched_cr_authors": ucr,
            "oa_year": oa_year, "cr_years": sorted(lib.cr_years(msg)),
        })
    return rows


def summarize(rows):
    n = len(rows)

    def bucket_rate(pred):
        k = sum(1 for r in rows if pred(r))
        lo, hi = wilson_ci(k, n)
        return {"count": k, "rate": round(k / n, 4) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}

    summary = {
        "n_joined": n,
        "venue_error": bucket_rate(lambda r: r["venue"] == "diff"),
        "venue_subseries_variant": bucket_rate(lambda r: r["venue"] == "subseries_hint"),
        "author_error_strict": bucket_rate(lambda r: r["author"] == "diff"),
        "author_error_broad": bucket_rate(lambda r: r["author"] in ("diff", "one_side_missing")),
        "author_missing": bucket_rate(lambda r: r["author"] == "one_side_missing"),
        "year_error": bucket_rate(lambda r: r["year"] == "diff"),
        "year_ambiguous": bucket_rate(lambda r: r["year"] == "ambiguous"),
    }

    per_bin = {}
    for label, _, _ in BINS:
        sub = [r for r in rows if r["_bin"] == label]
        if not sub:
            continue
        m = len(sub)
        per_bin[label] = {
            "n": m,
            "venue_error": round(sum(1 for r in sub if r["venue"] == "diff") / m, 4),
            "author_error_strict": round(sum(1 for r in sub if r["author"] == "diff") / m, 4),
            "author_error_broad": round(sum(1 for r in sub if r["author"] in ("diff", "one_side_missing")) / m, 4),
            "year_error": round(sum(1 for r in sub if r["year"] == "diff") / m, 4),
        }
    summary["per_bin"] = per_bin
    return summary


def main():
    works = pull_openalex()
    fetch_all(works)
    rows = analyze(works)
    summary = summarize(rows)

    with open(os.path.join(AUDIT_DIR, "audit_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(AUDIT_DIR, "audit_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== AUDIT SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
