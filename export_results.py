"""导出 Step 1 审计结果到 Excel（三类缺陷框架：错误 / 缺失 / 表示不一致，跨两域）。

sheets：审计信息 / 三类缺陷汇总 / 科研域三层结果 / 科研域分层 / 临床域NCT / 裁决明细
"""

import json
import math
import os

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(ROOT, "data", "audit")
AUDIT_CT = os.path.join(ROOT, "data", "audit_ct")
OUT_DIR = os.path.join(ROOT, "results")
OUT = os.path.join(OUT_DIR, "step1_audit_summary.xlsx")


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

    # ---- 读取两域数据 ----
    with open(os.path.join(AUDIT, "audit_summary.json"), encoding="utf-8") as f:
        summ = json.load(f)
    with open(os.path.join(AUDIT, "audit_analysis.json"), encoding="utf-8") as f:
        rows = json.load(f)
    with open(os.path.join(AUDIT_CT, "audit_ct2_summary.json"), encoding="utf-8") as f:
        csumm = json.load(f)
    n_s = summ["n_joined"]  # 940
    n_c = csumm["n_with_result_ref"]  # 181

    # ---- Sheet 1: 三类缺陷汇总（跨域）----
    # 错误=人工裁决真错误值/错链；缺失=字段缺失；表示不一致=同实体异写
    three = [
        ["科研(OpenAlex)", "venue", 1, 0, 71, n_s],
        ["科研(OpenAlex)", "author", 3, 7, 41, n_s],
        ["科研(OpenAlex)", "year", 1, 0, 30, n_s],
        ["临床(CT.gov)", "NCT", csumm["nct_error_mismatch"]["count"], csumm["nct_missing"]["count"], 0, n_c],
    ]
    df3 = pd.DataFrame(three, columns=["域", "字段", "错误", "缺失", "表示不一致", "n"])
    df3["错误率(%)"] = (df3["错误"] / df3["n"] * 100).round(2)
    df3["缺失率(%)"] = (df3["缺失"] / df3["n"] * 100).round(2)
    df3["表示不一致率(%)"] = (df3["表示不一致"] / df3["n"] * 100).round(2)

    # ---- Sheet 2: 科研域三层结果 ----
    spec = {
        "venue": {"raw": 0.100, "raw_ci": (0.0824, 0.1208), "key": "venue_error", "true": 1},
        "author": {"raw": 0.0681, "raw_ci": (0.0537, 0.0860), "key": "author_error_strict", "true": 3},
        "year": {"raw": 0.0011, "raw_ci": (0.0002, 0.0060), "key": "year_error", "true": 1},
    }
    rec = []
    for fld, sp in spec.items():
        rec.append([fld, "① 原始字符串差异", round(sp["raw"] * 100, 2),
                    round(sp["raw_ci"][0] * 100, 2), round(sp["raw_ci"][1] * 100, 2), None, n_s])
        nr = summ[sp["key"]]
        rec.append([fld, "② 归一化后候选", round(nr["rate"] * 100, 2),
                    round(nr["ci95"][0] * 100, 2), round(nr["ci95"][1] * 100, 2), nr["count"], n_s])
        lo, hi = wilson_ci(sp["true"], n_s)
        rec.append([fld, "③ 人工裁决真错误", round(sp["true"] / n_s * 100, 3),
                    round(lo * 100, 3), round(hi * 100, 3), sp["true"], n_s])
    df_layer = pd.DataFrame(rec, columns=["字段", "层", "错误率(%)", "CI下界(%)", "CI上界(%)", "count", "n"])

    # ---- Sheet 3: 科研域分层 ----
    df_bin = pd.DataFrame(summ["per_bin"]).T.reset_index().rename(columns={"index": "年份层"})
    order = ["年份层", "n", "venue_error", "author_error_strict", "author_error_broad", "year_error"]
    df_bin = df_bin[[c for c in order if c in df_bin.columns]]
    for c in ["venue_error", "author_error_strict", "author_error_broad", "year_error"]:
        df_bin[c] = (df_bin[c] * 100).round(2)
    df_bin.columns = ["年份层", "n", "venue候选错误率(%)", "author候选(严格,%)", "author候选(宽,%)", "year错误率(%)"]

    # ---- Sheet 4: 临床域 NCT ----
    crows = [
        ["错误（错链=指向错误试验）", csumm["nct_error_mismatch"]["count"], csumm["nct_error_mismatch"]["rate"],
         csumm["nct_error_mismatch"]["ci95"][0], csumm["nct_error_mismatch"]["ci95"][1]],
        ["缺失（NCT 未回链，完整性）", csumm["nct_missing"]["count"], csumm["nct_missing"]["rate"],
         csumm["nct_missing"]["ci95"][0], csumm["nct_missing"]["ci95"][1]],
        ["匹配", csumm["nct_match"]["count"], csumm["nct_match"]["rate"],
         csumm["nct_match"]["ci95"][0], csumm["nct_match"]["ci95"][1]],
    ]
    df_ct = pd.DataFrame(crows, columns=["类别", "count", "rate", "CI下界", "CI上界"])
    df_ct["rate(%)"] = (df_ct["rate"] * 100).round(2)
    df_ct["CI下界(%)"] = (df_ct["CI下界"] * 100).round(2)
    df_ct["CI上界(%)"] = (df_ct["CI上界"] * 100).round(2)
    df_ct = df_ct[["类别", "count", "rate(%)", "CI下界(%)", "CI上界(%)"]]
    df_ct.loc[len(df_ct)] = ["n(RESULT 引用)", n_c, "", "", ""]

    # ---- Sheet 5: 裁决明细（科研域 89 条候选）----
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

    # ---- Sheet 6: 审计信息 ----
    info = [
        ["框架", "三类元数据缺陷：错误(填错) / 缺失(没填) / 表示不一致(同实体异写)"],
        ["科研域源", "OpenAlex"],
        ["科研域金标准", "Crossref"],
        ["科研域采样", "分层随机 n=1000（5 年份层 × 200），join 成功 940"],
        ["临床域源", "ClinicalTrials.gov（RESULT 引用）"],
        ["临床域金标准", "PubMed（DataBankList 的 NCT）"],
        ["临床域样本", "n=1000 试验 → 181 个 RESULT 引用"],
        ["日期", "2026-10-19"],
    ]
    df_info = pd.DataFrame(info, columns=["属性", "值"])

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        df_info.to_excel(xw, sheet_name="审计信息", index=False)
        df3.to_excel(xw, sheet_name="三类缺陷汇总", index=False)
        df_layer.to_excel(xw, sheet_name="科研域三层结果", index=False)
        df_bin.to_excel(xw, sheet_name="科研域分层", index=False)
        df_ct.to_excel(xw, sheet_name="临床域NCT", index=False)
        df_adj.to_excel(xw, sheet_name="裁决明细", index=False)

    print(f"written: {OUT}")
    print(f"sheets: 审计信息 / 三类缺陷汇总({len(df3)}) / 科研域三层结果({len(df_layer)}) / "
          f"科研域分层({len(df_bin)}) / 临床域NCT({len(df_ct)}) / 裁决明细({len(df_adj)})")


if __name__ == "__main__":
    main()
