# build_self_healing.py — One-time bootstrap to give JARVIS autonomous self-healing.
import os, sys, subprocess, json, re
from pathlib import Path

ROOT = Path(r"D:\business\AI\Github\Jarvis Agency Office")
CAP_DIR = r"D:\business\AI\Github\youtube-automation-agent-master"

# ── 1. Fix credentials.json ──────────────────────────────────────────────
creds_path = Path(CAP_DIR) / "config" / "credentials.json"
try:
    raw = creds_path.read_text(encoding="utf-8")
    fixed = re.sub(r'("model"\s*:\s*"[^"]+")(\s*\n\s*"baseURL")', r'\1,\2', raw)
    data = json.loads(fixed)
    creds_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[FIX] credentials.json valid. Model: {data['aiProvider']['model']}")
except Exception as e:
    print(f"[WARN] Could not fix credentials.json: {e}")

# ── 2. Create consult_groq.py ────────────────────────────────────────────
CONSULT_GROQ = '''"""Consult Groq (GPT-OSS 120B) when local Ollama fails."""
import os
from groq import Groq

def consult_groq(error: str, file_path: str, file_content: str, context: str = "") -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY environment variable not set."}
    
    client = Groq(api_key=api_key)
    prompt = f"""You are an expert senior developer. Fix the following code based on the error.
Error: {error}
Context: {context}
File: {file_path}
Code:
{file_content}

Return ONLY the complete, fixed code. No markdown fences, no explanations. Just the raw code."""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000,
        )
        fixed_code = response.choices[0].message.content.strip()
        # Strip markdown if Groq adds it anyway
        if fixed_code.startswith("```"):
            lines = fixed_code.splitlines()
            fixed_code = "\\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return {"status": "success", "fixed_code": fixed_code}
    except Exception as e:
        return {"error": str(e)}

TOOL = {
    "name": "consult_groq",
    "description": "Consult Groq's 120B model to fix a broken file when local tools fail.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "error": {"type": "STRING"},
            "file_path": {"type": "STRING"},
            "file_content": {"type": "STRING"},
            "context": {"type": "STRING"}
        },
        "required": ["error", "file_path", "file_content"]
    }
}
'''

# ── 3. Create self_heal.py ───────────────────────────────────────────────
SELF_HEAL = '''"""Autonomous self-healing loop."""
import json, time
from pathlib import Path
from actions.shell_exec import shell_exec
from actions.consult_groq import consult_groq

def self_heal(goal: str, target_file: str, command_to_run: str, max_retries: int = 3) -> dict:
    print(f"🚀 [SELF-HEAL] Starting goal: {goal}")
    file_path = Path(target_file)
    
    for attempt in range(1, max_retries + 1):
        print(f"🔄 [SELF-HEAL] Attempt {attempt}/{max_retries}...")
        
        # 1. Try to run the command
        result = shell_exec(command_to_run, timeout=60)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        
        # Check for common success indicators (you can customize this)
        if result.get("returncode") == 0 and "Error" not in stderr:
            print(f"✅ [SELF-HEAL] Success on attempt {attempt}!")
            return {"status": "success", "output": stdout, "attempts": attempt}
            
        error_msg = stderr or stdout or "Unknown error"
        print(f"❌ [SELF-HEAL] Failed. Error: {error_msg[:200]}")
        
        # 2. Read the file
        try:
            file_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"status": "failed", "reason": f"Cannot read target file: {e}"}
            
        # 3. Consult Groq for a fix
        print(f"🧠 [SELF-HEAL] Asking Groq for a fix...")
        groq_res = consult_groq(error=error_msg, file_path=str(file_path), file_content=file_content)
        
        if "error" in groq_res:
            print(f"⚠️  [SELF-HEAL] Groq failed: {groq_res['error']}")
            continue
            
        # 4. Write the fix
        fixed_code = groq_res["fixed_code"]
        if fixed_code and fixed_code != file_content:
            file_path.write_text(fixed_code, encoding="utf-8")
            print(f"🔧 [SELF-HEAL] Applied fix to {target_file}. Retrying...")
        else:
            print("🤷 [SELF-HEAL] Groq returned no changes. Retrying same file...")

    print("🚨 [SELF-HEAL] Max retries reached. Escalating to human.")
    return {"status": "failed", "reason": "Max retries reached without success"}

TOOL = {
    "name": "self_heal",
    "description": "Run a command, catch errors, and use Groq to fix the code automatically in a loop.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {"type": "STRING", "description": "What we are trying to achieve"},
            "target_file": {"type": "STRING", "description": "Full path to the file to fix"},
            "command_to_run": {"type": "STRING", "description": "The terminal command that tests the file"},
            "max_retries": {"type": "INTEGER", "description": "How many times to try before giving up"}
        },
        "required": ["goal", "target_file", "command_to_run"]
    }
}
'''

def write_file(path, content):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"[write] {path}")

# ── 4. Wire into main.py ─────────────────────────────────────────────────
def wire_main():
    main = ROOT / "main.py"
    src = main.read_text(encoding="utf-8")
    if 'name == "self_heal"' in src:
        print("[skip] Tools already wired.")
        return True

    # Add declarations
    decl = '''    {
        "name": "consult_groq",
        "description": "Consult Groq's 120B model to fix a broken file when local tools fail.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "error": {"type": "STRING"},
                "file_path": {"type": "STRING"},
                "file_content": {"type": "STRING"},
                "context": {"type": "STRING"}
            },
            "required": ["error", "file_path", "file_content"]
        }
    },
    {
        "name": "self_heal",
        "description": "Run a command, catch errors, and use Groq to fix the code automatically in a loop.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "STRING"},
                "target_file": {"type": "STRING"},
                "command_to_run": {"type": "STRING"},
                "max_retries": {"type": "INTEGER"}
            },
            "required": ["goal", "target_file", "command_to_run"]
        }
    },
'''
    m = re.search(r'(TOOL_DECLARATIONS\s*=\s*\[)', src)
    start = m.end() - 1
    depth, end = 0, -1
    for i in range(start, len(src)):
        if src[i] == '[': depth += 1
        elif src[i] == ']':
            depth -= 1
            if depth == 0: end = i; break
    src = src[:end] + decl + src[end:]

    # Add handlers
    undo_match = re.search(r'^([ \t]*)elif\s+name\s*==\s*"undo"', src, re.MULTILINE)
    indent = undo_match.group(1)
    handler = (
        f'{indent}elif name == "consult_groq":\n'
        f'{indent}    from actions.consult_groq import consult_groq\n'
        f'{indent}    result = consult_groq(args.get("error", ""), args.get("file_path", ""), args.get("file_content", ""), args.get("context", ""))\n'
        f'{indent}elif name == "self_heal":\n'
        f'{indent}    from actions.self_heal import self_heal\n'
        f'{indent}    result = self_heal(args.get("goal", ""), args.get("target_file", ""), args.get("command_to_run", ""), int(args.get("max_retries", 3)))\n'
    )
    src = src[:undo_match.start()] + handler + src[undo_match.start():]
    main.write_text(src, encoding="utf-8")
    print("[wire] main.py updated")
    return True

if __name__ == "__main__":
    write_file("actions/consult_groq.py", CONSULT_GROQ)
    write_file("actions/self_heal.py", SELF_HEAL)
    wire_main()
    
    # Verify
    r = subprocess.run([sys.executable, "-c", "import main; print('main.py OK')"], cwd=str(ROOT), capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())