# CivicWorks Automation Lab

[![tests](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml)

**Eight tested data pipelines that catch bad data before it is published, ask a person when a rule cannot
decide, and prove what they did.**

Most data problems are not hard queries - they are a wrong number that gets published, a job that "succeeds"
with nothing in it, or two systems that quietly disagree. Each pipeline here takes invented data with planted
problems and shows how to stop exactly that.

### See it - nothing to install

**[The website](https://data-dl.github.io/civicworks-automation-lab/)** has three ways in:

- **Click through a pipeline's flow.** Every step in plain words, with its real code and the database rule it
  relies on explained part by part. ([MasterRecord](https://data-dl.github.io/civicworks-automation-lab/p/masterrecord.html#flow))
- **Remove a safeguard.** Each pipeline has one protection you can switch off to see exactly what goes wrong
  without it - recorded from the real code. ([OpenBadge](https://data-dl.github.io/civicworks-automation-lab/p/openbadge.html#switch))
- **[For hiring managers](https://data-dl.github.io/civicworks-automation-lab/hiring.html):** what a data analyst,
  analytics engineer or data engineer is expected to know, and where each is shown.

Each pipeline page also has a narrated video, a scene-by-scene replay, experiments that change the data, and
the pipeline's real database to query with SQL in the browser.

| | pipeline | what it does | safeguard you can switch off | tests |
|---|---|---|---|---|
| 1 | [Atlas License Directory](atlas-license-directory/) | Four source catalogs into twelve verified PDF directories | the editor's sign-off | 12 |
| 2 | [OpenBadge Registry Publisher](openbadge-registry-publisher/) | A public JSON registry that goes live only after it is fetched back and matched | the check after upload | 14 |
| 3 | [Regional Programs Analytics](regional-programs-analytics/) | Quarterly Excel reports that refuse approval while data is incomplete | the blocking checks | 11 |
| 4 | [LedgerGuard Data Quality](ledgerguard-data-quality/) | Daily export QA that never mistakes an empty file for success | the row-count proof | 13 |
| 5 | [SafeSite Compliance Cycle](safesite-compliance-cycle/) | Deadlines, return checks, escalations and two Word reports | the return checks | 11 |
| 6 | [MasterRecord Steward](masterrecord-steward/) | Field-level precedence across three feeds; a person decides the rest | holding disagreements for a person | 16 |
| 7 | [ReconcileHub](reconcilehub/) | Access-roster reconciliation that never merges people on a guess | review before approval | 16 |
| 8 | [OpsPilot Control Center](opspilot-control-center/) | Runs the others in order, with approvals, checkpoints and an append-only log | approval for publishing steps | 15 |

**108 tests**, plus 15 for the Lab. On every push GitHub installs everything from scratch on Ubuntu and
Windows and runs every test and every demo.

### Run it - one command

```bash
git clone https://github.com/data-dl/civicworks-automation-lab
cd civicworks-automation-lab
python start.py          # Python 3.11+; on Windows you can double-click "Start CivicWorks Lab.cmd"
```

It creates a private environment in `.venv`, installs the eight pipelines, and opens the **CivicWorks Lab** in
your browser (local only). In the Lab everything runs live on your machine: switch a safeguard off and the real
pipeline runs without it; pause a run between scenes and change the data yourself; query each database with SQL.

### What every pipeline does the same way

- **Checks before outputs.** Blocking findings stop the run and name the record; advisory ones are reported.
- **People decide what a rule cannot.** Conflicts, near-matches and publishing wait for a named person.
- **Two layers of rules.** The code checks the data, and the database enforces keys and allowed values too.
- **Nothing good is overwritten.** Build, verify, then swap in one step; reruns change nothing; rollback re-checks.
- **Evidence.** Every run writes a manifest with fingerprints of what it read and wrote.

### Found by experimenting

Running the experiments against the real code found real defects, each now fixed with a test: a badge with an
unknown type vanished silently from a public release because of an inner join; a name that drifted under the
same member id passed unreported; a report step crashed when a quarter was never approved; and atomic folder
swaps could fail on Windows while a virus scanner briefly held a new file.

### Repository layout

```
<eight project folders>/   each its own package, migrations, tests, README and data dictionary
start.py                   one-command setup and launch
lab/                       the CivicWorks Lab: flows, safeguard switches, guided runs, experiments, SQL console
learn/                     plain-language content: guides, flows, safeguards, experiments, SQL questions, hiring guide
docs/                      the website (GitHub Pages), with recorded runs and databases for the browser
tools/                     recorders for the website, the video maker, the site builder
```

Everything in this repository is public. Interview practice notes are kept outside it.

### How this was built

An AI coding assistant wrote most of the code and documentation to my design. I decided what each pipeline had
to do, which mistakes it had to catch, where a person must approve, and what the tests had to prove, and I
reviewed the results. Nothing is claimed without a test anyone can run. This is an original fictional
demonstration: no real organisation's data, code or systems are in it.

MIT licensed, per project.
