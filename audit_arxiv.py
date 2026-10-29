"""Step 1 审计（arXiv 域）：arXiv(源，作者自提交) vs DBLP(金标准，人工维护) author/year 分歧率。

- 数据：本地 dblp.xml.gz（DBLP 静态 dump，绕过 Anubis 反爬；搜索 API 已被 Anubis 挡）。
- 采样：流式解析 dump，蓄水池抽样 N 条带 arXiv ee 链接的 inproceedings/article。
- 比对：author（DBLP 人工维护 vs arXiv 自提交，姓名归一化后集合比对）、year（DBLP 出版年 vs arXiv 提交年）。
- 输出 data/audit_arxiv/pilot_*.json
"""

import gzip
import html
import json
import math
import os
import random
import re
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "metadatarag-research/0.1 (mailto:research@example.com)"}
ARXIV = "https://export.arxiv.org/api/query"
ROOT = os.path.dirname(os.path.abspath(__file__))
DBLP_GZ = os.path.join(ROOT, "data", "dblp", "dblp.xml.gz")
OUT_DIR = os.path.join(ROOT, "data", "audit_arxiv")

N_SAMPLE = 200
SEED = 42

BLOCK_RE = re.compile(r"<(inproceedings|article)\b([^>]*)>(.*?)</\1>", re.S)


def extract_arxiv_id(body):
    """DBLP 存 arXiv 链接有三种形式：
    - arxiv.org/abs/cs/0011010   （老式，archive 前缀）
    - arxiv.org/abs/1803.10319   （新式）
    - 10.48550/arXiv.1803.10319  （新式 DOI 形式）
    """
    m = re.search(r"arxiv\.org/abs/([\w./\-]+)", body)
    if m:
        return re.sub(r"v\d+$", "", m.group(1)).rstrip(".")
    m = re.search(r"10\.48550/arXiv\.(\d{4}\.\d{4,5})", body)
    if m:
        return m.group(1)
    return None


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def parse_block(typ, attrs, body):
    key = re.search(r'key="([^"]*)"', attrs)
    title = re.search(r"<title>(.*?)</title>", body, re.S)
    authors = re.findall(r"<author>(.*?)</author>", body, re.S)
    year = re.search(r"<year>(\d{4})</year>", body)
    venue = re.search(r"<(?:booktitle|journal)>(.*?)</(?:booktitle|journal)>", body, re.S)
    arx = extract_arxiv_id(body)
    return {
        "type": typ,
        "key": key.group(1) if key else "",
        "title": title.group(1).strip() if title else "",
        "authors": [a.strip() for a in authors],
        "year": int(year.group(1)) if year else None,
        "venue": venue.group(1).strip() if venue else "",
        "arxiv_id": arx,
    }


def reservoir_sample(n, seed=42):
    rng = random.Random(seed)
    sample = []
    seen = 0
    buf = ""
    with gzip.open(DBLP_GZ, "rt", encoding="utf-8", errors="replace") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), ""):
            buf += chunk
            # process complete blocks
            pos = 0
            while True:
                m = BLOCK_RE.search(buf, pos)
                if not m:
                    buf = buf[pos:]
                    break
                rec = parse_block(m.group(1), m.group(2), m.group(3))
                pos = m.end()
                if rec["arxiv_id"] is None:
                    continue
                if rec["key"].startswith("journals/corr/"):
                    continue  # skip CoRR preprints，只看正式发表条目
                seen += 1
                if len(sample) < n:
                    sample.append(rec)
                else:
                    j = rng.randint(0, seen - 1)
                    if j < n:
                        sample[j] = rec
            # keep a tail buffer to avoid splitting a block
            if len(buf) > 1_000_000:
                buf = buf[-100_000:]
    print(f"reservoir: seen {seen} arXiv-linked records, sampled {len(sample)}")
    return sample


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def norm_name(s):
    s = html.unescape(s or "")                 # 解码 HTML 实体（&uuml; -> ü）
    s = re.sub(r"\s+\d{4}$", "", s.strip())     # 剥 DBLP 消歧后缀（"Chen 0001" -> "Chen"）
    s = re.sub(r"[^\w\s]", "", s)               # 去标点（"T.-H." -> "T H"）
    return " ".join(s.split()).lower()


