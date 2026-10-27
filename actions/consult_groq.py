"""Consult Groq (GPT-OSS 120B) when local Ollama fails."""
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
            fixed_code = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
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
