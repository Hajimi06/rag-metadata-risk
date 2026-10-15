"""导出审计中的候选分歧（venue diff / author diff），供人工裁决。"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "audit")

with open(os.path.join(DATA_DIR, "audit_analysis.json"), encoding="utf-8") as f:
    rows = json.load(f)

venue_diffs = [r for r in rows if r["venue"] == "diff"]
author_diffs = [r for r in rows if r["author"] == "diff"]

print(f"=== VENUE DIFFS: {len(venue_diffs)} ===")
for i, r in enumerate(venue_diffs, 1):
    print(f"{i}. OA=[{r['oa_venue']}]  CR=[{r['cr_venue']}]")

print(f"\n=== AUTHOR DIFFS: {len(author_diffs)} ===")
for i, r in enumerate(author_diffs, 1):
    print(f"{i}. OA-only={r['unmatched_oa_authors']}  CR-only={r['unmatched_cr_authors']}")
