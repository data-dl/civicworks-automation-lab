# masterrecord - transcript

Length 127 s.

- **00:00** MasterRecord Steward. Master records from three disagreeing sources - justified changes approved, the rest held for a person, nothing else touched.
- **00:11** Scene 1. A master workbook with history and reference rows, and three feeds that disagree in planted ways. The registry - it is the authority for that field.
- **00:23** Scene 2. Every field is resolved. Five changes are justified, four cases are held, one workshop is out of scope. No source gave any certification. Unknown is not the same as not certified, so a person decides.
- **00:41** Scene 3. The registrar approves the changes and settles two holds with a reason. Two stay open. A resolution, an approver role and a rationale.
- **00:52** Scene 4. A dry run shows exactly which cells would change. No - a dry run only reports.
- **01:01** Scene 5. Apply: verified backup, decided cells written, a new Changes tab, and proof that 309 other cells are unchanged. It is untouched; the new changes go on a new dated tab.
- **01:17** Scene 6. The same decisions are applied again. None. Each decision is recognised by its hash.
- **01:26** Scene 7. The next proposal run shows only the two undecided holds. Their decisions are recorded and the master now holds the decided value.
- **01:37** The review queue: each hold with the evidence from every source.
- **01:43** The new Changes tab: old value, new value, decision, role, reason.
- **01:51** What this run showed: Authority wins; disagreements are held, never guessed. Unknown kept apart from ineligible. Only approved cells changed; history intact. Applying twice changes nothing.

## Terminal output (captured, unedited)

```
== 1. A guild master workbook and three feeds that disagree
  master: 30 workshops, an earlier Changes tab, reference rows at row 500
  feeds: registry (authoritative), contract, site inspections

== 2. Propose: resolve every field by the precedence matrix
  136 field values agree with the master; 3 duplicate assertions ignored
  5 changes to approve:
    P-GJF-0003-certification_class: Journeyman -> Master  [registry (authority) says Master; contract says Journeyman - not used]
    P-GJF-0020-inspection_zone: (blank) -> Z4  [no source gives one; filled from the postcode fallback map (Z4)]
    P-GJF-0022-participation_status: active -> lapsed  [registry (authority) says lapsed]
    P-GJF-0023-certification_class: Journeyman -> none  [registry (authority) says none]
    P-GJF-0027-network_affiliation: Inland Bench -> Northern Circle  [contract says Northern Circle]
  4 holds for a person:
    H-GJF-0005-network_affiliation: sources disagree: contract says Coastal Ring, registry says Northern Circle
    H-GJF-0008-inspection_zone: sources disagree: site says Z2/Z4
    H-GJF-0011-workshop_type: sources disagree: site says joinery, contract says finishing
    H-GJF-0014-certification_class: UNKNOWN: no source gives a value and the master has none (missing, not ineligible)
  excluded GJF-0017: registry classifies it as retail showroom, which is out of scope for the master
  review queue: review/Review_queue_2026-11.xlsx

== 3. The registrar decides: approve the changes, settle two holds, leave two for later
  decisions file: review/decisions_2026-11_signed.csv

== 4. Dry run: what would be written
    would write GJF-0003 certification_class: Journeyman -> Master
    would write GJF-0020 inspection_zone: (blank) -> Z4
    would write GJF-0022 participation_status: active -> lapsed
    would write GJF-0023 certification_class: Journeyman -> none
    would write GJF-0027 network_affiliation: Inland Bench -> Northern Circle
    would write GJF-0017 Scope: in -> excluded
    would write GJF-0008 inspection_zone: Z3 -> Z4
    would write GJF-0011 workshop_type: joinery -> finishing
    no decision yet: H-GJF-0005-network_affiliation, H-GJF-0014-certification_class

== 5. Apply: backup, write, prove nothing else moved
    wrote GJF-0003 certification_class: Journeyman -> Master
    wrote GJF-0020 inspection_zone: (blank) -> Z4
    wrote GJF-0022 participation_status: active -> lapsed
    wrote GJF-0023 certification_class: Journeyman -> none
    wrote GJF-0027 network_affiliation: Inland Bench -> Northern Circle
    wrote GJF-0017 Scope: in -> excluded
    wrote GJF-0008 inspection_zone: Z3 -> Z4
    wrote GJF-0011 workshop_type: joinery -> finishing
    no decision yet: H-GJF-0005-network_affiliation, H-GJF-0014-certification_class
    new tab 'Changes 2026-11-23'; backup Guild_Workshop_Master_20261124T025251.xlsx; 309 existing cells checked unchanged

== 6. Apply the same decisions again
  0 writes; 8 decisions already applied - nothing changed

== 7. Next proposal run: only the undecided holds remain
  changes 0, holds 2: H-GJF-0005-network_affiliation, H-GJF-0014-certification_class
```
