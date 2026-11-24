# atlas - transcript

Length 189 s.

- **00:00** Atlas License Directory. A monthly printed directory that is checked, frozen, printed, verified and published - and can be rolled back.
- **00:11** Scene 1. Four separate files arrive, as they would from four different systems. One example of every problem the rules know about has been planted. Six. The missing venue token and the near-duplicate name are advisory: reported, not blocking. The repeated row is simply collapsed.
- **00:31** Scene 2. Every file is fingerprinted and counted, values are cleaned, and the rulebook runs. Each blocking finding names the record and the reason. No. Six blocking findings stop the run at the check stage. The QA summary is written instead.
- **00:49** Scene 3. The editor fixes the sources. This time the checks pass - but freezing needs a named person's approval, and nobody has given it. The approval gate. Clean data is necessary but not sufficient; a person must sign off before printing.
- **01:07** Scene 4. With approval the snapshot is frozen and twelve PDFs are printed into staging. Then the process is stopped on purpose, before anything is checked or published. No. Publishing only happens after verification, and the files are still in staging.
- **01:26** Scene 5. Resume reads the checkpoints. Stages whose output still has the same fingerprint are skipped; the remaining ones run, each PDF is verified, and the set is published in one step. Only verify and publish. Check, freeze and render are proven done by their hashes.
- **01:46** Scene 6. December's data arrives with three new listings and two withdrawn. It goes through the same line and is published, with a report of what changed. Nothing. It stays in published/2026-11, untouched; only the pointer moves to December.
- **02:06** Scene 7. A problem is reported with December. Rollback re-checks every November file against its manifest and points readers back at November. No. It is kept; only the pointer changes. And if any November file had been altered, rollback would refuse.
- **02:25** The contents page: every entry is a link, and every page number was planned before drawing.
- **02:33** A craft section: each listing printed from the frozen snapshot.
- **02:39** The QA summary: every finding with its rule, records and fix.
- **02:46** December compared with November: what was added and withdrawn.
- **02:52** What this run showed: Six bad records blocked, each one named. Nothing printed before a named sign-off. A crash mid-print resumed without redoing work. Every PDF verified; rollback re-hashes first.

## Terminal output (captured, unedited)

```
== 1. Four source catalogs arrive, with problems planted
  150 members, 48 studios, 150 endorsements, 413 listing rows (seed 20261123); four separate CSV catalogs
    planted duplicate_member_id: M0042
    planted near_duplicate_name: M0101 / M0151
    planted orphaned_studio: S019
    planted missing_venue_token: S023
    planted expired_endorsement: M0007
    planted invalid_date: E0012
    planted unknown_craft: E0016
    planted contradictory_audience: M0018
    planted repeated_listing_row: M0002 public

== 2. Ingest, normalise and check: the rule registry blocks the release
  ingest: every file hashed and counted; 1 repeated listing row(s) collapsed by their key (member, studio, edition)
  150 craft spellings mapped to 12 codes; phone numbers put in one format
  check: 6 blocking finding(s); see qa/2026-11/qa_summary.html
  6 blocking, 2 advisory findings:
    [x] duplicate_member_id: M0042 is both 'Elin Kettlewell' and 'Joss Rookfield'
    [x] orphaned_studio: S019 is in district 'NM', which does not exist
    [-] missing_venue_token: S023 has no venue token
    [x] expired_endorsement: M0007's endorsement E0007 ends 2026-10-31, before the 2026-12-01 edition
    [x] invalid_dates: E0012: 2026-04-06 to 2027-02-30 is not a real date range
    [x] unknown_craft: E0016: craft 'Glasblowing' matches no known craft
    [x] contradictory_audience: M0018 is placed in the public edition but did not opt in
    [-] possible_duplicate_person: 'Quill Oakhollow' (M0101) and 'Quill Oakhollo' (M0151) are 97% alike - review, never merged
  verdict: STOPPED at check - nothing frozen, nothing printed; QA summary in qa/2026-11/

== 3. The directory editor fixes the sources; the checks pass
  fixed: removed second M0042 (Joss Rookfield): it belongs to another person and needs its own id
  fixed: S019: district NM corrected to LM
  fixed: E0007: renewal recorded, valid to 2028-10-31
  fixed: E0012: 2027-02-30 corrected to 2027-02-28
  fixed: E0016: craft spelling corrected
  fixed: withdrew 1 public listing(s) for people who did not opt in
  freeze: checks pass; a directory editor must approve before the snapshot is frozen (--approve ROLE)
  verdict: STOPPED at freeze - checks pass, but no one has signed off

== 4. Sign-off freezes a snapshot; printing starts - and the machine stops
  freeze: snapshot frozen read-only after the directory editor approved
  render: 12 PDFs (4 districts x 3 editions) written to staging - not yet published
  !! process stopped after render

== 5. Resume: finished stages are skipped, every PDF is verified, then published
  check: done earlier - checkpoint verified by hash, not repeated
  freeze: done earlier - checkpoint verified by hash, not repeated
  render: done earlier - checkpoint verified by hash, not repeated
  verify: all 12 PDFs verified: page counts, contents links, index last and linked, bookmarks, footers
  publish: published/2026-11/ is now current; previous: none; changes: first release
  verdict: PUBLISHED

== 6. Next month: a new release, compared with the last one
  December sources: 3 listings added, 2 withdrawn
  1 repeated listing row(s) collapsed by their key (member, studio, edition)
  151 craft spellings mapped to 12 codes; phone numbers put in one format
  check: no blocking findings (2 advisory)
  freeze: snapshot frozen read-only, sha256 718912904ee2, approved by directory editor
  render: 12 PDFs rendered into staging/2026-12/ (not yet published)
  verify: all 12 PDFs verified: page counts, contents links, index last and linked, bookmarks, footers
  publish: published/2026-12/ is now current; previous: 2026-11; changes: 3 added, 2 withdrawn (CHANGES.md)
  verdict: PUBLISHED

== 7. A problem is reported: roll back to November
  rollback to 2026-11: OK - CURRENT now points at 2026-11 (all 12 files re-hashed); 2026-12 kept, not deleted
  readers now get: 2026-11; published/ still holds 2026-11 and 2026-12
```
