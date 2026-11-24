-- Atlas License Directory: a fictional coalition's directory of endorsed craftspeople and studios.
-- staging_* tables hold each source exactly as received; the normalised tables hold cleaned values,
-- always alongside the raw value they came from.

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE source_file (
    source_name  TEXT NOT NULL,
    period       TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    row_count    INTEGER NOT NULL,
    columns      TEXT NOT NULL,
    loaded_at    TEXT NOT NULL,
    PRIMARY KEY (source_name, period)
);

CREATE TABLE district (
    district_id  TEXT PRIMARY KEY,
    label        TEXT NOT NULL UNIQUE
);

CREATE TABLE craft (
    craft_code  TEXT PRIMARY KEY,
    label       TEXT NOT NULL UNIQUE
);

CREATE TABLE guild_member (
    member_id      TEXT PRIMARY KEY,
    invented_name  TEXT NOT NULL,
    raw_name       TEXT NOT NULL,
    phone_token    TEXT NOT NULL,
    raw_phone      TEXT NOT NULL,
    active_state   TEXT NOT NULL CHECK (active_state IN ('active', 'suspended', 'retired')),
    public_opt_in  INTEGER NOT NULL CHECK (public_opt_in IN (0, 1))
);

CREATE TABLE studio (
    studio_id    TEXT PRIMARY KEY,
    district_id  TEXT REFERENCES district(district_id),   -- NULL when the source named an unknown district
    raw_district TEXT NOT NULL,
    studio_name  TEXT NOT NULL,
    venue_token  TEXT NOT NULL
);

CREATE TABLE endorsement (
    endorsement_id  TEXT PRIMARY KEY,
    member_id       TEXT NOT NULL REFERENCES guild_member(member_id),
    craft_code      TEXT REFERENCES craft(craft_code),      -- NULL when the source craft could not be mapped
    raw_craft       TEXT NOT NULL,
    valid_from      TEXT NOT NULL,
    valid_to        TEXT NOT NULL
);

CREATE TABLE placement (
    placement_id  TEXT PRIMARY KEY,
    member_id     TEXT NOT NULL REFERENCES guild_member(member_id),
    studio_id     TEXT NOT NULL REFERENCES studio(studio_id),
    edition_code  TEXT NOT NULL CHECK (edition_code IN ('public', 'member', 'inspector')),
    approved      INTEGER NOT NULL CHECK (approved IN (0, 1)),
    UNIQUE (member_id, studio_id, edition_code)
);

CREATE TABLE review_candidate (
    candidate_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    period        TEXT NOT NULL,
    member_a      TEXT NOT NULL,
    member_b      TEXT NOT NULL,
    similarity    REAL NOT NULL,
    evidence      TEXT NOT NULL
);

CREATE TABLE directory_release (
    release_id     TEXT PRIMARY KEY,                 -- the period, e.g. 2026-11
    period         TEXT NOT NULL,
    stage          TEXT NOT NULL CHECK (stage IN ('frozen', 'rendered', 'verified', 'published', 'rolled-back')),
    snapshot_hash  TEXT NOT NULL,
    approved_by    TEXT NOT NULL,
    pdf_count      INTEGER NOT NULL DEFAULT 0,
    manifest_hash  TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL
);
