# openbadge - transcript

Length 148 s.

- **00:00** OpenBadge Registry Publisher. A public data file that only goes live after it has been fetched back and proven identical.
- **00:09** Scene 1. A generator invents 120 learners and about 300 badges from a fixed seed. Yes, byte for byte - that is what the seed and canonical JSON guarantee.
- **00:22** Scene 2. The first release passes every check, is uploaded, downloaded again and matched, and then the pointer moves. The catalogue imports it. After. The pointer only moves once the downloaded file matches the built one exactly.
- **00:40** Scene 3. Two bad records are planted: a duplicated badge and an impossible date. No. The release is blocked at validation, before anything is written to the site.
- **00:53** Scene 4. The data is fixed, but this time the upload is deliberately cut off half way. Still R0001. The hash mismatch stops the pointer, and a correction ticket opens.
- **01:07** Scene 5. The release is rerun and publishes. The catalogue's first check only queues it; the next day it accepts it. Yes. Technical verification and business acceptance are recorded separately.
- **01:23** Scene 6. Rollback is asked to go to the release that failed verification, then to the previous good one. Rolling back to R0003, which never verified. Rolling back to R0001 works after it is re-checked over HTTP.
- **01:41** Scene 7. The history shows every attempt, including the blocked and failed ones. So you can explain what happened and prove nothing bad was ever pointed at.
- **01:53** The pointer consumers read: which release, its hash and record count.
- **02:00** The correction ticket opened by the cut-off upload.
- **02:06** Every release leaves a manifest: stages, hashes, seed, versions, verdict.
- **02:14** What this run showed: Bad records blocked with the record named. A damaged upload never became 'latest'. Rollback only to a release proven good. Every attempt on record.

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
