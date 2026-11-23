# Regional Programs Analytics - transcript

Video length 106 s. Real demo run 1.5 s; 11 passed.

- **00:00** Regional Programs Analytics. Quarterly Excel reports for an arts network that refuse to be approved while the data is incomplete or wrong.
- **00:07** 1. A fictional arts network: 4 regions, 16 venues, two service tiers. Sixteen invented venues send a CSV every quarter. This quarter's files carry five planted problems.
- **00:18** 2. Last quarter: checks pass, the program director approves it. Last quarter is clean: checks pass, the program director approves, and the workbooks are frozen read-only.
- **00:28** 3. This quarter: draft packs are built, but approval is blocked. This quarter builds draft workbooks but approval is blocked: two venues missing, one total that does not add up. A wrong-quarter file and a second version are handled and noted.
- **00:40** 4. Reminders went out; the late and corrected files arrive. The late and corrected files arrive. Rerun: everything reconciles and the quarter is approved. A real attendance swing is flagged for commentary.
- **00:51** 5. Someone re-runs approval: the approved quarter is not replaced. Approving again replaces nothing. A revision would need --new-version and would sit beside v1.
- **01:02** 6. What was produced. Approved workbooks and draft emails. Nothing is sent; the outbox holds drafts for a person.
- **01:12** What it produced: Studio_2026Q3.xlsx - Summary tab. The approved Summary tab: every figure is a formula over the venue rows, with the chart.
- **01:19** What it produced: Studio_2026Q3.xlsx - Quarter Comparison tab. Like-for-like comparison with last quarter.
- **01:25** What it produced: Incidents_2026Q3.xlsx - Incidents tab. The incident workbook, reportable incidents highlighted.
- **01:32** What it produced: outbox/2026Q3/2026Q3-program-director.eml. A distribution draft - marked NOT SENT.
- **01:38** What this run showed: Missing venues and bad totals blocked approval; Wrong-quarter and duplicate files handled, not counted twice; Approved quarters frozen and hashed; Distribution is draft-only. Tests: 11 passed.

## Terminal output (captured, unedited)

```
== 1. A fictional arts network: 4 regions, 16 venues, two service tiers
  16 venues; 2026Q2 submissions clean; 2026Q3 has planted problems:
    totals_mismatch: HV-NF01
    missing_contributor: HV-EM03
    wrong_period: HV-SB02
    duplicate_submission: HV-WV02
    large_swing: Westvale outreach

== 2. Last quarter: checks pass, the program director approves it
  2026Q2: APPROVED v1  (usable submissions 16 of 16)
    [-] prior_quarter: 2026Q1 is not approved; comparison is provisional
    built: Studio_2026Q2.xlsx, Outreach_2026Q2.xlsx, Incidents_2026Q2.xlsx, Review_pack_2026Q2.md
    approved copies (read-only): v1/

== 3. This quarter: draft packs are built, but approval is blocked
  2026Q3: BLOCKED  (usable submissions 14 of 16)
    [-] wrong_period: HV-SB02_v1.csv: file is for 2026Q2, not 2026Q3
    [-] duplicate_submission: HV-WV02: 2 versions received; v2 used, v1 kept as superseded
    [x] missing_contributor: HV-EM03 (Eastmere Story Bus) has not submitted a usable file
    [x] missing_contributor: HV-SB02 (Southbank Kiln House) has not submitted a usable file
    [x] totals_reconcile: HV-NF01: attendance_total 1501 but categories sum to 1464
    [-] large_swing: Westvale outreach: attendance +71% vs 2026Q2; add commentary to the review pack
    built: Studio_2026Q3.xlsx, Outreach_2026Q3.xlsx, Incidents_2026Q3.xlsx, Review_pack_2026Q3.md

== 4. Reminders went out; the late and corrected files arrive
    received HV-EM03_v1.csv
    received HV-SB02_v2.csv
    received HV-NF01_v2.csv
  2026Q3: APPROVED v1  (usable submissions 16 of 16)
    [-] wrong_period: HV-SB02_v1.csv: file is for 2026Q2, not 2026Q3
    [-] duplicate_submission: HV-NF01: 2 versions received; v2 used, v1 kept as superseded
    [-] duplicate_submission: HV-WV02: 2 versions received; v2 used, v1 kept as superseded
    [-] large_swing: Westvale outreach: attendance +71% vs 2026Q2; add commentary to the review pack
    built: Studio_2026Q3.xlsx, Outreach_2026Q3.xlsx, Incidents_2026Q3.xlsx, Review_pack_2026Q3.md
    approved copies (read-only): v1/

== 5. Someone re-runs approval: the approved quarter is not replaced
  2026Q3: ALREADY APPROVED (v1); nothing replaced  (usable submissions 16 of 16)
    [-] large_swing: Westvale outreach: attendance +71% vs 2026Q2; add commentary to the review pack
    built: Studio_2026Q3.xlsx, Outreach_2026Q3.xlsx, Incidents_2026Q3.xlsx, Review_pack_2026Q3.md

== 6. What was produced
  approved/2026Q3/v1/
    Incidents_2026Q3.xlsx
    Outreach_2026Q3.xlsx
    Studio_2026Q3.xlsx
  outbox/2026Q3/
    2026Q3-board-liaison.eml
    2026Q3-program-director.eml
    2026Q3-regional-leads.eml
  Drafts are never sent: the outbox holds .eml files for a person to review.
```
