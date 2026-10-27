import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python clean_file.py <file_path>")
    sys.exit(1)

p = Path(sys.argv[1])
if not p.exists():
    print(f"File not found: {p}")
    sys.exit(1)

lines = p.read_text(encoding="utf-8").split("\n")
cleaned = [l for l in lines if not l.strip().startswith("```")]
removed = len(lines) - len(cleaned)
p.write_text("\n".join(cleaned), encoding="utf-8")
print(f"Removed {removed} markdown fence lines from {p}")