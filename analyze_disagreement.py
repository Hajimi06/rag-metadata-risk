"""归一化 + 匹配层（v2）：把「不一致」拆成「格式差」与「候选真错误」。

v2 相对 v1 的作者匹配升级：
1. Unicode 转写归一：NFKD 分解 + 去掉组合符（ü→u 等）+ 西里尔同形字母→拉丁。
2. 首字母子序列匹配：姓相同 + 缩略侧首字母是另一侧首字母的子序列 → 匹配。
3. 组作者识别 + 单侧缺失单列：机构作者单独处理；单侧无作者归「完整性差」非「错」。

输出 data/disagreement_analysis.json 与 data/disagreement_summary.json。
"""

import html
import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "2nd", "3rd", "junior", "senior"}

# 西里尔 → 拉丁 转写（俄语 + 乌克兰语；用于跨文字姓名/机构匹配）
_TRANSLIT = str.maketrans({
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "I", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch",
    "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "Ґ": "G", "Є": "Ie", "І": "I", "Ї": "Yi",
    "ґ": "g", "є": "ie", "і": "i", "ї": "yi",
})

GROUP_KWS = (
    "group", "committee", "association", "federation", "society", "institute",
    "project", "consortium", "collaboration", "team", "center", "board",
    "commission", "organization", "organisation", "university", "department",
    "laboratory", "lab ", "network", "subgroup", "working",
)


def norm_ascii(s):
    s = str(s or "")
    s = html.unescape(s)
    s = s.translate(_TRANSLIT)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def norm_punct(s):
    s = norm_ascii(s).replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def name_tokens(name):
    toks = [t for t in re.split(r"[^a-z0-9]+", norm_ascii(name)) if t]
    return [t for t in toks if t not in SUFFIXES]


def initials(name):
    return "".join(t[0] for t in name_tokens(name))


def surname(name):
    toks = name_tokens(name)
    return toks[-1] if toks else ""


def is_subsequence(a, b):
    it = iter(b)
    return all(ch in it for ch in a)