def compare_authors(dblp_names, arxiv_names):
    d = {norm_name(x) for x in dblp_names}
    a = {norm_name(x) for x in arxiv_names}
    if not d and not a:
        return "both_missing"
    if not d:
        return "dblp_missing"
    if not a:
        return "arxiv_missing"
    if d == a:
        return "match"
    return "diff"


def fetch_arxiv(ids):
    """Batch fetch arXiv metadata by id_list; return {arxiv_id: {authors,title,pub_year}}."""
    out = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        params = {"id_list": ",".join(batch), "max_results": len(batch)}
        for attempt in range(4):
            try:
                r = requests.get(ARXIV, params=params, headers=UA, timeout=60)
                if r.status_code == 200:
                    break
                time.sleep(3 + attempt * 3)
            except requests.exceptions.RequestException:
                time.sleep(3 + attempt * 3)
        else:
            print(f"  [warn] batch fetch failed: {batch[:3]}...")
            continue
        for e in re.findall(r"<entry>(.*?)</entry>", r.text, re.S):
            m = re.search(r"<id>http://arxiv.org/abs/([\w./\-]+?)(?:v\d+)?<", e)
            if not m:
                continue
            aid = m.group(1)
            t = re.search(r"<title>(.*?)</title>", e, re.S)
            names = re.findall(r"<name>(.*?)</name>", e)
            pub = re.search(r"<published>(\d{4})", e)
            out[aid] = {
                "title": t.group(1).strip() if t else "",
                "authors": names,
                "pub_year": int(pub.group(1)) if pub else None,
            }
        time.sleep(3)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("parsing dblp.xml.gz (reservoir sample)...")
    sample = reservoir_sample(N_SAMPLE, SEED)

    with open(os.path.join(OUT_DIR, "pilot_sample.json"), "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"fetching arXiv metadata for {len(sample)} ids...")
    arxiv = fetch_arxiv([r["arxiv_id"] for r in sample])

    rows = []
    for r in sample:
        a = arxiv.get(r["arxiv_id"])
        if a is None:
            continue
        author_status = compare_authors(r["authors"], a["authors"])
        if r["year"] is None:
            year_status = "dblp_missing"
        elif a["pub_year"] is None:
            year_status = "arxiv_missing"
        elif r["year"] == a["pub_year"]:
            year_status = "match"
        else:
            year_status = "diff"
        rows.append({
            "arxiv_id": r["arxiv_id"],
            "dblp_title": r["title"],
            "arxiv_title": a["title"],
            "dblp_authors": r["authors"],
            "arxiv_authors": a["authors"],
            "dblp_year": r["year"],
            "arxiv_year": a["pub_year"],
            "dblp_venue": r["venue"],
            "author_status": author_status,
            "year_status": year_status,
        })

    with open(os.path.join(OUT_DIR, "pilot_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    n = len(rows)

    def rate(pred):
        k = sum(1 for x in rows if pred(x))
        lo, hi = wilson_ci(k, n)
        return {"count": k, "rate": round(k / n, 3) if n else None, "ci95": [round(lo, 3), round(hi, 3)]}

    summary = {
        "n_sampled": len(sample),
        "n_fetched": n,
        "author_match": rate(lambda r: r["author_status"] == "match"),
        "author_diff": rate(lambda r: r["author_status"] == "diff"),
        "author_missing": rate(lambda r: r["author_status"] in ("dblp_missing", "arxiv_missing")),
        "year_match": rate(lambda r: r["year_status"] == "match"),
        "year_diff": rate(lambda r: r["year_status"] == "diff"),
        "year_missing": rate(lambda r: r["year_status"] in ("dblp_missing", "arxiv_missing")),
    }
    with open(os.path.join(OUT_DIR, "pilot_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== PILOT SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n=== author diff 样例 ===")
    for r in rows:
        if r["author_status"] == "diff":
            print(f"  {r['dblp_title'][:40]:42} DBLP={r['dblp_authors'][:4]}  arXiv={r['arxiv_authors'][:4]}")
    print("\n=== year diff 样例 ===")
    for r in rows:
        if r["year_status"] == "diff":
            print(f"  {r['dblp_title'][:40]:42} DBLP={r['dblp_year']}  arXiv={r['arxiv_year']}")


if __name__ == "__main__":
    main()
