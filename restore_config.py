import json
from pathlib import Path

config = {
    "llm_provider": "openai",
    "llm_url": "https://openrouter.ai/api/v1",
    "llm_model": "google/gemma-4-31b-it:free",
    "llm_api_key": "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",
    "gemini_api_key": "AQ.Ab8RN6LlSaFHNTCqItBVJ2affczzJaQRyXFks3l59RmTKAbTPw",
    "os_system": "windows",
    "hud_style": "core",
    "push_to_talk_enabled": False,
    "wake_word_enabled": True,
    "input_device": "Microphone Array (Realtek Audio)",
    "output_device": "Speakers / Headphones (Realtek Audio)",
    "voice_name": "Charon",
    "assistant_name": "JARVIS",
    "user_name": "",
    "ui_color": "#00d4ff",
    "morning_brief_enabled": False
}

Path("config").mkdir(exist_ok=True)
Path("config/api_keys.json").write_text(json.dumps(config, indent=4), encoding="utf-8")
print("Config restored!")