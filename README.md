# CivicWorks Automation Lab

[![tests](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/data-dl/civicworks-automation-lab/actions/workflows/tests.yml)

**Reliable automation, from messy inputs to verified outputs.**

Eight data pipelines for invented organisations. Each one takes data with deliberately planted problems,
catches them, stops where a person has to decide, and leaves evidence of everything it did.

**[Open the presentation site](https://data-dl.github.io/civicworks-automation-lab/)** - a two-minute
overview video, a narrated walkthrough of every pipeline replayed from a real run, the real outputs
(PDFs, Excel, Word, JSON), each database's structure, and the reasoning behind every design choice.

| | pipeline | what it does | tests |
|---|---|---|---|
| 1 | [Atlas License Directory](atlas-license-directory/) | Four source catalogs into twelve verified PDF directories: rule registry, approval, frozen snapshot, checkpoint resume, atomic publish, rollback | 12 |
| 2 | [OpenBadge Registry Publisher](openbadge-registry-publisher/) | A public JSON registry that only goes live after it is fetched back over HTTP and matched by hash | 13 |
| 3 | [Regional Programs Analytics](regional-programs-analytics/) | Quarterly Excel reports with live formulas that refuse approval while data is incomplete | 11 |
| 4 | [LedgerGuard Data Quality](ledgerguard-data-quality/) | Daily export QA that never mistakes an empty or reshaped file for success; restorable archives | 13 |
| 5 | [SafeSite Compliance Cycle](safesite-compliance-cycle/) | Deadline reminders, return checks, escalations and two Word reports; nothing sent, no final overwritten | 11 |
| 6 | [MasterRecord Steward](masterrecord-steward/) | Field-level precedence across three feeds; holds for people; Excel write-back that proves nothing else moved | 16 |
| 7 | [ReconcileHub](reconcilehub/) | Access-roster reconciliation that suggests near-matches and never merges people on a guess | 15 |
| 8 | [OpsPilot Control Center](opspilot-control-center/) | Orchestrates the others through a fixed tool registry with approvals, checkpoints and an append-only log | 15 |

**106 tests.** GitHub Actions installs all eight projects on fresh Ubuntu and Windows machines, lints
them, runs every test suite and every demo on each push.

## Try it

```bash
git clone https://github.com/data-dl/civicworks-automation-lab
cd civicworks-automation-lab
python -m venv .venv && .venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -e "./atlas-license-directory[dev]" -e "./openbadge-registry-publisher[dev]" \
    -e "./regional-programs-analytics[dev]" -e "./ledgerguard-data-quality[dev]" \
    -e "./safesite-compliance-cycle[dev]" -e "./masterrecord-steward[dev]" -e "./reconcilehub[dev]" \
    -e "./opspilot-control-center[dev]" -e ./lab
cd atlas-license-directory && python -m atlas demo      # any project: run its demo from its own folder
```

**The CivicWorks Lab** (`python -m civicworks_lab`) is a local web app that runs any pipeline one scene at
a time: before each scene it explains what is about to happen and asks you to predict; after it, it shows
the output, every file that changed, and the exact rows and cells that changed (with each record the output names traced back to its input row), and opens any spreadsheet, Word report, PDF
page or database right in the page. It also holds the concepts, a glossary and question flashcards.

## What every pipeline does the same way

- **Invented data from a fixed seed,** with known planted problems, so every result can be checked.
- **Checks before outputs.** Blocking findings stop the run and name the record; advisory ones are reported.
- **People decide what a rule cannot.** Conflicts, near-matches and publishing wait for a named role.
- **Nothing good is overwritten.** Versions sit side by side; reruns change nothing; rollback re-hashes first.
- **Evidence.** Run manifests with SHA-256 fingerprints of inputs and outputs, seeds and verdicts.
- **Drafts, never sends.** Every message is an `.eml` draft to an example.org address.

## Repository layout

```
<eight project folders>/   each its own package, migrations, tests, README and data dictionary
lab/                       the CivicWorks Lab (local app)
learn/                     plain-language content: per-pipeline guides, glossary, big ideas, interview notes
docs/                      the presentation site (GitHub Pages), videos and rendered outputs
tools/                     make_videos.py (narrated videos from real runs), build_site.py, narrate.py
```

## How this was built

The author set the problems, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository. This is
an original fictional demonstration: no real organisation's data, code or systems are in it.

MIT licensed, per project.
