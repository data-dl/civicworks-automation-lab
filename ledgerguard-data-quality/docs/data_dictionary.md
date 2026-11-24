# Data dictionary

All values are synthetic. Sensitivity: none.

## Sources

| source | field | meaning |
|---|---|---|
| registry.sqlite `equipment` | equipment_id (PK), class_code, depot, serial_token, last_service, status | the equipment register |
| roster.csv | technician_id, alias, depot, active | technicians (aliases only) |
| authorizations.csv | technician_id, class_code, expiry | which classes each technician may service, until when |
| desk app export | equipment_id, class_code, depot, serial_token, last_service, status | the same register, via the old program's Export button |

## Operations log (ledgerguard.sqlite)

| table | column | constraint | meaning |
|---|---|---|---|
| qa_run | run_id | PK | the day, e.g. 2026-11-23 |
| qa_run | run_date, started_at, verdict | | |
| export_job | (run_id, job_code) | unique | one row per job per day |
| export_job | source_adapter | | sqlite / csv / sqlite+csv / desk-app |
| export_job | expected_rows, observed_rows | | what the source says vs what the file holds |
| export_job | state | verified / quarantined | |
| export_job | reason, file_sha256, exceptions | | why quarantined; the file's hash; exception count |
| archive_item | run_id, file_name, sha256, archive_path, restore_path | | every file moved to the archive, and where it would go back (paths relative to the workspace) |

Files: `exports/<day>/`, `quarantine/<day>/`, `current/{4 CSVs, exceptions.xlsx, dashboard.html,
MANIFEST.json}`, `archive/<day>/` (same layout).
