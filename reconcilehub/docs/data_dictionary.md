# Data dictionary

All values are synthetic; names are built from invented fragments. Sensitivity: none.

| table | column | constraint | meaning |
|---|---|---|---|
| participant | participant_id | PK | normalised member id, `FC-00031` |
| participant | invented_alias | | display name as first seen |
| roster_snapshot | cycle, source_code, sha256 | unique together | each input file as received: current / prior / registrations |
| roster_entry | snapshot_id | FK roster_snapshot | |
| roster_entry | participant_id | nullable | NULL when the row had no usable id |
| roster_entry | raw_id | | the id exactly as received, never altered |
| roster_entry | display_name, space_code, access_role | | |
| match_case | case_id | PK | stable: kind + the refs involved |
| match_case | kind | possible-id-change / missing-id / possible-duplicate / needs-id / duplicate-id | |
| match_case | old_ref, new_ref, confidence, detail | | the suggestion and how strong it is |
| match_case | disposition, reviewer | held / same-person / different-person / exclude | set only by a person |
| reconciliation_release | cycle, version | unique together | approved versions |
| reconciliation_release | approved_by, sha256, reason, created_at | | sha256 of the approved roster; reason when superseding |

Inputs (`inputs/<cycle>/`): `current_roster.csv`, `prior_approvals.csv`, `new_registrations.csv`.
Outputs: `snapshots/<cycle>/v<n>/approved_roster.csv`, `exports/<cycle>/Access_import_<cycle>_v<n>.xlsx`,
`Change_report_<cycle>_v<n>.md`, `outbox/<cycle>/*.eml`.
