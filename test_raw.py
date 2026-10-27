from core import gemini

prompt = """You are a senior software architect. Break this goal into 3-7 concrete tasks.

Goal: Build Phase 3: Finance and Compliance layer. Include: ledger, invoice generator, bill vault, bill collector, bill matcher, bill verifier, payment tracker, follow-up scheduler, market-rate pricing, tax calculator, monthly CA report, YoY growth tracker, and approval gatekeeper. Enforce 8 agency rules.

Return ONLY a JSON array. Each task must have:
- "id": 1, 2, 3...
- "title": short description
- "target_file": relative path
- "prompt": detailed instructions

Output ONLY the JSON array. No markdown fences. No explanation."""

response = gemini.text(prompt, tier=gemini.SMART, timeout_ms=60_000)
print("=== RAW RESPONSE ===")
print(response)
print("=== END ===")
print(f"Length: {len(response)} chars")
print(f"Ends with ']': {response.strip().endswith(']')}")