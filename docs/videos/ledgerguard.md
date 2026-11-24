# ledgerguard - transcript

Length 129 s.

- **00:00** LedgerGuard Data Quality. Daily export checks that never mistake an empty file for success, with archives you can safely restore.
- **00:09** Scene 1. Three systems and an old desktop export, with five data problems planted for the checks to find. The desk app's export: it always says 'Export complete'.
- **00:23** Scene 2. Day one: every export proves usable, then the checks find each planted problem. Five: one depot class nobody may service, two incomplete items, one serial under two classes, one lapsed technician.
- **00:40** Scene 3. Day two: the desktop program reports success but writes no rows. Yes, marked stale, with the reason; the empty file is in quarantine.
- **00:53** Scene 4. Day three: an update renames a column in the export. No - all 120 rows are there. Only the column check catches it.
- **01:05** Scene 5. Day four is healthy. Yesterday's set moves into the archive with its manifest before today's replaces it. Three: the 23rd, 24th and 25th.
- **01:19** Scene 6. Restore is tried on an archive that someone edited, then on an intact one. It is kept too, in archive/<day>-replaced-by-restore.
- **01:30** The dashboard on the day the export columns changed: quarantined, with the reason.
- **01:38** The exception workbook: each job, rows expected and found, exceptions.
- **01:46** An archived day's manifest: every file's fingerprint, checked before any restore.
- **01:53** What this run showed: An empty or reshaped export never counted as success. Yesterday's good file kept, clearly marked stale. Every day archived with fingerprints. A tampered archive is refused.

## Terminal output (captured, unedited)

```
== 1. Three source systems and an old desktop export, with data problems planted
  registry.sqlite: 120 equipment items; roster.csv: 28 technicians; authorizations.csv: 81 authorisations; plus the desk app's Export button
  planted: a blank serial, a missing service date, one serial under two classes, a technician active with every authorisation lapsed, a depot class nobody may service

== 2. Day 1: all four exports proven usable, then checked for exceptions
  qualification_mapping    sqlite+csv ok           24/24  rows  1 exceptions
      5 SAW at Wharfside with nobody authorised
  attribute_completeness   desk-app   ok          120/120 rows  2 exceptions
      EQ-0010 missing serial
      EQ-0034 missing last service date
  category_overlaps        sqlite     ok          118/118 rows  1 exceptions
      serial SNACA14F2 is registered as CMP SAW
  active_eligibility       csv        ok           28/28  rows  1 exceptions
      T-007 at Wharfside is active with no valid authorisation
  published as one set: current/ holds four verified files, exceptions.xlsx and dashboard.html

== 3. Day 2: the desktop export 'succeeds' with no rows
  the desk app says 'Export complete' - but wrote only the header row
  qualification_mapping    sqlite+csv ok           24/24  rows  1 exceptions
  attribute_completeness   desk-app   QUARANTINED   0/120 rows  0 exceptions  - the file has a header but no rows; the source has 120
  category_overlaps        sqlite     ok          118/118 rows  1 exceptions
  active_eligibility       csv        ok           28/28  rows  1 exceptions
  kept yesterday's verified file for: attribute_completeness (marked stale)
  the previous verified set moved to archive/2026-11-23/ with its SHA-256 manifest

== 4. Day 3: the export's columns change
  after a desk app update, a column is renamed in its export
  qualification_mapping    sqlite+csv ok           24/24  rows  1 exceptions
  attribute_completeness   desk-app   QUARANTINED 120/120 rows  0 exceptions  - columns changed: missing ['serial_token'], unexpected ['serial_no']
  category_overlaps        sqlite     ok          118/118 rows  1 exceptions
  active_eligibility       csv        ok           28/28  rows  1 exceptions
  kept yesterday's verified file for: attribute_completeness (marked stale)
  the previous verified set moved to archive/2026-11-24/ with its SHA-256 manifest

== 5. Day 4: healthy again; yesterday's set is archived before it is replaced
  qualification_mapping    sqlite+csv ok           24/24  rows  1 exceptions
  attribute_completeness   desk-app   ok          120/120 rows  2 exceptions
  category_overlaps        sqlite     ok          118/118 rows  1 exceptions
  active_eligibility       csv        ok           28/28  rows  1 exceptions
  the previous verified set moved to archive/2026-11-25/ with its SHA-256 manifest
  archive/ now holds: 2026-11-23, 2026-11-24, 2026-11-25

== 6. Restore: a tampered archive is refused, an intact one comes back
  restore 2026-11-25 after someone edited a file in it: REFUSED - 1 archived file(s) no longer match their manifest (category_overlaps.csv); refusing
  restore 2026-11-23: OK - current is 2026-11-23 again (all 6 files re-hashed); the set it replaced is kept in archive/2026-11-26-replaced-by-restore
```
