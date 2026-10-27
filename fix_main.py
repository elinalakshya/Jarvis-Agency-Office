from pathlib import Path

p = Path("finance/main.py")
lines = p.read_text(encoding="utf-8").split("\n")

# Find the last line that is valid Python (ends with : or ) or is indented or is a comment)
# Then drop everything after it.
cleaned = []
for line in lines:
    stripped = line.strip()
    # Keep lines that look like Python
    if (stripped == "" or
        stripped.startswith("#") or
        stripped.startswith("import") or
        stripped.startswith("from") or
        stripped.startswith("def") or
        stripped.startswith("class") or
        stripped.startswith("if") or
        stripped.startswith("return") or
        stripped.startswith("try") or
        stripped.startswith("except") or
        stripped.startswith("else") or
        stripped.startswith("elif") or
        stripped.startswith("for") or
        stripped.startswith("while") or
        stripped.startswith("print") or
        stripped.startswith("    ") or
        stripped.startswith("\t") or
        "=" in stripped or
        stripped.endswith(":") or
        stripped.endswith(")") or
        stripped.endswith("]")):
        cleaned.append(line)
    else:
        # This line is prose. Stop here.
        print(f"Stopped at: {stripped[:80]}")
        break

p.write_text("\n".join(cleaned), encoding="utf-8")
print(f"Cleaned. New size: {len('\\n'.join(cleaned))} chars")