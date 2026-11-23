"""The tool registry and the planners.

A plan is only ever a list of registry tools with typed inputs. Whatever proposes a plan - the
deterministic rules planner, or an optional language-model planner behind the same interface - the
plan is validated against the registry before anything runs, so an unknown tool, a missing input or
a path outside the workspaces is refused no matter who asked.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

REGISTRY_FILE = Path(__file__).with_name("tools.yaml")
QUARTER = re.compile(r"^\d{4}Q[1-4]$")
ROLE = re.compile(r"^[a-z][a-z ]{2,40}$")


class Refused(Exception):
    """A request OpsPilot will not carry out. The message says why."""


@dataclass(frozen=True)
class Tool:
    name: str
    module: str
    argv: tuple[str, ...]
    inputs: dict
    effect: str
    outputs: tuple[str, ...]


@dataclass
class Step:
    id: str
    tool: str
    project: str
    after: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


@dataclass
class Plan:
    goal: str
    description: str
    steps: list[Step]


def load_registry(path: Path = REGISTRY_FILE) -> tuple[dict[str, Tool], dict]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    tools = {name: Tool(name, t["module"], tuple(t["argv"]), dict(t["inputs"]), t["effect"],
                        tuple(t.get("outputs", []))) for name, t in raw["tools"].items()}
    return tools, raw["goals"]


def check_inputs(tool: Tool, values: dict, workspaces: Path) -> dict:
    """Type-check every input the tool declares; refuse anything else."""
    clean = {}
    for name, kind in tool.inputs.items():
        if name not in values:
            raise Refused(f"{tool.name}: missing input '{name}'")
        value = values[name]
        if kind == "workspace":
            root = workspaces.resolve()
            target = (workspaces / str(value)).resolve()
            if root != target and root not in target.parents:
                raise Refused(f"{tool.name}: workspace '{value}' is outside {workspaces.name}/")
            clean[name] = str(target)
        elif kind == "quarter":
            if not QUARTER.match(str(value)):
                raise Refused(f"{tool.name}: '{value}' is not a quarter like 2026Q2")
            clean[name] = str(value)
        elif kind == "role":
            if not ROLE.match(str(value)):
                raise Refused(f"{tool.name}: '{value}' is not an approver role")
            clean[name] = str(value)
        else:
            raise Refused(f"{tool.name}: unknown input type {kind}")
    extra = set(values) - set(tool.inputs)
    if extra:
        raise Refused(f"{tool.name}: inputs it does not declare: {sorted(extra)}")
    return clean


def validate_plan(plan: Plan, tools: dict[str, Tool]) -> list[Step]:
    """Every tool registered, every dependency known, no cycles. Returns steps in dependency order."""
    ids = {s.id for s in plan.steps}
    for s in plan.steps:
        if s.tool not in tools:
            raise Refused(f"step {s.id}: '{s.tool}' is not a registered tool")
        unknown = set(s.after) - ids
        if unknown:
            raise Refused(f"step {s.id}: waits for unknown steps {sorted(unknown)}")
    ordered, done = [], set()
    pending = list(plan.steps)
    while pending:
        ready = [s for s in pending if set(s.after) <= done]
        if not ready:
            raise Refused(f"plan has a dependency cycle among {[s.id for s in pending]}")
        for s in ready:
            ordered.append(s)
            done.add(s.id)
            pending.remove(s)
    return ordered


class Planner(Protocol):
    def plan(self, goal: str) -> Plan: ...


class RulesPlanner:
    """Deterministic: the goal's steps come straight from the registry file."""

    def __init__(self, goals: dict):
        self.goals = goals

    def plan(self, goal: str) -> Plan:
        if goal not in self.goals:
            raise Refused(f"unknown goal '{goal}'; known: {sorted(self.goals)}")
        g = self.goals[goal]
        return Plan(goal, g["description"], [Step(s["id"], s["tool"], s["project"], list(s.get("after", [])),
                                                  dict(s.get("params", {}))) for s in g["steps"]])


class LanguageModelPlanner:
    """The optional integration point. Off unless OPSPILOT_LLM=1, and no model is wired in here: whatever
    a model proposed would still go through validate_plan, approvals and the same refusals."""

    def plan(self, goal: str) -> Plan:
        if os.environ.get("OPSPILOT_LLM") != "1":
            raise Refused("language-model planning is disabled (set OPSPILOT_LLM=1 to enable the interface)")
        raise Refused("no language model is configured for this demonstration")