def names_match(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if sorted(ta) == sorted(tb):
        return True
    sa, sb = surname(a), surname(b)
    if sa and sa == sb:
        ia, ib = initials(a), initials(b)
        if ia == ib:
            return True
        if is_subsequence(ia, ib) or is_subsequence(ib, ia):
            return True
    if SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= 0.85:
        return True
    return False


def is_group_author(name):
    s = str(name or "").strip()
    if not s:
        return False
    if s.endswith("."):
        return True
    low = s.lower()
    return any(kw in low for kw in GROUP_KWS)


def match_author_lists(oa, cr):
    oa = [x for x in oa if str(x).strip()]
    cr = [x for x in cr if str(x).strip()]
    if not oa and not cr:
        return True, [], []
    matched_cr = [False] * len(cr)
    unmatched_oa = []
    for a in oa:
        found = None
        for j, b in enumerate(cr):
            if not matched_cr[j] and names_match(a, b):
                found = j
                break
        if found is None:
            unmatched_oa.append(a)
        else:
            matched_cr[found] = True
    unmatched_cr = [cr[j] for j in range(len(cr)) if not matched_cr[j]]
    return (not unmatched_oa and not unmatched_cr), unmatched_oa, unmatched_cr


def classify_author(oa, cr):
    oa = [x for x in oa if str(x).strip()]
    cr = [x for x in cr if str(x).strip()]
    oa_pers = [x for x in oa if not is_group_author(x)]
    cr_pers = [x for x in cr if not is_group_author(x)]
    oa_grp = [x for x in oa if is_group_author(x)]
    cr_grp = [x for x in cr if is_group_author(x)]

    if not oa_pers and not cr_pers:
        return "match", [], [], oa_grp, cr_grp
    if not oa_pers or not cr_pers:
        return "one_side_missing", oa_pers, cr_pers, oa_grp, cr_grp
    ok, uoa, ucr = match_author_lists(oa_pers, cr_pers)
    return ("match" if ok else "diff"), uoa, ucr, oa_grp, cr_grp


def classify_venue(oa, cr):
    a, b = norm_punct(oa), norm_punct(cr)
    if not a or not b:
        return "missing"
    if a == b:
        return "match"
    ta, tb = a.split(), b.split()
    if (a in b or b in a) and abs(len(ta) - len(tb)) <= 2:
        return "subseries_hint"
    return "diff"


def cr_years(msg):
    ys = set()
    for k in ("issued", "published-print", "published-online"):
        dp = (msg.get(k) or {}).get("date-parts")
        if dp and dp[0] and dp[0][0]:
            try:
                ys.add(int(dp[0][0]))
            except (TypeError, ValueError):
                pass
    return ys


def classify_year(oa_year, cr_ys):
    if oa_year is None:
        return "missing_oa"
    if not cr_ys:
        return "missing_cr"
    if oa_year in cr_ys:
        return "match"
    if any(abs(oa_year - y) <= 1 for y in cr_ys):
        return "ambiguous"
    return "diff"


def main():
    with open(os.path.join(DATA_DIR, "openalex_sample.json"), encoding="utf-8") as f:
        works = json.load(f)

    rows = []
    for w in works:
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        path = os.path.join(DATA_DIR, "crossref", doi.replace("/", "_") + ".json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            msg = json.load(f).get("message", {})

        oa_authors = [
            (a.get("author") or {}).get("display_name") or ""
            for a in w.get("authorships", [])
        ]
        cr_authors = [
            " ".join(((a.get("given") or "") + " " + (a.get("family") or "")).split())
            for a in msg.get("author", [])
        ]
        oa_venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        cr_venue = (msg.get("container-title") or [""])[0] if msg.get("container-title") else ""
        oa_year = w.get("publication_year")

        a_bucket, uoa, ucr, oa_grp, cr_grp = classify_author(oa_authors, cr_authors)
        rows.append({
            "doi": doi,
            "title": (w.get("title") or "")[:80],
            "venue": classify_venue(oa_venue, cr_venue),
            "author": a_bucket,
            "year": classify_year(oa_year, cr_years(msg)),
            "oa_venue": oa_venue, "cr_venue": cr_venue,
            "unmatched_oa_authors": uoa, "unmatched_cr_authors": ucr,
            "oa_group_authors": oa_grp, "cr_group_authors": cr_grp,
            "oa_year": oa_year, "cr_years": sorted(cr_years(msg)),
        })

    n = len(rows)

    def rate(key, val):
        c = sum(1 for r in rows if r[key] == val)
        return {"count": c, "rate": round(c / n, 3) if n else None}

    summary = {
        "n_joined": n,
        "venue": {b: rate("venue", b) for b in ("match", "subseries_hint", "diff", "missing")},
        "author": {b: rate("author", b) for b in ("match", "diff", "one_side_missing")},
        "year": {b: rate("year", b) for b in ("match", "ambiguous", "diff", "missing_oa", "missing_cr")},
    }

    with open(os.path.join(DATA_DIR, "disagreement_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "disagreement_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n=== 候选真错误 / 待审清单 ===")
    c = 0
    for r in rows:
        interesting = (
            r["venue"] in ("diff", "subseries_hint")
            or r["author"] in ("diff", "one_side_missing")
            or r["year"] in ("diff", "ambiguous")
        )
        if not interesting:
            continue
        c += 1
        print(f"\n[{r['doi']}] {r['title']}")
        if r["venue"] in ("diff", "subseries_hint"):
            print(f"  venue[{r['venue']}]: OA={r['oa_venue']} | CR={r['cr_venue']}")
        if r["author"] == "diff":
            print(f"  author[diff]: OA-only={r['unmatched_oa_authors']} | CR-only={r['unmatched_cr_authors']}")
        if r["author"] == "one_side_missing":
            print(f"  author[one_side_missing]: OA-only={r['unmatched_oa_authors']} | CR-only={r['unmatched_cr_authors']}")
        if r["oa_group_authors"] or r["cr_group_authors"]:
            print(f"  group: OA={r['oa_group_authors']} | CR={r['cr_group_authors']}")
        if r["year"] in ("diff", "ambiguous"):
            print(f"  year[{r['year']}]: OA={r['oa_year']} | CR={r['cr_years']}")
    print(f"\n共 {c} 条进入待审/候选集合 (n={n})")


if __name__ == "__main__":
    main()
