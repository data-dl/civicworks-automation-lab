-- Regional Programs Analytics: a fictional network of art studios reporting every quarter.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE region (
    region_code  TEXT PRIMARY KEY,
    label        TEXT NOT NULL UNIQUE
);

CREATE TABLE venue (
    venue_id     TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    region_code  TEXT NOT NULL REFERENCES region(region_code),
    tier         TEXT NOT NULL CHECK (tier IN ('studio', 'outreach')),
    active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE quarter (
    quarter_id  TEXT PRIMARY KEY,               -- e.g. 2026Q3
    year        INTEGER NOT NULL,
    number      INTEGER NOT NULL CHECK (number BETWEEN 1 AND 4),
    UNIQUE (year, number)
);

CREATE TABLE submission (
    submission_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id       TEXT NOT NULL REFERENCES venue(venue_id),
    quarter_id     TEXT NOT NULL REFERENCES quarter(quarter_id),
    version        INTEGER NOT NULL,
    file_name      TEXT NOT NULL,
    file_sha256    TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('accepted', 'superseded', 'rejected')),
    reason         TEXT NOT NULL DEFAULT '',
    UNIQUE (venue_id, quarter_id, version, file_sha256)
);

-- Only one accepted submission per venue and quarter, enforced by the database itself.
CREATE UNIQUE INDEX one_accepted_submission ON submission(venue_id, quarter_id) WHERE status = 'accepted';

CREATE TABLE measure (
    measure_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id  INTEGER NOT NULL REFERENCES submission(submission_id) ON DELETE CASCADE,
    metric_code    TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT '',
    amount         INTEGER NOT NULL CHECK (amount >= 0)
);

CREATE TABLE report_release (
    report_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    quarter_id    TEXT NOT NULL REFERENCES quarter(quarter_id),
    version       INTEGER NOT NULL,
    approved_by   TEXT NOT NULL,
    approved_at   TEXT NOT NULL,
    inputs_json   TEXT NOT NULL,                -- file name -> sha256 of every accepted submission
    outputs_json  TEXT NOT NULL,                -- workbook name -> sha256
    UNIQUE (quarter_id, version)
);
