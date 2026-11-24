# CivicWorks Automation Lab

[![tests](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml)

**Reliable automation, from messy inputs to verified outputs.**

Eight data pipelines for invented organisations. Each one takes data with deliberately planted problems,
catches them, stops where a person has to decide, and leaves evidence of everything it did.

**[Open the presentation site](https://data-dl.github.io/civicworks-automation-lab/)** - nothing to install:

- a two-minute narrated overview, and a walkthrough of every pipeline replayed from a real run
- **experiments**: break the data on purpose and see only the lines of output the change made different
- **query the data**: each pipeline's real database opens in your browser, with SQL questions to try
- the exact rows and cells each step changed, the rules, the data model, and why each design choice was made
- **[for hiring teams](https://data-dl.github.io/civicworks-automation-lab/roles.html)**: what it shows for data engineer,
  analytics engineer and data analyst roles, with links to the code

| | pipeline | what it does | tests |
|---|---|---|---|
| 1 | [Atlas License Directory](atlas-license-directory/) | Four source catalogs into twelve verified PDF directories: rule registry, approval, frozen snapshot, checkpoint resume, atomic publish, rollback | 12 |
| 2 | [OpenBadge Registry Publisher](openbadge-registry-publisher/) | A public JSON registry that only goes live after it is fetched back over HTTP and matched by hash | 14 |
| 3 | [Regional Programs Analytics](regional-programs-analytics/) | Quarterly Excel reports with live formulas that refuse approval while data is incomplete | 11 |
| 4 | [LedgerGuard Data Quality](ledgerguard-data-quality/) | Daily export QA that never mistakes an empty or reshaped file for success; restorable archives | 13 |
| 5 | [SafeSite Compliance Cycle](safesite-compliance-cycle/) | Deadline reminders, return checks, escalations and two Word reports; nothing sent, no final overwritten | 11 |
| 6 | [MasterRecord Steward](masterrecord-steward/) | Field-level precedence across three feeds; holds for people; Excel write-back that proves nothing else moved | 16 |
| 7 | [ReconcileHub](reconcilehub/) | Access-roster reconciliation that suggests near-matches and never merges people on a guess | 16 |
| 8 | [OpsPilot Control Center](opspilot-control-center/) | Orchestrates the others through a fixed tool registry with approvals, checkpoints and an append-only log | 15 |

**108 tests** (plus 11 for the Lab). GitHub Actions installs all eight projects on fresh Ubuntu and Windows
machines, lints them, runs every test suite and every demo, and runs the one-command setup below from
scratch, on each push.

## Run it yourself - one command

With Python 3.11 or newer:

```bash
git clone https://github.com/data-dl/civicworks-automation-lab
cd civicworks-automation-lab
python start.py
```

`start.py` creates a private environment in `.venv`, installs the eight pipelines and the Lab, and opens
the **CivicWorks Lab** in your browser. Run it again any time; it skips what is done. `python start.py --check`
also runs every test and demo first. On Windows you can double-click `Start CivicWorks Lab.cmd`.

**The CivicWorks Lab** is a local web app (127.0.0.1 only) for learning the pipelines by using them:

- **Guided run** - the real demo, paused before each scene. It explains what is about to happen and asks
  you to predict; afterwards it shows the output, the exact rows and cells that changed, and every record
  the output names traced back to its input row. Between scenes you can **change the data** yourself -
  edit any input file or run SQL - and watch the pipeline react.
- **Experiments** - one click runs a normal run and a changed run side by side and shows only what differs.
- **Query the data** - a SQL console on the run's database, with example questions that each teach one idea
  (joins, CTEs, window functions, anti-joins, date arithmetic).
- Every output opens in the page: spreadsheets with their formulas, Word reports, PDF pages, JSON, databases.
- Plain-language concepts, a glossary on hover, interview practice and flashcards.

To run one pipeline by hand: `cd atlas-license-directory && python -m atlas demo` (any project, from its
own folder), and `python -m pytest` for its tests.

## What every pipeline does the same way

- **Invented data from a fixed seed,** with known planted problems, so every result can be checked.
- **Checks before outputs.** Blocking findings stop the run and name the record; advisory ones are reported.
- **People decide what a rule cannot.** Conflicts, near-matches and publishing wait for a named role.
- **Nothing good is overwritten.** Versions sit side by side; reruns change nothing; rollback re-hashes first.
- **Evidence.** Run manifests with SHA-256 fingerprints of inputs and outputs, seeds and verdicts.
- **Drafts, never sends.** Every message is an `.eml` draft to an example.org address.

## Found by experimenting

The experiments are not only for show. Running them against the real code found three real defects, each
now fixed with a test: a badge with an unknown type that vanished silently from a public release because of
an inner join (it now blocks the release and names the badge); a name that drifted under the same member id
and passed unreported (now noted for a person); and a report step that crashed when a quarter was never
approved. LedgerGuard also stopped storing absolute file paths in its archive index.

## Repository layout

```
<eight project folders>/   each its own package, migrations, tests, README and data dictionary
start.py                   one-command setup and launch
lab/                       the CivicWorks Lab (local app): guided runs, experiments, SQL console
learn/                     plain-language content: guides, experiments, SQL questions, glossary, interview notes
docs/                      the presentation site (GitHub Pages): videos, recorded runs, databases for the browser
tools/                     videos from real runs, recorders for the site's replays and experiments, site builder
```

## How this was built

The author set the problems, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository. This is
an original fictional demonstration: no real organisation's data, code or systems are in it.

MIT licensed, per project.
