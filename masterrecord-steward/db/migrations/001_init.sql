-- MasterRecord Steward: field-level assertions from several feeds, the conflicts between them,
-- the decisions people make, and every write-back to the master workbook.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE workshop_entity (
    entity_id      TEXT PRIMARY KEY,          -- stable synthetic organisation id, e.g. GJF-0007
    display_token  TEXT NOT NULL
);

CREATE TABLE source_assertion (
    assertion_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle           TEXT NOT NULL,
    entity_id       TEXT NOT NULL REFERENCES workshop_entity(entity_id),
    field_code      TEXT NOT NULL,
    asserted_value  TEXT NOT NULL,
    source_code     TEXT NOT NULL,
    observed_at     TEXT NOT NULL,
    UNIQUE (cycle, entity_id, field_code, asserted_value, source_code, observed_at)
);

CREATE TABLE proposal (
    proposal_id   TEXT PRIMARY KEY,           -- P-001 (a change) or H-001 (a hold)
    cycle         TEXT NOT NULL,
    entity_id     TEXT NOT NULL REFERENCES workshop_entity(entity_id),
    field_code    TEXT NOT NULL,
    current_value TEXT NOT NULL,
    proposed      TEXT NOT NULL,              -- '' for a hold
    kind          TEXT NOT NULL CHECK (kind IN ('change', 'hold', 'exclude')),
    explanation   TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);

CREATE TABLE stewardship_decision (
    decision_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id    TEXT NOT NULL REFERENCES proposal(proposal_id),
    resolution     TEXT NOT NULL CHECK (resolution IN ('approve', 'reject', 'choose')),
    value          TEXT NOT NULL,
    approver_role  TEXT NOT NULL,
    rationale      TEXT NOT NULL,
    decided_at     TEXT NOT NULL,
    decision_hash  TEXT NOT NULL UNIQUE       -- the same decision can never be recorded twice
);

CREATE TABLE history_write (
    write_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id    INTEGER NOT NULL REFERENCES stewardship_decision(decision_id),
    sheet_name     TEXT NOT NULL,
    backup_name    TEXT NOT NULL,
    snapshot_hash  TEXT NOT NULL,             -- master workbook hash after the write
    written_at     TEXT NOT NULL
);
