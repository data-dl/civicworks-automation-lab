-- OpsPilot: runs, their steps, checkpoints, scoped approvals and an append-only event log.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE pipeline (
    pipeline_id  TEXT PRIMARY KEY,             -- the goal name
    description  TEXT NOT NULL
);

CREATE TABLE stage (
    pipeline_id   TEXT NOT NULL REFERENCES pipeline(pipeline_id),
    stage_id      TEXT NOT NULL,
    ordinal       INTEGER NOT NULL,
    tool          TEXT NOT NULL,
    effect_class  TEXT NOT NULL CHECK (effect_class IN ('read', 'write', 'publish')),
    PRIMARY KEY (pipeline_id, stage_id)
);

CREATE TABLE execution (
    run_id       TEXT PRIMARY KEY,
    pipeline_id  TEXT NOT NULL REFERENCES pipeline(pipeline_id),
    state        TEXT NOT NULL CHECK (state IN ('running', 'interrupted', 'awaiting-approval', 'blocked',
                                                'failed', 'complete')),
    started_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE checkpoint (
    run_id         TEXT NOT NULL REFERENCES execution(run_id),
    stage_id       TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('done', 'blocked', 'failed', 'awaiting-approval', 'skipped')),
    exit_code      INTEGER,
    artifact_hash  TEXT NOT NULL DEFAULT '',
    finished_at    TEXT NOT NULL,
    PRIMARY KEY (run_id, stage_id)
);

CREATE TABLE authorization (
    authorization_id  TEXT PRIMARY KEY,         -- the token a person issued, e.g. APR-0001
    run_id            TEXT NOT NULL REFERENCES execution(run_id),
    stage_id          TEXT NOT NULL,
    role              TEXT NOT NULL,
    approved_at       TEXT NOT NULL,
    UNIQUE (run_id, stage_id)
);

CREATE TABLE event_log (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    at          TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL
);

-- Append-only: the database itself refuses to change or delete history.
CREATE TRIGGER event_log_no_update BEFORE UPDATE ON event_log
BEGIN SELECT RAISE(ABORT, 'event_log is append-only'); END;
CREATE TRIGGER event_log_no_delete BEFORE DELETE ON event_log
BEGIN SELECT RAISE(ABORT, 'event_log is append-only'); END;
