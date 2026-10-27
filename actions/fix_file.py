import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def fix_file(parameters=None, **kwargs):
    """
    Apply surgical string replacements to fix a file.
    No LLM. No hanging. Just exact string matching.
    """
    target_file = (parameters or {}).get("target_file", "").strip()
    
    if not target_file:
        return "Error: No target_file provided."

    full_path = Path(target_file)
    if not full_path.exists():
        full_path = BASE_DIR / target_file
        if not full_path.exists():
            return f"Error: File {target_file} does not exist."

    content = full_path.read_text(encoding="utf-8")
    patches_applied = []

    # ── CONTENT STRATEGY AGENT PATCHES ──
    
    # PATCH 1: Fix parsed.topic null check
    if "const topic = String(parsed.topic" in content:
        content = content.replace(
            "const topic = String(parsed.topic || requestedTopic || '').trim();",
            "const topic = String((parsed && parsed.topic) || requestedTopic || 'AI agencies').trim();"
        )
        patches_applied.append("parsed.topic")

    # PATCH 2: Fix parsed.contentType null check
    if "this.normalizeContentType(parsed.contentType" in content:
        content = content.replace(
            "const contentType = this.normalizeContentType(parsed.contentType, topic);",
            "const contentType = this.normalizeContentType((parsed && parsed.contentType), topic);"
        )
        patches_applied.append("parsed.contentType")

    # PATCH 3: Fix parsed.keywords null check
    if "Array.isArray(parsed.keywords)" in content:
        content = content.replace(
            "const keywords = Array.isArray(parsed.keywords) && parsed.keywords.length > 0",
            "const parsedKeywords = (parsed && Array.isArray(parsed.keywords)) ? parsed.keywords : [];\n      const keywords = parsedKeywords.length > 0"
        )
        patches_applied.append("parsed.keywords")

    # PATCH 4: Fix parsed.plan null check
    if "Array.isArray(parsed.plan)" in content:
        content = content.replace(
            "return Array.isArray(parsed) ? parsed : Array.isArray(parsed.plan) ? parsed.plan : [];",
            "return Array.isArray(parsed) ? parsed : ((parsed && Array.isArray(parsed.plan)) ? parsed.plan : []);"
        )
        patches_applied.append("parsed.plan")

    # PATCH 5: Fix parsed.targetAudience null check
    if "parsed.targetAudience" in content:
        content = content.replace(
            "targetAudience: String(parsed.targetAudience || await this.identifyTargetAudience(topic)).trim(),",
            "targetAudience: String((parsed && parsed.targetAudience) || await this.identifyTargetAudience(topic)).trim(),"
        )
        patches_applied.append("parsed.targetAudience")

    # ── SCRIPT WRITER AGENT PATCHES ──
    
    # PATCH 6: Fix strategy.angle null check (line 125)
    if "Angle: ${strategy.angle}" in content:
        content = content.replace(
            "Angle: ${strategy.angle}",
            "Angle: ${(strategy && strategy.angle) || 'General'}"
        )
        patches_applied.append("strategy.angle (line 125)")

    # PATCH 7: Fix strategy.angle null check (line 269)
    if "${strategy.angle}" in content:
        content = content.replace(
            "${strategy.angle}",
            "${(strategy && strategy.angle) || 'General'}"
        )
        patches_applied.append("strategy.angle (line 269)")

    # ── SEO OPTIMIZER AGENT PATCHES ──
    
    # PATCH 8: Fix strategy.angle null check (line 108)
    if "Angle: ${strategy.angle}" in content:
        content = content.replace(
            "Angle: ${strategy.angle}",
            "Angle: ${(strategy && strategy.angle) || 'General'}"
        )
        patches_applied.append("strategy.angle (seo line 108)")

    # PATCH 9: Fix strategy.angle.toLowerCase() null check (line 227)
    if "${strategy.angle.toLowerCase()}" in content:
        content = content.replace(
            "${strategy.angle.toLowerCase()}",
            "${(strategy && strategy.angle || 'General').toLowerCase()}"
        )
        patches_applied.append("strategy.angle.toLowerCase() (seo line 227)")

    if not patches_applied:
        return "No patches needed. File is already fixed."

    full_path.write_text(content, encoding="utf-8")
    return f"SUCCESS: Applied {len(patches_applied)} patches: {', '.join(patches_applied)}"


TOOL = {
    "name": "fix_file",
    "description": "Fix a specific file by applying known surgical string replacements. Use this to fix the YouTube agent's strategy bug.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_file": {"type": "STRING", "description": "Absolute or relative path to the file"}
        },
        "required": ["target_file"]
    },
    "handler": fix_file
}