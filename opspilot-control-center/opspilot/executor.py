"""Running a plan: checkpoints, approvals, project QA blocks, resume, and the event log.

Role-separated helpers, all deterministic:
    planner              builds the step order (registry.RulesPlanner)
    release reviewer     no publish step runs without a scoped approval a person issued
    data QA reviewer     reads each project's exit code: 0 done, 1 blocked by that project's own checks
    operations narrator  one plain sentence per step and a next action for the run
    documentation steward writes HANDOFF.md for whoever picks the run up next
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .db import connect, migrate
from .registry import Plan, Refused, RulesPlanner, Step, Tool, check_inputs, load_registry, validate_plan
from .runkit import atomic_write_text, guard, sha256_bytes, sha256_file, unique_dir, utc_now

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SimulatedCrash(Exception):
    """Stands in for the machine stopping half way through a run."""


@dataclass
class StepOutcome:
    step: str
    status: str
    note: str


@dataclass
class RunSummary:
    run_id: str
    state: str
    outcomes: list[StepOutcome] = field(default_factory=list)
    next_action: str = ""


class OpsPilot:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.workspaces = self.root / "workspaces"
        self.workspaces.mkdir(exist_ok=True)
        self.tools, self.goals = load_registry()
        self.planner = RulesPlanner(self.goals)
        self.con = connect(self.root / "ops.sqlite")
        migrate(self.con)

    # --- events -------------------------------------------------------------------------------------
    def event(self, run_id: str | None, kind: str, **payload) -> None:
        self.con.execute("INSERT INTO event_log (run_id, at, event_type, payload) VALUES (?, ?, ?, ?)",
                         (run_id, utc_now(), kind, json.dumps(payload, sort_keys=True)))
        self.con.commit()

    # --- planning -----------------------------------------------------------------------------------
    def plan(self, goal: str, planner=None) -> list[Step]:
        try:
            plan: Plan = (planner or self.planner).plan(goal)
            return validate_plan(plan, self.tools)
        except Refused as exc:
            self.event(None, "refused", what=f"plan {goal}", why=str(exc))
            raise

    def start(self, goal: str) -> str:
        steps = self.plan(goal)
        self.con.execute("INSERT OR IGNORE INTO pipeline VALUES (?, ?)", (goal, self.goals[goal]["description"]))
        for n, s in enumerate(steps, start=1):
            self.con.execute("INSERT OR IGNORE INTO stage VALUES (?, ?, ?, ?, ?)",
                             (goal, s.id, n, s.tool, self.tools[s.tool].effect))
        run_dir = unique_dir(self.root / "logs", f"{goal}-{utc_now()[:10]}")
        run_id = run_dir.name
        self.con.execute("INSERT INTO execution VALUES (?, ?, 'running', ?, ?)", (run_id, goal, utc_now(), utc_now()))
        self.con.commit()
        self.event(run_id, "run-started", goal=goal, steps=[s.id for s in steps])
        return run_id

    # --- approvals (a person's action; never called by the executor itself) --------------------------
    def approve(self, run_id: str, stage_id: str, role: str) -> str:
        goal = self._goal(run_id)
        stage = self.con.execute("SELECT * FROM stage WHERE pipeline_id = ? AND stage_id = ?",
                                 (goal, stage_id)).fetchone()
        if stage is None:
            raise Refused(f"run {run_id} has no step {stage_id}")
        if stage["effect_class"] != "publish":
            raise Refused(f"{stage_id} does not publish; it needs no approval")
        n = self.con.execute("SELECT COUNT(*) FROM authorization").fetchone()[0] + 1
        token = f"APR-{n:04d}"
        self.con.execute("INSERT INTO authorization VALUES (?, ?, ?, ?, ?)", (token, run_id, stage_id, role, utc_now()))
        self.con.commit()
        self.event(run_id, "approved", step=stage_id, role=role, token=token)
        return token

    # --- execution ----------------------------------------------------------------------------------
    def _goal(self, run_id: str) -> str:
        row = self.con.execute("SELECT pipeline_id FROM execution WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise Refused(f"no run {run_id}")
        return row[0]

    def _outputs_hash(self, tool: Tool, workspace: Path, params: dict) -> str | None:
        hashes = []
        for pattern in tool.outputs:
            path = workspace / pattern.format(**params)
            if not path.exists():
                return None
            hashes.append(f"{pattern}={sha256_file(path)}")
        return sha256_bytes("\n".join(hashes).encode())

    def _checkpoint(self, run_id: str, step: str, status: str, exit_code: int | None = None,
                    artifact: str = "") -> None:
        self.con.execute("INSERT INTO checkpoint VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(run_id, stage_id) DO UPDATE "
                         "SET status = excluded.status, exit_code = excluded.exit_code, "
                         "artifact_hash = excluded.artifact_hash, finished_at = excluded.finished_at",
                         (run_id, step, status, exit_code, artifact, utc_now()))
        self.con.commit()

    def run(self, run_id: str, crash_after: str | None = None) -> RunSummary:
        goal = self._goal(run_id)
        steps = self.plan(goal)
        summary = RunSummary(run_id, "running")
        status: dict[str, str] = {}
        self._set_state(run_id, "running")
        for s in steps:
            tool = self.tools[s.tool]
            workspace = self.workspaces / s.project
            cp = self.con.execute("SELECT * FROM checkpoint WHERE run_id = ? AND stage_id = ?",
                                  (run_id, s.id)).fetchone()
            params = {**s.params}
            if cp and cp["status"] == "done":
                auth = self._authorization(run_id, s.id)
                if auth and "role" in tool.inputs:
                    params["role"] = auth["role"]
                current = self._outputs_hash(tool, workspace, params) if tool.outputs else ""
                if current == cp["artifact_hash"]:
                    status[s.id] = "done"
                    note = ("checkpoint verified by hash; not re-run" if tool.outputs
                            else "done earlier in this run; not re-run")
                    summary.outcomes.append(StepOutcome(s.id, "done", note))
                    continue
                self.event(run_id, "checkpoint-stale", step=s.id)
            waiting = [d for d in s.after if status.get(d) != "done"]
            if waiting:
                status[s.id] = "waiting"
                self._checkpoint(run_id, s.id, "skipped")
                summary.outcomes.append(StepOutcome(s.id, "waiting", f"waits for {', '.join(waiting)}"))
                continue
            if tool.effect == "publish":
                auth = self._authorization(run_id, s.id)
                if auth is None and guard("publish-approval"):
                    status[s.id] = "awaiting-approval"
                    self._checkpoint(run_id, s.id, "awaiting-approval")
                    self.event(run_id, "approval-required", step=s.id, tool=s.tool)
                    summary.outcomes.append(StepOutcome(s.id, "awaiting-approval",
                                                        "publishes, so a person must approve it first"))
                    continue
                if "role" in tool.inputs:  # the project records who approved, in its own terms
                    params["role"] = auth["role"] if auth else "nobody"
            try:
                clean = check_inputs(tool, {"workspace": s.project, **params}, self.workspaces)
            except Refused as exc:
                self.event(run_id, "refused", step=s.id, why=str(exc))
                raise
            argv = [sys.executable, "-m", tool.module] + [a.format(**clean) for a in tool.argv]
            self.event(run_id, "step-started", step=s.id, tool=s.tool, effect=tool.effect)
            proc = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=900,
                                  creationflags=NO_WINDOW)
            log = self.root / "logs" / run_id / f"{s.id}.log"
            atomic_write_text(log, f"$ {' '.join(argv[1:])}\n\n{proc.stdout}\n{proc.stderr}")
            if proc.returncode == 0:
                artifact = self._outputs_hash(tool, workspace, clean) if tool.outputs else ""
                if artifact is None:
                    status[s.id] = "failed"
                    self._checkpoint(run_id, s.id, "failed", 0)
                    summary.outcomes.append(StepOutcome(s.id, "failed", "exit 0 but a declared output is missing"))
                    continue
                status[s.id] = "done"
                self._checkpoint(run_id, s.id, "done", 0, artifact)
                self.event(run_id, "step-done", step=s.id, artifact=artifact[:16])
                summary.outcomes.append(StepOutcome(s.id, "done", _last_line(proc.stdout)))
            else:
                kind = "blocked" if proc.returncode == 1 else "failed"
                status[s.id] = kind
                self._checkpoint(run_id, s.id, kind, proc.returncode)
                self.event(run_id, f"step-{kind}", step=s.id, exit_code=proc.returncode)
                summary.outcomes.append(StepOutcome(s.id, kind, f"exit {proc.returncode}: "
                                                    + _last_line(proc.stdout or proc.stderr)))
            if crash_after == s.id:
                self._set_state(run_id, "interrupted")
                self.event(run_id, "interrupted", after=s.id)
                raise SimulatedCrash(f"process stopped after {s.id}")
        states = set(status.values())
        summary.state = ("failed" if "failed" in states else "blocked" if "blocked" in states
                         else "awaiting-approval" if "awaiting-approval" in states else "complete")
        summary.next_action = self._next_action(run_id, summary)
        self._set_state(run_id, summary.state)
        self.event(run_id, "run-finished", state=summary.state)
        self._handoff(run_id, goal, summary)
        return summary

    def _authorization(self, run_id: str, stage_id: str) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM authorization WHERE run_id = ? AND stage_id = ?",
                                (run_id, stage_id)).fetchone()

    def _set_state(self, run_id: str, state: str) -> None:
        self.con.execute("UPDATE execution SET state = ?, updated_at = ? WHERE run_id = ?", (state, utc_now(), run_id))
        self.con.commit()

    def _next_action(self, run_id: str, summary: RunSummary) -> str:
        waiting = [o.step for o in summary.outcomes if o.status == "awaiting-approval"]
        blocked = [o for o in summary.outcomes if o.status in ("blocked", "failed")]
        if blocked:
            why = "its project's own checks stopped it" if blocked[0].status == "blocked" else "it failed"
            return (f"{blocked[0].step}: {why} - read logs/{run_id}/{blocked[0].step}.log, fix the cause in that "
                    f"project, then `opspilot run --resume {run_id}`")
        if waiting:
            return f"a person approves {', '.join(waiting)} (`opspilot approve`), then `opspilot run --resume {run_id}`"
        return "nothing; every step is done and checkpointed"

    def _handoff(self, run_id: str, goal: str, summary: RunSummary) -> None:
        lines = [f"# Handoff - {run_id}", "", f"Goal: {goal}. State: **{summary.state}**.", "",
                 "| step | status | note |", "|---|---|---|"]
        lines += [f"| {o.step} | {o.status} | {o.note} |" for o in summary.outcomes]
        lines += ["", f"Next action: {summary.next_action}", "", "_DEMO / SYNTHETIC_"]
        atomic_write_text(self.root / "logs" / run_id / "HANDOFF.md", "\n".join(lines) + "\n")

    # --- requests from outside ----------------------------------------------------------------------
    def request(self, tool_name: str, **inputs) -> None:
        """A direct request (say from a chat agent) to run one tool. Only registry tools, typed inputs, and
        never a publish without the run-scoped approval - which a direct request does not have."""
        try:
            tool = self.tools.get(tool_name)
            if tool is None:
                raise Refused(f"'{tool_name}' is not a registered tool; there is no general command runner")
            check_inputs(tool, inputs, self.workspaces)
            if tool.effect == "publish":
                raise Refused(f"{tool_name} publishes; it runs only inside a planned run, after a person approves it")
            raise Refused(f"{tool_name} runs only as a step of a planned run")
        except Refused as exc:
            self.event(None, "refused", what=tool_name, inputs=inputs, why=str(exc))
            raise


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:140] if lines else ""
