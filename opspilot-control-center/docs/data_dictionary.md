# Data dictionary

| table | column | constraint | meaning |
|---|---|---|---|
| pipeline | pipeline_id, description | PK | a goal from `tools.yaml` |
| stage | (pipeline_id, stage_id) | PK | a step of the goal |
| stage | ordinal, tool, effect_class | read / write / publish | |
| execution | run_id | PK | `<goal>-<date>[-n]` |
| execution | state | running / interrupted / awaiting-approval / blocked / failed / complete | |
| checkpoint | (run_id, stage_id) | PK | |
| checkpoint | status | done / blocked / failed / awaiting-approval / skipped | |
| checkpoint | exit_code, artifact_hash, finished_at | | SHA-256 over the step's declared outputs |
| authorization | authorization_id | PK | `APR-0001`, issued by a person |
| authorization | (run_id, stage_id) | unique | one approval per publish step per run |
| authorization | role, approved_at | | passed to the project as its approver role |
| event_log | event_id, run_id, at, event_type, payload | append-only (UPDATE and DELETE abort) | every start, step, approval, refusal, crash and finish |

Files: `status.html` (read-only snapshot), `logs/<run>/<step>.log`, `logs/<run>/HANDOFF.md`,
`workspaces/<project>/` (each project's own workspace; tools cannot reach outside it).
