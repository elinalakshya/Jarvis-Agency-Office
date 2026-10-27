from pathlib import Path

p = Path(r'D:\business\AI\Github\youtube-automation-agent-master\index.js')
src = p.read_text(encoding='utf-8')

# Add a safe guard right before the strategyContext properties are read
anchor = "generated.requestedLength = lengthLabels[length] || lengthLabels.medium;"
guard = "\n      const safeCtx = strategyContext || {};\n"

if "const safeCtx" not in src:
    src = src.replace(anchor, anchor + guard)
    print("INSERTED safeCtx guard")

# Replace every strategyContext.X with safeCtx.X
properties = [
    "angle", "rationale", "audience", "objective",
    "valueProposition", "constraints", "pillar", "researchSources"
]

for prop in properties:
    old = f"strategyContext.{prop}"
    new = f"safeCtx.{prop}"
    if old in src:
        src = src.replace(old, new)
        print(f"  guarded strategyContext.{prop}")

p.write_text(src, encoding='utf-8')
print("PATCHED: all strategyContext properties guarded")