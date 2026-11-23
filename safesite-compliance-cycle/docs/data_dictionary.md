# Data dictionary

All values are synthetic. No real people, sites or incidents.

| table | column | constraint | meaning |
|---|---|---|---|
| facility | facility_id, name | PK, unique | `F01` "Harbor Ward Joinery Workshop" |
| facility | area_code | | HW / MD / RQ (invented districts) |
| facility | category | workshop / depot | decides the report variant |
| coordinator | coordinator_id, role | PK | known only by role |
| coordinator | fictional_email | must end @example.org | |
| assignment | assignment_id | PK | `<quarter>-<facility>` |
| assignment | quarter, facility_id | unique together | one return per facility per quarter |
| assignment | coordinator_id, due_at | FK coordinator | |
| assignment | state | open / correction-requested / accepted / accepted-late / overdue | |
| assignment | submitted_on, file_name, file_sha256, note | | which file was used and why it was refused |
| observation | (assignment_id, observation_id) | PK | |
| observation | severity | S1-S4 | S1 note, S2 minor, S3 significant, S4 urgent |
| observation | action_state | open / in-progress / closed | |
| observation | evidence_ref | | required for S3/S4 |
| reminder | (assignment_id, kind) | unique | kind T-14 / T-3 / overdue / correction; the .eml draft name |
| report_final | (quarter, variant) | PK | approved final, its hash, who approved and when |
