-- OpenBadge registry: learners, the badges they hold, and every release of the public registry.
-- All names, codes and rules are invented for a fictional academy.

CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE badge_type (
    code           TEXT PRIMARY KEY,
    label          TEXT NOT NULL,
    validity_days  INTEGER NOT NULL CHECK (validity_days > 0)
);

CREATE TABLE learner (
    learner_id  TEXT PRIMARY KEY,
    alias       TEXT NOT NULL UNIQUE
);

-- No UNIQUE on badge_id on purpose: duplicates arrive from upstream and must be caught by the
-- release checks with a readable finding, not by a constraint error halfway through an import.
CREATE TABLE badge (
    row_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id     TEXT NOT NULL,
    learner_id   TEXT NOT NULL REFERENCES learner(learner_id),
    badge_type   TEXT NOT NULL REFERENCES badge_type(code),
    issue_date   TEXT NOT NULL,
    expiry_date  TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('approved', 'revoked', 'pending'))
);
CREATE INDEX badge_by_id ON badge(badge_id);

CREATE TABLE registry_release (
    release_id         TEXT PRIMARY KEY,
    payload_path       TEXT,
    sha256             TEXT,
    record_count       INTEGER,
    technical_status   TEXT NOT NULL CHECK (technical_status IN ('blocked', 'verify-failed', 'verified')),
    consumer_status    TEXT NOT NULL DEFAULT 'not-checked'
                       CHECK (consumer_status IN ('not-checked', 'pending', 'accepted', 'rejected')),
    created_at         TEXT NOT NULL,
    findings_json      TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE pointer_history (
    pointer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id   TEXT NOT NULL REFERENCES registry_release(release_id),
    switched_at  TEXT NOT NULL,
    reason       TEXT NOT NULL
);

CREATE TABLE consumer_result (
    result_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id  TEXT NOT NULL REFERENCES registry_release(release_id),
    verdict     TEXT NOT NULL CHECK (verdict IN ('pending', 'accepted', 'rejected')),
    reason      TEXT NOT NULL,
    checked_at  TEXT NOT NULL
);
