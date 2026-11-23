# OpsPilot Control Center

Part of **CivicWorks Automation Lab**, a set of independently built demonstrations on invented data.

OpsPilot runs the other CivicWorks pipelines as one operation: it plans the order, runs each step,
checkpoints what finished, waits for a person before anything is published, picks up exactly where it
stopped after a crash, stops when a project's own checks say no, and refuses everything it has not
been given a contract for. It is built so that a planner - a rules engine here, a language model
later - can propose work without ever being able to do more than the registry allows.

## The problem

Orchestration is where automation acquires power: one process that can run everything. The risks
are the obvious ones. It runs a publish step nobody approved. It re-runs a step that already happened
and duplicates its effect. It loses its place after a crash. It accepts an instruction to run an
arbitrary command, or to write outside its folders. It quietly edits its own history. An AI agent in
the loop makes each of these easier to trigger by accident.

## How it is built

| part | what it does | file |
|---|---|---|
| tool registry | the only actions that exist: 10 typed contracts over the five projects' commands, each with inputs, an effect class (read / write / publish) and the output files that prove it ran | `opspilot/tools.yaml` |
| rules planner | turns a goal into steps from the registry; validated for unknown tools, unknown dependencies and cycles | `registry.py` |
| language-model planner | the same interface, **off by default** and not wired to any model; anything it proposed would pass the same validation | `registry.py` |
| release reviewer | a publish step runs only with an approval a person issued for that step of that run (`APR-0001`) | `executor.py` |
| data QA reviewer | reads each project's exit code: 0 done, 1 blocked by that project's own checks, anything else failed | `executor.py` |
| checkpoints | each finished step stores a SHA-256 of its declared outputs; on resume a step is skipped only if those files still hash the same | `executor.py` |
| narrator / documentation steward | one line per step, a next action, and `HANDOFF.md` for whoever picks the run up | `executor.py` |
| event log | every start, step, approval, refusal and crash; append-only, enforced by database triggers | `db/migrations/001_init.sql` |
| status page | a static, read-only HTML snapshot of runs, steps, approvals and events | `dashboard.py` |

Steps run as `python -m <project> ...` from an argument list (never a shell string), with no console
window, and with every input type-checked: workspaces must resolve inside `workspaces/`, quarters
look like `2026Q2`, roles are plain words.

## What the demo shows

```bash
python -m opspilot demo --out build/demo
```

| scene | what happens |
|---|---|
| 1 | the registry and the environment profile |
| 2 | the plan for `publish-cycle` in dependency order |
| 3 | write steps run; both publish steps stop at **awaiting-approval** |
| 4 | a person approves them (scoped tokens) |
| 5 | resume - the process "crashes" right after the badge release; the run is marked interrupted |
| 6 | resume again: six steps are skipped on verified checkpoints, the last one runs, **COMPLETE** |
| 7 | `roster-cycle`: the roster project refuses to approve with held cases, so the run is **BLOCKED** with a next action |
| 8 | refused: an unregistered command, a path outside the workspaces, a publish outside an approved run, a language-model plan, approving a non-publishing step, and erasing the event log (refused by the database) |
| 9 | the status page and handoff notes |

## Run it

OpsPilot drives the other five CivicWorks projects, so install them into the same environment:

```bash
pip install -e ../openbadge-registry-publisher -e ../regional-programs-analytics \
            -e ../masterrecord-steward -e ../reconcilehub -e ".[dev]"
python -m opspilot demo --out build/demo
python -m pytest            # 15 tests
```

## Tests

15 tests: every goal validates in dependency order; unknown tools and cycles are refused; inputs are
type-checked (path outside the workspaces, undeclared input, missing input, bad quarter, bad role);
the language-model planner is off by default; publish steps wait for a person; a crash is recorded and
resume re-runs only the step after it; the projects record the approver's role; a changed output makes
a checkpoint stale and the step re-runs; a project's own block stops the run with a handoff; direct
requests and history edits are refused and logged; the status page is built; the demo runs.

## How this was built

The author set the problem, the rules, the points where a person must decide, and the acceptance
tests, and reviewed the results. The code and most of the documentation were written with AI coding
assistance working to that design. Nothing here is claimed without a test in this repository.

## License

MIT.
