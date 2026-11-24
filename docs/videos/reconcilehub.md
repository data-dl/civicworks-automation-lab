# reconcilehub - transcript

Length 119 s.

- **00:00** ReconcileHub. Monthly access-roster reconciliation that suggests near-matches and never merges two people on a guess.
- **00:09** Scene 1. Three monthly inputs with the usual mess planted. The formatting-only id, the role drift and the member who should be removed. The changed id, missing id and look-alike registration need a person.
- **00:24** Scene 2. Exact matches are decided; three cases are held with a suggestion and a score. Neither, while their case is held.
- **00:35** Scene 3. Approval is tried before review. It blocks and drafts a note to the space admins listing the held cases.
- **00:44** Scene 4. A reviewer decides each case. Only now do RENAME ID and FIX ID actions appear. A RENAME ID action from FC-00031 to FC-00931.
- **00:59** Scene 5. Approved: snapshot, import workbook and change report. Its SHA-256, recorded with the release.
- **01:11** Scene 6. The same inputs and decisions again. No. Identical hash: NOTHING NEW.
- **01:19** Scene 7. A late registration after approval: refused, then superseded with a reason. It stays exactly where it was; v2 sits beside it.
- **01:32** The import workbook: one row per action, with the reason.
- **01:38** The change report, reviewed cases included.
- **01:44** What this run showed: Ids normalised, originals kept. Near-matches suggested, never merged. Approval blocked until people decided. Re-runs idempotent; changes need a reason.

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
