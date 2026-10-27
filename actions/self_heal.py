"""Autonomous self-healing loop."""
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
