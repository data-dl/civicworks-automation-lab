# Data dictionary

Every value is synthetic. Sensitivity: none (no real people, organisations or places).

| table | column | type | constraint | meaning |
|---|---|---|---|---|
| badge_type | code | TEXT | primary key | controlled vocabulary, e.g. `KILN-SAFETY` |
| badge_type | label | TEXT | not null | display name |
| badge_type | validity_days | INTEGER | > 0 | how long a badge of this type lasts |
| learner | learner_id | TEXT | primary key | `L00001` ... |
| learner | alias | TEXT | unique | public alias, `adjective-animal-NNN`; never a name |
| badge | row_id | INTEGER | primary key | storage row |
| badge | badge_id | TEXT | indexed, **not unique on purpose** | `LSA-` + 8 hex; duplicates are caught by release checks |
| badge | learner_id | TEXT | FK learner | holder |
| badge | badge_type | TEXT | FK badge_type | |
| badge | issue_date, expiry_date | TEXT | ISO dates | expiry must be after issue (checked at release) |
| badge | status | TEXT | approved / revoked / pending | only approved badges are published |
| registry_release | release_id | TEXT | primary key | `R0001` ... one per attempt, blocked ones included |
| registry_release | payload_path | TEXT | | path of the data file under `site/` |
| registry_release | sha256 | TEXT | | hash of the canonical bytes built |
| registry_release | technical_status | TEXT | blocked / verify-failed / verified | |
| registry_release | consumer_status | TEXT | not-checked / pending / accepted / rejected | the catalogue's verdict, kept apart |
| registry_release | findings_json | TEXT | | every finding, blocking and advisory |
| pointer_history | release_id, switched_at, reason | | FK registry_release | every move of `latest.json`, rollbacks included |
| consumer_result | release_id, verdict, reason, checked_at | | FK registry_release | every import attempt |

Files: `site/releases/registry-Rnnnn.json` (immutable), `site/latest.json` (the pointer),
`runs/Rnnnn/manifest.json` and `findings.json`, `tickets/Tnnn-*.md`.
