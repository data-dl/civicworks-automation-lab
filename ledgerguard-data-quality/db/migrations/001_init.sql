-- LedgerGuard: the operations log for a fictional equipment-rental cooperative's daily QA jobs.
-- The equipment and people data live in their own sources; this database records what each job
-- exported, what it expected, what it found, and every file it archived.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE qa_run (
    run_id      TEXT PRIMARY KEY,
    run_date    TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    verdict     TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE export_job (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES qa_run(run_id),
    job_code        TEXT NOT NULL,
    source_adapter  TEXT NOT NULL,
    expected_rows   INTEGER NOT NULL,
    observed_rows   INTEGER NOT NULL,
    state           TEXT NOT NULL CHECK (state IN ('verified', 'quarantined')),
    reason          TEXT NOT NULL DEFAULT '',
    file_sha256     TEXT NOT NULL,
    exceptions      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (run_id, job_code)
);

CREATE TABLE archive_item (
    archive_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES qa_run(run_id),
    file_name     TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    archive_path  TEXT NOT NULL,
    restore_path  TEXT NOT NULL
);
