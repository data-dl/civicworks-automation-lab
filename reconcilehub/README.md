# ReconcileHub

Part of **CivicWorks Automation Lab**, a set of independently built demonstrations on invented data.

*Foundry Commons* is a fictional federation of four maker spaces. Every month someone has to compare
three lists: who the door-access system actually lets in, who was approved last month, and who
registered this month. This project does that comparison, produces an import-ready workbook of the
changes, and refuses to guess about anyone it cannot match exactly.

## The problem

Roster reconciliation is where people get locked out or let in by mistake. An id exported as
` fc-17 ` instead of `FC-00017` looks like a stranger. A member whose id changed in the access system
looks like one person leaving and another arriving. A row with no id at all gets dropped. A new
registration turns out to be an existing member typed differently. Two different people share a name.
A matcher that "helpfully" merges near-matches will eventually merge the wrong two people.

## What it decides, and what it holds

| situation | outcome |
|---|---|
| same id in the system and the approvals, same role | unchanged |
| approved role differs from the system | **CHANGE ROLE** back to the approved role |
| registration with an id, not in the system | **ADD** |
| in the system, in neither approvals nor registrations | **REMOVE** |
| approved id missing, a new id with a near-identical name in the same space | **held**: possible id change |
| a system row with no usable id | **held**: missing id, with a suggested member |
| a registration with no id that looks like an existing member | **held**: possible duplicate |
| two different ids with the same name | kept apart, noted |

Held cases carry the suggestion and a confidence (string similarity on normalised names). A reviewer
records *same-person*, *different-person* or *exclude* with their name. Only then does a same-person
id change become **RENAME ID**, a missing id become **FIX ID**, and so on. Different-person restores
the old member and removes the new id.

Identifiers are normalised (trimmed, upper-cased, zero-padded) for matching; the raw value is always
stored next to the normalised one.

## Approval

`commit` is blocked while any case is held and drafts a note to the space admins instead. Once
everything is decided it writes `snapshots/<cycle>/v1/approved_roster.csv`, an import workbook
(Import, Reviewed cases, Approved roster), and a change report. The approved roster is hashed:

- same inputs and decisions again: **NOTHING NEW**, nothing written;
- different result after approval: **REFUSED** unless `--supersede REASON`, which writes `v2` beside
  `v1` and records the reason.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
python -m reconcilehub demo --out build/demo
python -m pytest                                  # 15 tests
```

Step by step: `init`, `reconcile`, `decide --decisions file.csv`, `commit --approve ROLE`.

## Tests

15 tests: five id-normalisation cases; names normalise without losing meaning; exact matches decided
and the rest held, with nothing added or removed for anyone in a held case; same names kept apart;
commit blocked while held, with a draft to admins; same-person decisions become RENAME and FIX;
different-person restores the old member; approval writes the snapshot, workbook and report; re-runs
are idempotent and changes need supersede; bad decision lines are reported; the demo runs.

## How this was built

The author set the problem, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository.
Every member, space and name is invented.

## License

MIT.
