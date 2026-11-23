# Data dictionary

All values are synthetic. Sensitivity: none.

| table | column | constraint | meaning |
|---|---|---|---|
| workshop_entity | entity_id | PK | stable synthetic id, `GJF-0007` |
| workshop_entity | display_token | | workshop name from the registry feed |
| source_assertion | cycle, entity_id, field_code, asserted_value, source_code, observed_at | unique together | one value one source gave for one field; repeats are ignored |
| proposal | proposal_id | PK | stable: `P-` change / `H-` hold / `X-` exclusion + entity + field |
| proposal | kind | change / hold / exclude | |
| proposal | current_value, proposed | | the master now, and what the evidence justifies ('' for a hold) |
| proposal | explanation, evidence_json | | why, and every source's values |
| stewardship_decision | proposal_id | FK proposal | |
| stewardship_decision | resolution | approve / reject / choose | |
| stewardship_decision | value, approver_role, rationale, decided_at | | role and rationale are required |
| stewardship_decision | decision_hash | unique | the same decision is never recorded or applied twice |
| history_write | decision_id | FK stewardship_decision | |
| history_write | sheet_name, backup_name, snapshot_hash, written_at | | which Changes tab, which verified backup, the master's SHA-256 after the write |

Master workbook tabs: Instructions, Master (data rows, then reference rows from row 500), Reference,
and one `Changes <date>` tab per apply.
