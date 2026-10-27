# upgrade_jarvis.py
import sys, subprocess, re
from pathlib import Path

ROOT = Path(r"D:\business\AI\Github\Jarvis Agency Office")

# 1. Create the Senior Developer Prompt
PROMPT = """You are JARVIS, the Lead Systems Engineer for this AI Agency. 
You do not ask the human for permission. You do not say "Would you like me to". 
You investigate, you read the code, you apply the fix, you verify it, and then you report the results.
If you hit an error, you use `consult_groq` or your local Ollama to figure out the fix.
If a file needs editing, you use `fix_file` or `shell_exec` to do it.
You are autonomous. The human is the CEO. You are the CTO."""

prompt_file = ROOT / "prompts" / "senior_developer.md"
prompt_file.parent.mkdir(exist_ok=True)
prompt_file.write_text(PROMPT, encoding="utf-8")
print("[write] prompts/senior_developer.md")

# 2. Create the Orchestrator Tool
ORCHESTRATOR = '''"""Autonomous goal orchestrator."""
from actions.consult_groq import consult_groq
from actions.shell_exec import shell_exec
from pathlib import Path

def project_orchestrator(goal: str, target_dir: str, max_loops: int = 5) -> dict:
    print(f"🤖 [ORCHESTRATOR] Starting autonomous goal: {goal}")
    
    for i in range(max_loops):
        print(f"🔄 Loop {i+1}/{max_loops}...")
        
        # This tool just gives JARVIS a loop structure.
        # The LLM itself will execute the tools in the main loop.
        # This function is a placeholder if called directly, but JARVIS
        # will actually use the LLM loop to fix things.
        pass
        
    return {"status": "orchestrator running"}
'''

# Actually, a Python tool can't run the LLM loop. The LLM loop IS the loop.
# We just need to update the system prompt so JARVIS stops asking for permission.

def wire_prompt():
    main = ROOT / "main.py"
    src = main.read_text(encoding="utf-8")
    
    # Find the system prompt injection in main.py (usually where it says SYSTEM_PROMPT or similar)
    # We will just append a strong override.
    if "You are JARVIS, the Lead Systems Engineer" not in src:
        # Find the TOOL_DECLARATIONS list to anchor our insert
        # Actually, we will just replace the system prompt entirely.
        # But since we don't know the exact variable, we'll create a file JARVIS reads.
        pass

if __name__ == "__main__":
    print("Done.")