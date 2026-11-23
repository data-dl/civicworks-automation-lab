-- SafeSite: a fictional facilities consortium's quarterly safety-observation cycle.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE facility (
    facility_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    area_code    TEXT NOT NULL,
    category     TEXT NOT NULL CHECK (category IN ('workshop', 'depot'))
);

CREATE TABLE coordinator (
    coordinator_id   TEXT PRIMARY KEY,
    role             TEXT NOT NULL,
    fictional_email  TEXT NOT NULL CHECK (fictional_email LIKE '%@example.org')
);

CREATE TABLE assignment (
    assignment_id   TEXT PRIMARY KEY,
    quarter         TEXT NOT NULL,
    facility_id     TEXT NOT NULL REFERENCES facility(facility_id),
    coordinator_id  TEXT NOT NULL REFERENCES coordinator(coordinator_id),
    due_at          TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'open'
                    CHECK (state IN ('open', 'correction-requested', 'accepted', 'accepted-late', 'overdue')),
    submitted_on    TEXT,
    file_name       TEXT,
    file_sha256     TEXT,
    note            TEXT NOT NULL DEFAULT '',
    UNIQUE (quarter, facility_id)
);

CREATE TABLE observation (
    observation_id  TEXT NOT NULL,
    assignment_id   TEXT NOT NULL REFERENCES assignment(assignment_id) ON DELETE CASCADE,
    observed_on     TEXT NOT NULL,
    area            TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('S1', 'S2', 'S3', 'S4')),
    description     TEXT NOT NULL,
    action_state    TEXT NOT NULL CHECK (action_state IN ('open', 'in-progress', 'closed')),
    evidence_ref    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (assignment_id, observation_id)
);

-- One draft per assignment and reminder kind: re-running the cycle never duplicates a reminder.
CREATE TABLE reminder (
    reminder_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  TEXT NOT NULL REFERENCES assignment(assignment_id),
    kind           TEXT NOT NULL CHECK (kind IN ('T-14', 'T-3', 'overdue', 'correction')),
    as_of          TEXT NOT NULL,
    draft_path     TEXT NOT NULL,
    UNIQUE (assignment_id, kind)
);

CREATE TABLE report_final (
    quarter      TEXT NOT NULL,
    variant      TEXT NOT NULL,
    path         TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    approved_by  TEXT NOT NULL,
    approved_at  TEXT NOT NULL,
    PRIMARY KEY (quarter, variant)
);
