# ReconcileHub - transcript

Video length 98 s. Real demo run 0.9 s; 15 passed.

- **00:00** ReconcileHub. Monthly access-roster reconciliation that never merges two people on a guess.
- **00:08** 1. This month's inputs: access-system roster, last month's approvals, new registrations. Three inputs: the door-access system's roster, last month's approvals, new registrations, with the usual mess planted.
- **00:19** 2. Reconcile: exact matches decided, everything else held. Exact id matches are decided automatically. An id change, a row with no id and a likely duplicate registration are held with a suggestion.
- **00:30** 3. Try to approve before review. Approval is refused while cases are held, and a note to the space admins is drafted.
- **00:36** 4. A reviewer decides the held cases. A reviewer records same-person for each. Only now do they become rename and fix-id actions.
- **00:49** 5. Approve. Approved: a hashed roster snapshot, an import workbook and a change report.
- **00:55** 6. Run it again: same inputs, same decisions. Same inputs and decisions again: identical hash, nothing new written.
- **01:01** 7. A late registration arrives after approval. A late registration after approval is refused unless superseded with a reason; v2 sits beside v1.
- **01:11** What it produced: Access_import_2026-11_v1.xlsx - Import tab. The import workbook: one row per action, with the reason.
- **01:18** What it produced: exports/2026-11/Change_report_2026-11_v1.md. The change report, reviewed cases included.
- **01:24** What it produced: outbox/2026-11/2026-11-held-cases.eml. The draft to space admins while cases were held.
- **01:31** What this run showed: Ids normalised, originals kept; Near-matches suggested, never merged; Approval blocked until people decided; Re-runs idempotent; changes need a reason. Tests: 15 passed.

## Terminal output (captured, unedited)

```
== 1. This month's inputs: access-system roster, last month's approvals, new registrations
  planted changed_id: FC-00031 -> FC-00931 (Quin Brindlecote)
  planted missing_id: Lark Brindlecote
  planted role_drift: FC-00013 member -> steward in the access system
  planted should_be_revoked: FC-00051 (not in last month's approvals)
  planted possible_duplicate_registration: REG-2611-03 looks like FC-00009 Kit Larkspurne
  planted same_name_two_people: FC-00005 and FC-00059 are both Bryn Mossgrave

== 2. Reconcile: exact matches decided, everything else held
  unchanged 55; ids normalised 1; actions: ADD 2, CHANGE ROLE 1, REMOVE 1
    CHANGE ROLE FC-00013 Hollis Mossgrave: system has steward; approved member
    ADD         FC-00060 Pim Hollowmere: registration REG-2611-01
    ADD         FC-00061 Sable Quarrywick: registration REG-2611-02
    REMOVE      FC-00051 Esme Fennimoss: not in last month's approvals or this month's registrations
    case [held] possible-id-change (100%): Quin Brindlecote (FC-00031) is missing; Quin Brindlecote (FC-00931) appeared in the same space
    case [held] missing-id (100%): access-system row 42 (Lark Brindlecote) has no member id; suggested FC-00041
    case [held] possible-duplicate (100%): REG-2611-03 'kit  larkspurne' has no member id; looks like FC-00009 Kit Larkspurne (100%)
    note: FC-00005 and FC-00059 share a name; kept as different people (ids differ)

== 3. Try to approve before review
  BLOCKED: 3 case(s) held for review; draft to space admins: 2026-11-held-cases.eml

== 4. A reviewer decides the held cases
    possible-id-change:FC-00031->FC-00931 -> same-person
    missing-id:FC-00041->row 42 -> same-person
    possible-duplicate:FC-00009->REG-2611-03 -> same-person
  recorded (0 problems)
  unchanged 55; ids normalised 1; actions: ADD 2, CHANGE ROLE 1, FIX ID 1, REMOVE 1, RENAME ID 1
    RENAME ID   FC-00931 Quin Brindlecote: was FC-00031; possible-id-change:FC-00031->FC-00931
    FIX ID      FC-00041 Lark Brindlecote: row 42 had no id; missing-id:FC-00041->row 42
    CHANGE ROLE FC-00013 Hollis Mossgrave: system has steward; approved member
    ADD         FC-00060 Pim Hollowmere: registration REG-2611-01
    ADD         FC-00061 Sable Quarrywick: registration REG-2611-02
    REMOVE      FC-00051 Esme Fennimoss: not in last month's approvals or this month's registrations
    case [same-person] possible-id-change (100%): Quin Brindlecote (FC-00031) is missing; Quin Brindlecote (FC-00931) appeared in the same space
    case [same-person] missing-id (100%): access-system row 42 (Lark Brindlecote) has no member id; suggested FC-00041
    case [same-person] possible-duplicate (100%): REG-2611-03 'kit  larkspurne' has no member id; looks like FC-00009 Kit Larkspurne (100%)
    note: REG-2611-03 is existing member FC-00009; no new access
    note: FC-00005 and FC-00059 share a name; kept as different people (ids differ)

== 5. Approve
  APPROVED v1 (sha256 826d7305c4b3): approved_roster.csv, Access_import_2026-11_v1.xlsx, Change_report_2026-11_v1.md

== 6. Run it again: same inputs, same decisions
  NOTHING NEW: identical to v1 (sha256 826d7305c4b3)

== 7. A late registration arrives after approval
  REFUSED: v1 is approved and the result now differs; rerun with --supersede REASON to approve a new version
  with --supersede: APPROVED v2 (sha256 a39445c6d5ec): approved_roster.csv, Access_import_2026-11_v2.xlsx, Change_report_2026-11_v2.md
  v1 is still in snapshots/2026-11/v1/
```
