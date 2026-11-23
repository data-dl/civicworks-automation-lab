# MasterRecord Steward - transcript

Video length 96 s. Real demo run 0.9 s; 16 passed.

- **00:00** MasterRecord Steward. Master records fed by three systems that disagree: decide what the evidence justifies, hold the rest for a person, change nothing else.
- **00:08** 1. A guild master workbook and three feeds that disagree. A guild master workbook with history and reference rows at row 500, and three feeds that disagree.
- **00:15** 2. Propose: resolve every field by the precedence matrix. Each field is resolved by a precedence matrix. Five changes are justified; four cases are held because no rule can settle them; one workshop is out of scope.
- **00:28** 3. The registrar decides: approve the changes, settle two holds, leave two for later. The registrar approves the changes and settles two holds with a reason. Two stay open.
- **00:34** 4. Dry run: what would be written. A dry run shows exactly which cells would change.
- **00:46** 5. Apply: backup, write, prove nothing else moved. Apply: a verified backup, the decided cells written, a new dated Changes tab, and a check that every other cell is unchanged.
- **00:57** 6. Apply the same decisions again. The same decisions again change nothing: each decision is recorded once by its hash.
- **01:03** 7. Next proposal run: only the undecided holds remain. Next run, only the two undecided holds come back. Settled questions stay settled.
- **01:09** What it produced: Review_queue_2026-11.xlsx - Holds - decide tab. The review queue: each hold with the evidence from every source.
- **01:16** What it produced: Guild_Workshop_Master.xlsx - Changes 2026-11-23 tab. The new Changes tab: old value, new value, decision, role, reason.
- **01:22** What it produced: review/decisions_2026-11_signed.csv. The registrar's decisions file.
- **01:29** What this run showed: Authority wins; disagreements are held, never guessed; Unknown is kept apart from ineligible; Only approved cells changed; history and row 500 intact; Applying twice changes nothing. Tests: 16 passed.

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
    new tab 'Changes 2026-11-23'; backup Guild_Workshop_Master_20261123T221618.xlsx; 309 existing cells checked unchanged

== 6. Apply the same decisions again
  0 writes; 8 decisions already applied - nothing changed

== 7. Next proposal run: only the undecided holds remain
  changes 0, holds 2: H-GJF-0005-network_affiliation, H-GJF-0014-certification_class
```
