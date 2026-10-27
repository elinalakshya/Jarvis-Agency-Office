import json
import requests
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# OpenRouter rotation list
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
    
    return cfg

def run_claude_code(parameters=None, **kwargs):
    prompt = (parameters or {}).get("prompt", "").strip()
    target_file = (parameters or {}).get("target_file", "").strip()

    if not prompt or not target_file:
        return "Error: Missing prompt or target_file"

    # Safety check
    full_path = BASE_DIR / target_file
    if not str(full_path).lower().startswith(str(BASE_DIR).lower()):
        return f"BOUNDARY VIOLATION: {target_file} is outside allowed folder"

    # Create directory if needed
    full_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = _load_config()
    api_key = cfg.get("llm_api_key", "").strip()
    url = cfg.get("llm_url", "https://openrouter.ai/api/v1").rstrip("/")

    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")

    code_prompt = (
        f"You are a senior Python developer. Write the complete, working content for the file `{target_file}`.\n\n"
        f"Instructions: {prompt}\n\n"
        f"Rules:\n"
        f"- Output ONLY the file content (no markdown fences, no explanation)\n"
        f"- Make it production-quality code\n"
        f"- Add helpful comments\n"
        f"- If it's a Python file, make sure it runs\n"
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    endpoint = f"{url}/v1/chat/completions"

    # ── 1. TRY OPENROUTER MODELS ──
    for model in FREE_MODELS:
        print(f"[Orchestrator] Trying OpenRouter model: {model}...")
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": code_prompt}],
            "max_tokens": 8000,
            "temperature": 0.2,
        }

        try:
            r = requests.post(endpoint, headers=headers, json=payload, timeout=120)
            
            if r.status_code == 429:
                print(f"[Orchestrator] 429 Rate Limit on {model}. Switching to next...")
                time.sleep(1)
                continue
                
            if r.status_code == 404:
                print(f"[Orchestrator] 404 Model Not Found on {model}. Switching...")
                continue
                
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Strip markdown fences
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:])
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            if not content:
                print(f"[Orchestrator] Empty content from {model}. Switching...")
                continue

            # Success!
            full_path.write_text(content, encoding="utf-8")
            print(f"[Orchestrator] SUCCESS: Wrote {target_file} using {model}")
            return f"Success: Created {target_file} ({len(content)} chars) via {model}"

        except requests.exceptions.Timeout:
            print(f"[Orchestrator] Timeout on {model}. Switching...")
            continue
        except Exception as e:
            print(f"[Orchestrator] Error on {model}: {e}. Switching...")
            continue

    # ── 2. FALLBACK TO LOCAL OLLAMA ──
    print("[Orchestrator] All OpenRouter models failed. Switching to LOCAL OLLAMA (qwen2.5-coder:7b)...")
    
    try:
        ollama_payload = {
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": code_prompt}],
            "stream": False,
            "options": {"num_predict": 4000}
        }
        r_local = requests.post("http://localhost:11434/api/chat", json=ollama_payload, timeout=300)
        r_local.raise_for_status()
        
        content = r_local.json().get("message", {}).get("content", "").strip()
        
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:])
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
        if not content:
            return "Error: Ollama returned empty content."

        full_path.write_text(content, encoding="utf-8")
        print(f"[Orchestrator] SUCCESS (LOCAL): Wrote {target_file} using Ollama")
        return f"Success (Local): Created {target_file} ({len(content)} chars) via Ollama"

    except Exception as e:
        print(f"[Orchestrator] Ollama also failed: {e}")
        return f"Error: Cloud and Local both failed. {e}"


TOOL = {
    "name": "run_claude_code",
    "description": "MANDATORY TOOL. When the user asks you to build, create, write, or generate any file or code, you MUST call this tool IMMEDIATELY.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "Exact instructions for the code to write"},
            "target_file": {"type": "STRING", "description": "Relative path from project root"}
        },
        "required": ["prompt", "target_file"]
    },
    "handler": run_claude_code
}