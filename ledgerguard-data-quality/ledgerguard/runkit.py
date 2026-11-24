"""Run evidence shared by every CivicWorks project.

Hashes, atomic writes, a machine-readable run manifest, and a draft-only outbox. The same file is
copied into each project so every repository stands on its own; nothing here knows about any one
project's data.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

SYNTHETIC_NOTICE = "DEMO / SYNTHETIC - every organisation, person, place and number here is invented."
ALLOWED_MAIL_DOMAINS = ("example.org", "example.net", "example.com")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    """Write to a temporary file beside the target, flush it to disk, then rename it into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.writing-{os.getpid()}")
    with temp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    return path


def atomic_write_text(path: str | Path, text: str) -> Path:
    return atomic_write_bytes(path, text.encode("utf-8"))


def json_text(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n"


def write_json(path: str | Path, obj) -> Path:
    return atomic_write_text(path, json_text(obj))


def unique_dir(parent: str | Path, stem: str) -> Path:
    """A new folder named `stem`, or `stem-2`, `stem-3` ... - never one that already exists."""
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        candidate = parent / (stem if n == 1 else f"{stem}-{n}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            n += 1


def scene(number: int, title: str) -> None:
    """Announce a demo scene. With CIVICWORKS_STEP=1 the demo waits (reads a line from stdin) before every
    scene after the first, so a viewer such as the CivicWorks Lab can show the workspace between scenes."""
    if number > 1 and os.environ.get("CIVICWORKS_STEP") == "1":
        print(f"@@ waiting before scene {number}", flush=True)
        sys.stdin.readline()
    print(f"\n== {number}. {title}", flush=True)


def environment() -> dict:
    """Enough to reproduce a run; deliberately no host name, user name or paths."""
    return {"python": platform.python_version(), "os": platform.system(), "os_release": platform.release(),
            "executable": Path(sys.executable).name}


@dataclass
class StageRecord:
    name: str
    status: str = "ok"  # ok | hold | blocked | fail | skipped | dry-run
    started: str = field(default_factory=utc_now)
    finished: str = ""
    detail: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    project_id: str
    run_id: str
    code_version: str
    schema_version: str
    fixture_seed: int | None
    mode: str = "dry-run"
    started: str = field(default_factory=utc_now)
    finished: str = ""
    environment: dict = field(default_factory=environment)
    stages: list[StageRecord] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    verdict: str = "incomplete"
    approval_id: str | None = None
    previous_release_id: str | None = None
    synthetic: bool = True

    def begin(self, name: str) -> StageRecord:
        record = StageRecord(name)
        self.stages.append(record)
        return record

    def end(self, record: StageRecord, status: str | None = None, **detail) -> StageRecord:
        if status:
            record.status = status
        record.detail.update(detail)
        record.finished = utc_now()
        return record

    def add_input(self, path: str | Path, root: str | Path) -> None:
        self.inputs[Path(path).relative_to(root).as_posix()] = sha256_file(path)

    def add_output(self, path: str | Path, root: str | Path) -> None:
        self.outputs[Path(path).relative_to(root).as_posix()] = sha256_file(path)

    def write(self, path: str | Path) -> Path:
        self.finished = utc_now()
        return write_json(path, asdict(self))


class Outbox:
    """Draft messages written as .eml files. Nothing here can send mail: there is no SMTP code at all."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def draft(self, name: str, to: list[str], subject: str, body: str, sender: str = "automation@example.org") -> Path:
        for address in [sender, *to]:
            domain = address.rsplit("@", 1)[-1].lower()
            if domain not in ALLOWED_MAIL_DOMAINS:
                raise ValueError(f"refusing a non-example address in a demo draft: {address}")
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(to)
        msg["Subject"] = f"[DRAFT - NOT SENT] {subject}"
        msg["X-CivicWorks-Draft"] = "never sent; review and send by hand if this were real"
        msg.set_content(f"{body.rstrip()}\n\n-- \n{SYNTHETIC_NOTICE}\n")
        path = self.folder / f"{name}.eml"
        atomic_write_bytes(path, bytes(msg))
        return path
