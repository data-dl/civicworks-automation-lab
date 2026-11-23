# SafeSite Compliance Cycle - transcript

Video length 102 s. Real demo run 2.0 s; 11 passed.

- **00:00** SafeSite Compliance Cycle. A quarterly safety-return cycle: reminders, checks, escalations and two Word reports, with nothing sent and no final overwritten.
- **00:07** 1. Plan 2026Q4: 12 facilities, 4 coordinators, returns due 2026-12-15. Twelve invented facilities and four coordinators. Returns are due 15 December; the calendar sets the reminder dates.
- **00:14** 2. Two weeks out: first returns arrive and are checked (as of 2026-12-01). Two weeks out, six returns arrive. Three are refused with the exact reason; correction requests and first reminders are drafted.
- **00:26** 3. Three days out: corrections come back (as of 2026-12-12). Three days out, the corrections come back and pass. Running the same day again drafts nothing new.
- **00:37** 4. Past the deadline: escalate what is missing (as of 2026-12-18). Past the deadline, two facilities are overdue. Escalations copy the safety lead, and final reports are refused while returns are missing.
- **00:48** 5. Late returns arrive; the safety lead approves. The late returns arrive and are marked late. The safety lead approves; a second approval overwrites nothing.
- **00:58** 6. Folders kept apart. Working drafts, QA material, approved finals and the outbox are kept in separate folders.
- **01:08** What it produced: workshop_2026Q4_FINAL.docx - page 1. The Workshop & Studio report, approved.
- **01:14** What it produced: depot_2026Q4_FINAL.docx - page 1. The Warehouse & Depot variant is organised around open actions.
- **01:21** What it produced: outbox/2026Q4/2026Q4-F03-correction-F03_v1.eml. A correction request: the exact problem, drafted, never sent.
- **01:28** What it produced: qa/2026Q4/QA_pack_2026Q4.md. The QA pack: every return, its file hash and its reminders.
- **01:34** What this run showed: Each bad return refused with its reason; Reminders never duplicated, never sent; No final until every return was in; An approved final is never overwritten. Tests: 11 passed.

## Terminal output (captured, unedited)

```
== 1. Plan 2026Q4: 12 facilities, 4 coordinators, returns due 2026-12-15
  12 assignments; calendar: working/2026Q4/calendar.csv

== 2. Two weeks out: first returns arrive and are checked (as of 2026-12-01)
  received: F01_v1.xlsx, F02_v1.xlsx, F03_v1.xlsx, F04_v1.xlsx, F05_v1.xlsx, F08_v1.xlsx
  accepted: F01 (on time), F02 (on time), F04 (on time)
  correction requested from F03: row 2: F03-O01 is S3 but has no evidence reference
  correction requested from F05: Totals says 4 S1 but the sheet lists 2
  correction requested from F08: row 3: severity 'HIGH' is not one of S1, S2, S3, S4
  correction drafts: F03, F05, F08
  T-14 drafts: F06, F07, F09, F10, F11, F12
  states: accepted 3, correction-requested 3, open 6

== 3. Three days out: corrections come back (as of 2026-12-12)
  received: F03_v2.xlsx, F05_v2.xlsx, F06_v1.xlsx, F07_v1.xlsx, F08_v2.xlsx, F09_v1.xlsx
  accepted: F03 (on time), F05 (on time), F06 (on time), F07 (on time), F08 (on time), F09 (on time)
  T-3 drafts: F10, F11, F12
  states: accepted 9, open 3
  same day, run again: 0 new drafts (reminders are never duplicated)

== 4. Past the deadline: escalate what is missing (as of 2026-12-18)
  received: F10_v1.xlsx
  accepted: F10 (on time)
  overdue drafts: F11, F12
  states: accepted 10, overdue 2
  final reports: BLOCKED - F11 is overdue, F12 is overdue
  drafts instead: workshop_2026Q4_draft.docx, depot_2026Q4_draft.docx

== 5. Late returns arrive; the safety lead approves
  received: F11_v1.xlsx, F12_v1.xlsx
  accepted: F11 (late), F12 (late)
  states: accepted 10, accepted-late 2
  reports: FINAL (approved by safety lead): workshop_2026Q4_FINAL.docx, depot_2026Q4_FINAL.docx
  approve again: ALREADY FINAL; nothing overwritten

== 6. Folders kept apart
  working/2026Q4: 3 file(s), e.g. calendar.csv
  qa/2026Q4: 1 file(s), e.g. QA_pack_2026Q4.md
  final/2026Q4: 2 file(s), e.g. depot_2026Q4_FINAL.docx
  outbox/2026Q4: 14 file(s), e.g. 2026Q4-F03-correction-F03_v1.eml
  Nothing is emailed: every reminder is an .eml draft in outbox/.
```
