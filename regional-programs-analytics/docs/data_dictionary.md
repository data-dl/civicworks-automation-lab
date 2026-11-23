# Data dictionary

All values are synthetic. Sensitivity: none.

| table | column | constraint | meaning |
|---|---|---|---|
| region | region_code, label | PK, unique | NF Northfield, EM Eastmere, SB Southbank, WV Westvale |
| venue | venue_id | PK | `HV-NF01` ... |
| venue | name | unique | invented venue name |
| venue | region_code | FK region | |
| venue | tier | studio / outreach | service model |
| venue | active | 0/1 | inactive venues are not expected to report |
| quarter | quarter_id, year, number | PK; unique (year, number) | `2026Q3` |
| submission | venue_id, quarter_id | FK venue, FK quarter | |
| submission | version | | from the file name `_vN` |
| submission | file_name, file_sha256 | | which file, exactly |
| submission | status | accepted / superseded / rejected | one **accepted** per venue and quarter (partial unique index) |
| submission | reason | | why superseded or rejected |
| measure | submission_id | FK submission, cascade | |
| measure | metric_code, category, amount | amount >= 0 | attendance by category, attendance_total, sessions_delivered, first_time_visitors, complaints, improvements_logged, incidents_minor, incidents_reportable |
| report_release | quarter_id, version | unique together | approved versions |
| report_release | approved_by, approved_at | | who and when |
| report_release | inputs_json, outputs_json | | file -> SHA-256 for every input and every approved workbook |

Submission file format (`inbox/<quarter>/<venue>_v<n>.csv`): `quarter, venue_id, tier, metric_code,
category, amount`, one row per metric (attendance has one row per category).
