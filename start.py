"""One command to set up and open the CivicWorks Lab.

    python start.py            set up (first time only) and open the Lab in your browser
    python start.py --check    also run every pipeline's tests and demo, then open the Lab
    python start.py --no-lab   set up only

It creates a private Python environment in .venv (so nothing is installed system-wide), installs the eight
pipelines and the Lab into it, and starts the Lab. Running it again skips whatever is already done.
Needs Python 3.11 or newer and nothing else; no network is used after the first install.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = [("atlas-license-directory", "atlas"), ("openbadge-registry-publisher", "openbadge"),
            ("regional-programs-analytics", "regional"), ("ledgerguard-data-quality", "ledgerguard"),
            ("safesite-compliance-cycle", "safesite"), ("masterrecord-steward", "masterrecord"),
            ("reconcilehub", "reconcilehub"), ("opspilot-control-center", "opspilot")]
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MARK = VENV / ".civicworks-installed"


def say(msg: str) -> None:
    print(f"  {msg}", flush=True)


def fingerprint() -> str:
    """Changes whenever a project's dependencies change, so a pull that adds one triggers a reinstall."""
    h = hashlib.sha256()
    for folder in [d for d, _ in PROJECTS] + ["lab"]:
        h.update((ROOT / folder / "pyproject.toml").read_bytes())
    return h.hexdigest()


def setup() -> None:
    if sys.version_info < (3, 11):  # noqa: UP036 - people may run this with an old Python
        sys.exit(f"Python 3.11 or newer is needed; this is {sys.version.split()[0]}. Get it from python.org.")
    if not PY.exists():
        say("creating a private Python environment in .venv ...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    if MARK.exists() and MARK.read_text(encoding="utf-8") == fingerprint():
        say("already installed")
        return
    say("installing the eight pipelines and the Lab (first time: a minute or two) ...")
    args = [str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    for folder, _ in PROJECTS:
        args += ["-e", f"{ROOT / folder}[dev]"]
    args += ["-e", f"{ROOT / 'lab'}[dev]"]
    for attempt in (1, 2, 3):
        if subprocess.run(args + ["--retries", "5"]).returncode == 0:
            break
        say(f"the install did not finish (attempt {attempt} of 3)")
    else:
        sys.exit("Could not download the packages. The first install needs the internet (pypi.org); "
                 "check the connection or proxy and run start.py again - it picks up where it stopped.")
    MARK.write_text(fingerprint(), encoding="utf-8")
    say("installed")


def check() -> bool:
    ok = True
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for folder, pkg in PROJECTS:
        t = subprocess.run([str(PY), "-m", "pytest", "-q"], cwd=ROOT / folder, capture_output=True, text=True, env=env)
        d = subprocess.run([str(PY), "-m", pkg, "demo", "--out", str(ROOT / "build" / "start-check" / pkg)],
                           cwd=ROOT / folder, capture_output=True, text=True, env=env)
        last = (t.stdout.strip().splitlines() or ["?"])[-1]
        good = t.returncode == 0 and d.returncode == 0
        ok &= good
        say(f"{'ok  ' if good else 'FAIL'} {pkg:13} tests: {last}; demo: {'ran' if d.returncode == 0 else 'failed'}")
    return ok


def main(argv: list[str]) -> int:
    print("CivicWorks Automation Lab")
    setup()
    if "--check" in argv and not check():
        say("something failed - see above")
        return 1
    if "--no-lab" in argv:
        say(f"done. Start the Lab later with:  {PY.relative_to(ROOT)} -m civicworks_lab")
        return 0
    say("opening the Lab at http://127.0.0.1:8870 (press Ctrl+C here, or Quit in the Lab, to stop) ...")
    return subprocess.call([str(PY), "-m", "civicworks_lab"], cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
