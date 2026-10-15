"""Step 1 冒烟测试：OpenAlex(源) vs Crossref(金标准) 三字段对拍。

拉 100 条期刊论文，逐条对拍 author / venue / year，算不一致率。
注意：不一致 != 错误（OpenAlex 是聚合+消歧库，可能纠正也可能引入错），仅作下界代理。
"""

import json
import os
import sys
import time

import requests

# Windows 控制台默认 GBK，打印含变音符号的作者名会崩；强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAILTO = "research@example.com"  # TODO 换成真实邮箱以获得礼貌池更高限额
UA = {"User-Agent": "metadatarag-research/0.1 (mailto:%s)" % MAILTO}

OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")


def norm(s):
    return " ".join(str(s or "").lower().strip().split())


def norm_set(lst):
    return set(norm(x) for x in lst if str(x).strip())


def safe_doi(doi):
    return doi.replace("/", "_").replace("\\", "_")


def fetch_crossref(doi):
    for attempt in range(2):
        try:
            r = requests.get(
                f"{CROSSREF_URL}/{doi}", params={"mailto": MAILTO}, headers=UA, timeout=30
            )
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            time.sleep(1)
        except Exception as e:  # 网络抖动，重试
            print(f"    [warn] crossref {doi}: {e}")
            time.sleep(1)
    return None


def main():
    os.makedirs(os.path.join(DATA_DIR, "crossref"), exist_ok=True)

    # 1) OpenAlex 拉 100 条期刊论文
    params = {"filter": "has_doi:true,type:article", "per-page": 100, "mailto": MAILTO}
    r = requests.get(OPENALEX_URL, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    works = r.json().get("results", [])
    print(f"OpenAlex 返回 {len(works)} 条")

    with open(os.path.join(DATA_DIR, "openalex_sample.json"), "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)

    # 2) 逐条对拍 Crossref
    rows, join_ok = [], 0
    for i, w in enumerate(works):
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        oa_authors = sorted(
            (a.get("author") or {}).get("display_name") or "" for a in w.get("authorships", [])
        )
        src = (w.get("primary_location") or {}).get("source") or {}
        oa_venue = src.get("display_name") or ""
        oa_year = w.get("publication_year")

        cr = fetch_crossref(doi) if doi else None
        if cr is None:
            rows.append({"doi": doi, "title": w.get("title"), "joined": False})
        else:
            join_ok += 1
            msg = cr.get("message", {})
            cr_authors = sorted(
                " ".join(((a.get("given") or "") + " " + (a.get("family") or "")).split())
                for a in msg.get("author", [])
            )
            cr_venue = ""
            if msg.get("container-title"):
                cr_venue = msg["container-title"][0]
            cr_year = None
            try:
                cr_year = msg["issued"]["date-parts"][0][0]
            except Exception:
                pass
            rows.append({
                "doi": doi, "title": w.get("title"),
                "oa_venue": oa_venue, "oa_year": oa_year, "oa_authors": oa_authors,
                "cr_venue": cr_venue, "cr_year": cr_year, "cr_authors": cr_authors,
                "joined": True,
            })
            with open(os.path.join(DATA_DIR, "crossref", safe_doi(doi) + ".json"), "w", encoding="utf-8") as f:
                json.dump(cr, f, ensure_ascii=False, indent=2)

        if (i + 1) % 20 == 0:
            print(f"  进度 {i + 1}/{len(works)}")
        time.sleep(0.2)  # 礼貌节流

    # 3) 不一致率
    joined = [r for r in rows if r["joined"]]
    n = len(joined)

    def venue_d(r):
        return norm(r["oa_venue"]) != norm(r["cr_venue"])

    def year_d(r):
        return (r["oa_year"] is not None and r["cr_year"] is not None
                and int(r["oa_year"]) != int(r["cr_year"]))

    def author_d(r):
        return norm_set(r["oa_authors"]) != norm_set(r["cr_authors"])

    vd = sum(1 for r in joined if venue_d(r))
    yd = sum(1 for r in joined if year_d(r))
    ad = sum(1 for r in joined if author_d(r))

    summary = {
        "n_openalex": len(works),
        "n_joined_crossref": n,
        "join_rate": round(n / len(works), 3) if works else 0,
        "venue_disagreement": {"count": vd, "rate": round(vd / n, 3) if n else None},
        "year_disagreement": {"count": yd, "rate": round(yd / n, 3) if n else None},
        "author_disagreement": {"count": ad, "rate": round(ad / n, 3) if n else None},
    }
    with open(os.path.join(DATA_DIR, "comparison_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n=== VENUE 不一致样例 ===")
    for r in joined:
        if venue_d(r):
            print(f"- {str(r['title'])[:60]} | OA: {r['oa_venue']} | CR: {r['cr_venue']}")

    print("\n=== YEAR 不一致样例 ===")
    for r in joined:
        if year_d(r):
            print(f"- {str(r['title'])[:60]} | OA: {r['oa_year']} | CR: {r['cr_year']}")

    print("\n=== AUTHOR 不一致样例(前5) ===")
    c = 0
    for r in joined:
        if author_d(r):
            print(f"- {str(r['title'])[:60]}")
            print(f"    OA: {r['oa_authors'][:5]}")
            print(f"    CR: {r['cr_authors'][:5]}")
            c += 1
            if c >= 5:
                break

    print(f"\nDone. 文件写入 {DATA_DIR}")


if __name__ == "__main__":
    main()
