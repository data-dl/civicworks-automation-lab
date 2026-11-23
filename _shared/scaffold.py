"""Write the boilerplate every CivicWorks repository shares: package init/main, runkit copy, db.py copy,
pyproject, .gitignore, LICENSE, CI workflow. Usage: python scaffold.py <repo dir> <package> "<description>" deps..."""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
repo, package, description, *deps = sys.argv[1:]
repo = Path(repo)
pkg = repo / package
pkg.mkdir(parents=True, exist_ok=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


if not (pkg / "__init__.py").exists():
    write(pkg / "__init__.py", f'"""{description}"""\n\n__version__ = "0.1.0"\n')
write(pkg / "__main__.py", "import sys\n\nfrom .cli import main\n\nsys.exit(main())\n")
shutil.copyfile(HERE / "runkit.py", pkg / "runkit.py")
DB_SOURCE = HERE.parent / "openbadge-registry-publisher" / "openbadge" / "db.py"
if (repo / "db" / "migrations").exists() and DB_SOURCE.resolve() != (pkg / "db.py").resolve():
    shutil.copyfile(DB_SOURCE, pkg / "db.py")
dep_list = ", ".join(f'"{d}"' for d in deps)
write(repo / "pyproject.toml", f"""[project]
name = "{repo.name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [{dep_list}]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.5"]

[project.scripts]
{package} = "{package}.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["{package}*"]

[tool.setuptools.package-data]
{package} = ["*.json", "*.yaml"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
""")
write(repo / ".gitignore", "__pycache__/\n*.egg-info/\n.venv/\nbuild/\n.pytest_cache/\n.ruff_cache/\n")
write(repo / ".gitattributes", "* text=auto eol=lf\n*.xlsx binary\n*.docx binary\n*.mp4 binary\n")
write(repo / "LICENSE", """MIT License

Copyright (c) 2026 data-dl

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""")
write(repo / ".github" / "workflows" / "tests.yml", f"""name: tests

on: [push, pull_request]

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{{{ matrix.os }}}}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[dev]"
      - run: ruff check {package} tests
      - run: python -m pytest -q
      - run: python -m {package} demo --out build/demo
""")
print("scaffolded", repo.name)
