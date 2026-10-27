import json
import requests
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

FREE_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "minimax/minimax-m3.1-flash:free"
]

def _load_config() -> dict:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    if not cfg.get("llm_api_key"):
        cfg["llm_api_key"] = "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"
    if not cfg.get("llm_url"):
        cfg["llm_url"] = "https://openrouter.ai/api/v1"
    if not cfg.get("llm_model"):
        cfg["llm_model"] = "nvidia/nemotron-3-ultra-550b-a55b:free"
    return cfg

def run_security_audit(parameters=None, **kwargs):
    target_file = (parameters or {}).get("target_file", "").strip()

    if not target_file:
        return "Error: No target_file provided."

    full_path = BASE_DIR / target_file
    if not str(full_path).lower().startswith(str(BASE_DIR).lower()):
        return "BOUNDARY VIOLATION: File outside project."

    if not full_path.exists():
        return f"Error: File {target_file} does not exist."

    code = full_path.read_text(encoding="utf-8")
    if not code.strip():
        return f"PASS: {target_file} is empty."

    cfg = _load_config()
    api_key = cfg.get("llm_api_key", "").strip()
    url = cfg.get("llm_url", "https://openrouter.ai/api/v1").rstrip("/")

    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")

    system_prompt = (
        "You are a security auditor. You MUST output EXACTLY ONE of these two formats:\n"
        "PASS\n"
        "or\n"
        "FAIL: [Vulnerability Name] - [Short reason]\n\n"
        "Output NOTHING else. No explanations. No markdown. No thinking. Just the one line."
    )

    user_prompt = (
        "Check this code for: hardcoded secrets, command injection, path traversal, unsafe eval/exec, SQL injection.\n\n"
        "CODE:\n"
        + code
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    endpoint = f"{url}/v1/chat/completions"

    # ── 1. TRY OPENROUTER ──
    for model in FREE_MODELS:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 50,
            "temperature": 0,
        }
        try:
            r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            if r.status_code == 429:
                print(f"[Audit] 429 on {model}. Switching...")
                time.sleep(1)
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

            if "PASS" in content.upper():
                return f"PASS: {target_file} passed security audit."
            if "FAIL" in content.upper():
                fail_match = content.upper().split("FAIL", 1)[1].strip(" :")
                return f"FAIL: {fail_match[:100]}"
            return f"UNCLEAR: {content[:100]}"
        except Exception as e:
            continue

    # ── 2. FALLBACK TO LOCAL OLLAMA ──
    print(f"[Audit] All OpenRouter models failed. Switching to LOCAL OLLAMA...")
    try:
        ollama_payload = {
            "model": "qwen2.5-coder:7b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"num_predict": 100}
        }
        r_local = requests.post("http://localhost:11434/api/chat", json=ollama_payload, timeout=300)
        r_local.raise_for_status()
        content = r_local.json().get("message", {}).get("content", "").strip()

        if "PASS" in content.upper():
            return f"PASS: {target_file} passed security audit."
        if "FAIL" in content.upper():
            fail_match = content.upper().split("FAIL", 1)[1].strip(" :")
            return f"FAIL: {fail_match[:100]}"
        return f"UNCLEAR (Local): {content[:100]}"
    except Exception as e:
        return f"AUDIT ERROR (Local also failed): {e}"


TOOL = {
    "name": "run_security_audit",
    "description": "Run a security audit on a Python file. Use this IMMEDIATELY after writing a file, before marking the task complete. Returns PASS or FAIL.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_file": {"type": "STRING", "description": "Relative path to the file to audit, e.g. 'core/finance/ledger.py'"}
        },
        "required": ["target_file"]
    },
    "handler": run_security_audit
}