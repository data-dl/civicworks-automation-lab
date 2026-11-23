# MasterRecord Steward

Part of **CivicWorks Automation Lab**, a set of independently built demonstrations on invented data.

The fictional *Guild of Joiners & Finishers* keeps one master workbook of its certified workshops.
Each month three feeds describe the same workshops: the guild registry (authoritative for some
fields), the contract system, and site inspections. They do not always agree. This project decides,
field by field, what the feeds justify, holds anything it cannot justify for a person, and writes
only approved decisions back into the master without disturbing anything else in it.

## The problem

Master data goes wrong in two ways: a system overwrites a good value with a worse one because the
last feed to arrive wins, or a person edits the master by hand and nobody can say why a value
changed. Either way the history is lost. And spreadsheets have their own trap: rewrite one and you can
silently drop a tab, a note, or the reference rows someone put at row 500.

## Precedence, field by field

`masterrecord/precedence.yaml` is the whole rulebook (invented rules):

| field | sources, most trusted first | authority | if nothing says | allowed |
|---|---|---|---|---|
| certification_class | registry, contract | registry | HOLD as UNKNOWN | Journeyman, Master, Fellow, **none** |
| participation_status | registry | registry | HOLD as UNKNOWN | active, paused, lapsed |
| network_affiliation | contract, registry | - | keep the master value | four networks or independent |
| workshop_type | registry, site, contract | - | HOLD | five types; *retail showroom* is out of scope |
| inspection_zone | registry, site | - | fill from the postcode map **only if the master is blank** | Z1-Z5 |

- **An authority wins** and the disagreeing sources are recorded next to the decision, not used.
- **No authority and a disagreement: HOLD.** The system never picks between two credible values.
- **Unknown is not ineligible.** No certification anywhere is UNKNOWN (held); `none` is a real value
  meaning not certified.
- **Out of scope is excluded with a reason**, and the row stays in the master marked `excluded`.
- **Duplicate feed rows add nothing** (a unique key on each assertion).

## The cycle

```mermaid
flowchart LR
    F[registry / contract / site feeds] --> A[assertions<br/>one row per source and field]
    A --> R{precedence matrix}
    R --> C[changes to approve]
    R --> H[holds to decide]
    R --> X[exclusions]
    C & H & X --> Q[review queue .xlsx<br/>+ decisions template]
    Q --> D[decisions.csv<br/>role + rationale per line]
    D --> P{apply}
    P -- dry run --> V[cells that would change]
    P -- --apply --> B[verified backup -> write -> prove every<br/>other cell unchanged -> atomic swap]
```

Apply refuses a decision without an approver role and a rationale, an "approve" on a hold, an
approval that alters the proposed value, and a chosen value outside the vocabulary. Each decision is
hashed: applying the same decisions file twice changes nothing. Every write adds a dated *Changes* tab
(old value, new value, proposal, role, rationale), leaves earlier *Changes* tabs alone, and is
recorded with the master's new SHA-256. A hold a person has settled does not come back next run.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
python -m masterrecord demo --out build/demo
python -m pytest                                   # 16 tests
```

Step by step: `init`, `propose`, fill in `review/decisions_<cycle>.csv`, `apply --decisions <file>`
(dry run), then `apply --decisions <file> --apply`.

## Tests

16 tests: authority wins and the disagreement is recorded; no authority means hold; unknown differs
from ineligible; values outside the vocabulary hold; the fallback only fills a blank; every planted
case is found (4 holds, 5 changes, 1 exclusion, duplicate feed rows ignored); a dry run writes
nothing; apply changes only decided cells, keeps the reference rows at row 500, the earlier Changes
tab and undecided rows; applying twice changes nothing; decided holds do not return; five kinds of bad
decision are refused with nothing written; the demo runs.

## Limits

openpyxl rewrites the workbook: formatting and values survive, but charts, images and macros would
not. The preservation check compares every cell value of every existing sheet, so a lost value is
caught; lost drawings are not. A real deployment would need a library or a desktop step that
preserves those.

## How this was built

The author set the problem, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository.
Every guild, workshop and value is invented.

## License

MIT.
