from pathlib import Path

# Target file
f = Path("D:/business/AI/Github/youtube-automation-agent-master/agents/content-strategy-agent.js")
code = f.read_text(encoding="utf-8")

# Fix 1: Line 458 - parsed.topic null check
code = code.replace(
    "const topic = String(parsed.topic || requestedTopic || '').trim();",
    "const topic = String((parsed && parsed.topic) || requestedTopic || 'AI agencies').trim();"
)

# Fix 2: Line 464 - parsed.contentType null check
code = code.replace(
    "const contentType = this.normalizeContentType(parsed.contentType, topic);",
    "const contentType = this.normalizeContentType((parsed && parsed.contentType), topic);"
)

# Fix 3: Line 465-467 - parsed.keywords null check
code = code.replace(
    "const keywords = Array.isArray(parsed.keywords) && parsed.keywords.length > 0",
    "const parsedKeywords = (parsed && Array.isArray(parsed.keywords)) ? parsed.keywords : [];\n      const keywords = parsedKeywords.length > 0"
)

# Fix 4: Line 365 - parsed.plan null check
code = code.replace(
    "return Array.isArray(parsed) ? parsed : Array.isArray(parsed.plan) ? parsed.plan : [];",
    "return Array.isArray(parsed) ? parsed : ((parsed && Array.isArray(parsed.plan)) ? parsed.plan : []);"
)

# Fix 5: Line 472-473 - already has checks, but ensure targetAudience is safe
code = code.replace(
    "targetAudience: String(parsed.targetAudience || await this.identifyTargetAudience(topic)).trim(),",
    "targetAudience: String((parsed && parsed.targetAudience) || await this.identifyTargetAudience(topic)).trim(),"
)

f.write_text(code, encoding="utf-8")
print("SUCCESS: Patched content-strategy-agent.js")
