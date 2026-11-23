import pathlib, sys
root = pathlib.Path(sys.argv[1])
for p in root.rglob("*"):
    if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts and p.suffix in {".py", ".toml", ".md", ".json", ".sql", ".yaml", ".yml", ".txt", ".cfg"}:
        b = p.read_bytes()
        if b.startswith(b"\xef\xbb\xbf"):
            p.write_bytes(b[3:]); print("stripped", p.relative_to(root))
