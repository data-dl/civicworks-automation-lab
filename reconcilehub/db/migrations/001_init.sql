-- ReconcileHub: a fictional maker-space federation's monthly access-roster reconciliation.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE participant (
    participant_id  TEXT PRIMARY KEY,          -- normalised member id, e.g. FC-00031
    invented_alias  TEXT NOT NULL
);

CREATE TABLE roster_snapshot (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle        TEXT NOT NULL,
    source_code  TEXT NOT NULL CHECK (source_code IN ('current', 'prior', 'registrations')),
    sha256       TEXT NOT NULL,
    UNIQUE (cycle, source_code, sha256)
);

CREATE TABLE roster_entry (
    entry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     INTEGER NOT NULL REFERENCES roster_snapshot(snapshot_id) ON DELETE CASCADE,
    participant_id  TEXT,                       -- NULL when the source row had no usable id
    raw_id          TEXT NOT NULL,              -- exactly as received
    display_name    TEXT NOT NULL,
    space_code      TEXT NOT NULL,
    access_role     TEXT NOT NULL
);

CREATE TABLE match_case (
    case_id      TEXT PRIMARY KEY,              -- stable: kind + the refs involved
    cycle        TEXT NOT NULL,
    kind         TEXT NOT NULL,
    old_ref      TEXT NOT NULL,
    new_ref      TEXT NOT NULL,
    confidence   REAL NOT NULL,
    detail       TEXT NOT NULL,
    disposition  TEXT NOT NULL DEFAULT 'held'
                 CHECK (disposition IN ('held', 'same-person', 'different-person', 'exclude')),
    reviewer     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE reconciliation_release (
    release_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle        TEXT NOT NULL,
    version      INTEGER NOT NULL,
    approved_by  TEXT NOT NULL,
    sha256       TEXT NOT NULL,                 -- of the approved roster snapshot
    reason       TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    UNIQUE (cycle, version)
);
