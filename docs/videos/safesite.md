# safesite - transcript

Length 136 s.

- **00:00** SafeSite Compliance Cycle. A quarterly safety-return cycle - reminders, checks, escalations and two Word reports - with nothing sent and no final overwritten.
- **00:12** Scene 1. Twelve facilities, four coordinators, a due date and a reminder calendar. On 1 December, fourteen days before the 15 December deadline.
- **00:25** Scene 2. Six returns arrive two weeks out. Three break a rule; each gets a correction draft. The rest get a T-14 reminder. A serious finding with no evidence, totals that do not match, and a severity that does not exist.
- **00:43** Scene 3. Three days out: the corrections come back and pass. Running the same day again drafts nothing new. Each reminder is recorded once per facility and kind, so the same reminder is never drafted twice.
- **00:59** Scene 4. Past the deadline, two facilities are missing. Escalations go to the coordinator with the safety lead copied, and finals are refused. Yes - drafts, marked incomplete. Finals wait.
- **01:15** Scene 5. The late returns arrive and are accepted as late. The safety lead approves; a second approval overwrites nothing. No. They are read-only and a second approval reports ALREADY FINAL.
- **01:30** Scene 6. The four folders kept apart: working, QA, final and outbox. No. Fourteen drafts wait in the outbox.
- **01:42** The Workshop and Studio report, approved.
- **01:48** The Warehouse and Depot variant is organised around open actions.
- **01:54** A correction request: the exact problem, drafted, never sent.
- **02:01** What this run showed: Each bad return refused with its reason. Reminders never duplicated, never sent. No final until every return was in. An approved final is never overwritten.

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
