# OpenBadge Registry Publisher - transcript

Video length 102 s. Real demo run 4.3 s; 13 passed.

- **00:00** OpenBadge Registry Publisher. Publishing a public data file so that bad records and bad uploads never reach the people who import it.
- **00:07** 1. Seed a synthetic academy. Every learner, badge and date comes from a fixed seed, so the same academy can be rebuilt exactly.
- **00:13** 2. First release: validate, publish, verify over HTTP, then move the pointer. The registry is written as a dated file, fetched back over HTTP and matched by hash. Only then does 'latest' point to it.
- **00:22** 3. Bad data arrives: a duplicated badge and an impossible expiry date. Two bad records are planted. The release is blocked, each finding names the record, and nothing is published.
- **00:33** 4. Steward fixes the data; this time the upload is cut off half way. The data is fixed, but the upload is cut off half way. The hash check catches it, so consumers stay on the last good release and a ticket opens.
- **00:44** 5. Re-run the release; the catalogue imports it a day later. The rerun publishes. The outside catalogue imports a day later: pending, then accepted, tracked apart from the technical result.
- **00:55** 6. Roll back: a release that never verified is refused, the last good one is accepted. Rollback refuses the release that never verified and returns to the last one that did, after checking it over HTTP.
- **01:04** 7. Release history. Every attempt stays on record, including the blocked and failed ones.
- **01:15** What it produced: site/latest.json. The pointer consumers read: which release, its hash and record count.
- **01:22** What it produced: tickets/T001-R0003-verify-failed.md. The correction ticket opened by the cut-off upload.
- **01:28** What it produced: runs/R0004/manifest.json. Every release leaves a manifest: stages, hashes, seed, versions and the verdict.
- **01:35** What this run showed: Bad records blocked with the record named; A damaged upload never became 'latest'; Rollback only to a release proven good; Every attempt on record. Tests: 13 passed.

## Terminal output (captured, unedited)

```
== 1. Seed a synthetic academy
  120 learners, 305 badges, 12 badge types (seed 20261123)

== 2. First release: validate, publish, verify over HTTP, then move the pointer
  release R0001: PUBLISHED  (268 badges, sha256 f3cd1f10d538)
    pointer moved nothing -> R0001
  catalogue import: accepted (imported 268 badges)

== 3. Bad data arrives: a duplicated badge and an impossible expiry date
  planted: duplicate LSA-48AAC4DF, invalid date on LSA-B8388898
  release R0002: BLOCKED  (269 badges, sha256 86da833ae36c)
    [x] valid_dates: LSA-B8388898: not a real date (2026-08-13 / 2019-02-30)
    [x] unique_badge_id: LSA-48AAC4DF appears 2 times
    2 blocking finding(s); nothing published, pointer stays on R0001

== 4. Steward fixes the data; this time the upload is cut off half way
  repaired: {'duplicates_removed': 1, 'dates_fixed': 1}; new approvals: 12
  release R0003: VERIFY-FAILED  (280 badges, sha256 e95ad2d3d43d)
    [-] release_delta: 12 badges join the registry
    verification failed: served file hash 9aba5d7b80df != built e95ad2d3d43d; pointer stays on R0001; ticket T001-R0003-verify-failed.md

== 5. Re-run the release; the catalogue imports it a day later
  release R0004: PUBLISHED  (280 badges, sha256 13fe9832a121)
    [-] release_delta: 12 badges join the registry
    pointer moved R0001 -> R0004
  catalogue import: pending (queued for the nightly import)
  catalogue import (next day): accepted (imported 280 badges)

== 6. Roll back: a release that never verified is refused, the last good one is accepted
  rollback to R0003: REFUSED - R0003 never verified (verify-failed); refusing
  rollback to previous: OK - pointer moved R0004 -> R0001 (verified by hash over HTTP)

== 7. Release history
  release  badges  technical      consumer     file    
  R0001       268  verified       accepted     present  <- latest
  R0002       269  blocked        not-checked  -        
  R0003       280  verify-failed  not-checked  present  
  R0004       280  verified       accepted     present  

  evidence: build/demo/runs/<release>/manifest.json, tickets in build/demo/tickets/
```
