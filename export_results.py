"""导出 Step 1 审计结果到 Excel。

命名约定：step1_audit_{领域}_{错误来源机制}.xlsx
- 领域: scholarly(科研) / medical(医疗) / news(新闻) / legal(法律) ...
- 机制: aggregation(聚合/消歧) / ocr / llm / manual ...

本审计 = scholarly + aggregation（OpenAlex vs Crossref）。
"""

import json
import math
import os

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(ROOT, "data", "audit")
OUT_DIR = os.path.join(ROOT, "results")

# 本审计的领域与错误来源机制（决定文件名）
DOMAIN = "scholarly"
MECHANISM = "aggregation"
OUT = os.path.join(OUT_DIR, f"step1_audit_{DOMAIN}_{MECHANISM}.xlsx")


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(AUDIT, "audit_summary.json"), encoding="utf-8") as f:
        summ = json.load(f)
    with open(os.path.join(AUDIT, "audit_analysis.json"), encoding="utf-8") as f:
        rows = json.load(f)
    n = summ["n_joined"]

    # ---- Sheet 1: 审计信息 ----
    info = [
        ["领域", "科研/学术文献 (scholarly)"],
        ["错误来源机制", "聚合/消歧 (aggregation/disambiguation)，属「人工录入/迁移」类"],
        ["待审计源", "OpenAlex"],
        ["金标准", "Crossref"],
        ["采样", "分层随机 n=1000（5 个出版年份层 × 200）"],
        ["join 成功", n],
        ["日期", "2026-10-14"],
    ]
    df_info = pd.DataFrame(info, columns=["属性", "值"])

    # ---- Sheet 2: 三层结果 ----
    spec = {
        "venue": {"raw": 0.100, "raw_ci": (0.0824, 0.1208), "key": "venue_error", "true": 1},
        "author": {"raw": 0.0681, "raw_ci": (0.0537, 0.0860), "key": "author_error_strict", "true": 3},
        "year": {"raw": 0.0011, "raw_ci": (0.0002, 0.0060), "key": "year_error", "true": 1},
    }
    rec = []
    for fld, sp in spec.items():
        rec.append([fld, "① 原始字符串差异", round(sp["raw"] * 100, 2),
                    round(sp["raw_ci"][0] * 100, 2), round(sp["raw_ci"][1] * 100, 2), None, n])
        nr = summ[sp["key"]]
        rec.append([fld, "② 归一化后候选", round(nr["rate"] * 100, 2),
                    round(nr["ci95"][0] * 100, 2), round(nr["ci95"][1] * 100, 2), nr["count"], n])
        lo, hi = wilson_ci(sp["true"], n)
        rec.append([fld, "③ 人工裁决真错误", round(sp["true"] / n * 100, 3),
                    round(lo * 100, 3), round(hi * 100, 3), sp["true"], n])
    df3 = pd.DataFrame(rec, columns=["字段", "层", "错误率(%)", "CI下界(%)", "CI上界(%)", "count", "n"])

    # ---- Sheet 3: 真错误 vs 表示不一致 ----
    # 真错误值=指向错误实体；表示不一致=同一实体不同写法（改名/异写/转写/姓名序/子系列/online-print年份）
    # 计数来自人工裁决（见 CLAUDE.md）；venue 表示不一致含 40 改名异写 + 31 子系列
    decomp = {
        "venue": {"true": 1, "rep": 71},
        "author": {"true": 3, "rep": 41},
        "year": {"true": 1, "rep": 30},
    }
    drec = []
    for fld, d in decomp.items():
        drec.append([fld, d["true"], round(d["true"] / n * 100, 3),
                     d["rep"], round(d["rep"] / n * 100, 2), n])
    df_decomp = pd.DataFrame(drec, columns=["字段", "真错误count", "真错误率(%)",
                                            "表示不一致count", "表示不一致率(%)", "n"])
    note = pd.DataFrame([["说明", "真错误值=指向错误实体（低频）；表示不一致=同一实体不同写法（改名/转写/姓名序/子系列/online-print年份，高频）。venue 另含约 0.4% 的 Crossref错/歧义未单列。"]],
                        columns=["说明", "内容"])
    df_decomp_note = pd.concat([df_decomp, note], ignore_index=True)

    # ---- Sheet 4: 分层结果 ----
    df2 = pd.DataFrame(summ["per_bin"]).T.reset_index().rename(columns={"index": "年份层"})
    order = ["年份层", "n", "venue_error", "author_error_strict", "author_error_broad", "year_error"]
    df2 = df2[[c for c in order if c in df2.columns]]
    for c in ["venue_error", "author_error_strict", "author_error_broad", "year_error"]:
        df2[c] = (df2[c] * 100).round(2)
    df2.columns = ["年份层", "n", "venue候选错误率(%)", "author候选(严格,%)", "author候选(宽,%)", "year错误率(%)"]

    # ---- Sheet 5: 裁决明细（89 条候选，留空列供人工批注/IAA）----
    adj = []
    for r in rows:
        if r["venue"] == "diff":
            adj.append(["venue", r["doi"], r["title"], r["oa_venue"], r["cr_venue"]])
    for r in rows:
        if r["author"] == "diff":
            adj.append(["author", r["doi"], r["title"],
                        "; ".join(r["unmatched_oa_authors"]), "; ".join(r["unmatched_cr_authors"])])
    df_adj = pd.DataFrame(adj, columns=["字段", "DOI", "标题", "OpenAlex", "Crossref"])
    df_adj.insert(5, "裁决(留空待批注)", "")

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        df_info.to_excel(xw, sheet_name="审计信息", index=False)
        df3.to_excel(xw, sheet_name="三层结果", index=False)
        df_decomp_note.to_excel(xw, sheet_name="真错误vs表示不一致", index=False)
        df2.to_excel(xw, sheet_name="分层结果", index=False)
        df_adj.to_excel(xw, sheet_name="裁决明细", index=False)

    print(f"written: {OUT}")
    print(f"sheets: 审计信息 / 三层结果({len(df3)}) / 真错误vs表示不一致({len(df_decomp)}) / 分层结果({len(df2)}) / 裁决明细({len(df_adj)})")


if __name__ == "__main__":
    main()
