# regional - transcript

Length 129 s.

- **00:00** Regional Programs Analytics. Quarterly Excel reports that refuse approval while the data is incomplete, and freeze once approved.
- **00:10** Scene 1. Sixteen venues; last quarter's files are clean and this quarter's carry five planted problems. The missing venue and the bad total block. The wrong-quarter file and the duplicate version are handled and noted; the swing only needs commentary.
- **00:27** Scene 2. Last quarter passes every check and the program director approves it. The workbooks are frozen read-only. It is approved, and its input hashes are recorded, so any later change to it will be detected.
- **00:43** Scene 3. This quarter: drafts are built so people can see the state, but approval is refused. The other sent last quarter's file by mistake; it was rejected as the wrong period, so that venue has no usable file.
- **00:59** Scene 4. The late and corrected files arrive. Everything reconciles and the quarter is approved. v2, the newest. v1 is kept as superseded, never counted.
- **01:13** Scene 5. Approval is run again. No. ALREADY APPROVED; a real revision needs --new-version and would sit beside v1.
- **01:23** Scene 6. The approved workbooks and the draft emails. No. Drafts sit in the outbox for a person; there is no sending code at all.
- **01:35** The approved Summary tab: every figure is a formula over the venue rows.
- **01:42** Like-for-like comparison with last quarter.
- **01:48** A distribution draft - marked NOT SENT.
- **01:53** What this run showed: Missing venues and bad totals blocked approval. Wrong-quarter and duplicate files never counted twice. Approved quarters frozen and hashed. Distribution is draft-only.

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
