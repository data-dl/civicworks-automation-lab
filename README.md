# CivicWorks Automation Lab

**Reliable automation, from messy inputs to verified outputs.**

Eight independently built demonstration pipelines for a set of invented organisations. Each one takes
synthetic data with deliberately planted problems, catches them, stops where a person has to decide,
and leaves evidence of everything it did. Every organisation, person, place and number here is
fictional; nothing comes from a real system.

| project | the fictional problem | outputs | tests | video |
|---|---|---|---|---|
| [Atlas License Directory](atlas-license-directory/) | a monthly printed directory, 4 districts x 3 audiences, that must never print a bad listing | 12 verified PDFs with linked contents and index, QA summary, change report | 12 | (coming) |
| [LedgerGuard Data Quality](ledgerguard-data-quality/) | daily export QA that never mistakes an empty file for success | exception workbook, dashboard, archived and restorable daily sets | 13 | (coming) |
| [OpenBadge Registry Publisher](openbadge-registry-publisher/) | publish a public badge registry so bad records and bad uploads never reach consumers | versioned JSON, pointer, tickets | 13 | [watch](videos/openbadge.mp4) |
| [Regional Programs Analytics](regional-programs-analytics/) | quarterly reports for 16 arts venues that refuse approval while data is incomplete | 3 Excel workbooks with formulas and a chart, review pack, draft emails | 11 | [watch](videos/regional.mp4) |
| [SafeSite Compliance Cycle](safesite-compliance-cycle/) | quarterly safety returns: reminders, checks, escalation, two report variants | 2 Word reports, QA pack, reminder drafts | 11 | [watch](videos/safesite.mp4) |
| [MasterRecord Steward](masterrecord-steward/) | master records from three feeds that disagree; hold what cannot be justified | review queue, versioned Excel master with a Changes tab | 16 | [watch](videos/masterrecord.mp4) |
| [ReconcileHub](reconcilehub/) | monthly access-roster reconciliation that never merges two people on a guess | import workbook, hashed roster snapshot, change report | 15 | [watch](videos/reconcilehub.mp4) |
| [OpsPilot Control Center](opspilot-control-center/) | one control room over the others that cannot exceed its contracts | checkpoints, approvals, append-only log, status page | 15 | [watch](videos/opspilot.mp4) |

106 tests in all. Each video replays a real run of that project's demo command (captured, not typed),
then shows the files it produced, rendered from the real outputs. Captions (`.vtt`) and a transcript
with the full captured terminal output (`.md`) sit beside each video.

## What every project does the same way

- **Synthetic data from a fixed seed,** with an answer to what was planted, so results can be checked.
- **Checks before outputs.** Blocking findings stop publication and name the record; advisory ones are
  reported.
- **People decide what a rule cannot.** Conflicts, near-matches and approvals are held for a named role.
- **Nothing is overwritten.** Releases, approved reports and snapshots are versioned; a second run with
  the same inputs changes nothing.
- **Evidence.** Run manifests with input and output SHA-256, seeds, versions and verdicts.
- **Drafts, never sends.** Every message is an `.eml` draft to an example.org address; there is no
  mail-sending code.

## Run everything

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ./openbadge-registry-publisher[dev] -e ./regional-programs-analytics[dev] \
    -e ./safesite-compliance-cycle[dev] -e ./masterrecord-steward[dev] -e ./reconcilehub[dev] \
    -e ./opspilot-control-center[dev] -e ./atlas-license-directory[dev] \
    -e ./ledgerguard-data-quality[dev]
cd openbadge-registry-publisher && python -m openbadge demo     # likewise in each project's folder
```

Run each demo from its own project folder: at the repository root the `reconcilehub/` folder would be
picked up instead of the installed `reconcilehub` package.

Each project's README explains its rules, its demo scenes and its tests. `tools/make_videos.py`
rebuilds the videos (Windows with Office, for the Excel and Word page renders).

## How this was built

The author set the problems, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository. This
is an original fictional demonstration: no real organisation's data, code or systems are in it.

## License

MIT, per project.
