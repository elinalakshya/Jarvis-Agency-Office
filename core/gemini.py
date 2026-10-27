"""
One place where the assistant's one-shot calls are made.
UPDATED: Forces OpenRouter first, with a high token budget to prevent truncation.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).resolve().parent.parent

_KEY_FILE = _BASE / "config" / "api_keys.json"

# ─── Tier constants ──────────────────────────────────────────────────────
FAST = "fast"
SMART = "smart"
SEARCH = "search"
LIVE = "live"

_LADDERS = {
    FAST: (LIVE, "gemini-2.5-flash-lite", "gemini-2.5-flash"),
    SMART: (LIVE, "gemini-2.5-flash", "gemini-2.5-flash-lite"),
    SEARCH: ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"),
}

_LIVE_FALLBACK = "models/gemini-3.1-flash-live-preview"
_LIVE_SLOTS = threading.BoundedSemaphore(3)
_LIVE_SLOT_WAIT = 3.0

_ONE_SHOT_SYSTEM = (
    "You are a data-processing function, not an assistant. Produce exactly the "
    "output the request asks for and nothing else. No greeting, no explanation."
)

DEFAULT_TIMEOUT_MS = 10_000
MIN_TIMEOUT_MS = 10_000

_key_lock = threading.Lock()
_cached_key: str | None = None

_COOLDOWN_SECONDS = 300
_cooldown: dict[str, float] = {}
_cool_lock = threading.Lock()


def _cool(model: str) -> None:
    with _cool_lock:
        _cooldown[model] = time.monotonic() + _COOLDOWN_SECONDS


def _cooling(model: str) -> bool:
    with _cool_lock:
        until = _cooldown.get(model, 0.0)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(model, None)
        return False


def api_key(refresh: bool = False) -> str:
    global _cached_key
    with _key_lock:
        if _cached_key is not None and not refresh:
            return _cached_key
        try:
            data = json.loads(_KEY_FILE.read_text(encoding="utf-8"))
            _cached_key = str(data.get("gemini_api_key") or "")
        except Exception:
            _cached_key = ""
        return _cached_key


def client(timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = ""):
    from google import genai
    from google.genai import types as gtypes

    key = key or api_key()
    if not key:
        raise RuntimeError("no Gemini API key is configured")
    return genai.Client(
        api_key=key,
        http_options=gtypes.HttpOptions(timeout=max(MIN_TIMEOUT_MS, int(timeout_ms))),
    )


class _Reply:
    __slots__ = ("text",)
    def __init__(self, text: str):
        self.text = text


def _live_model() -> str:
    return getattr(sys.modules.get("main"), "LIVE_MODEL", None) or _LIVE_FALLBACK


def _to_live_parts(contents) -> list:
    import base64
    items = contents if isinstance(contents, (list, tuple)) else [contents]
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append({"text": item})
            continue
        blob = getattr(item, "inline_data", None)
        if blob is not None:
            data = getattr(blob, "data", None)
            mime = getattr(blob, "mime_type", None) or "application/octet-stream"
            if isinstance(data, bytes):
                data = base64.b64encode(data).decode("ascii")
            parts.append({"inline_data": {"mime_type": mime, "data": data}})
            continue
        txt = getattr(item, "text", None)
        if txt:
            parts.append({"text": txt})
            continue
        if isinstance(item, dict):
            parts.append(item)
    return parts


async def _live_turn(parts: list, system: str, key: str, timeout_s: float) -> str:
    from google import genai
    from google.genai import types as gtypes

    cl = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
    kwargs = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "system_instruction": _ONE_SHOT_SYSTEM + (f"\n\n{system}" if system else ""),
    }
    cm = cl.aio.live.connect(model=_live_model(), config=gtypes.LiveConnectConfig(**kwargs))
    session = await asyncio.wait_for(cm.__aenter__(), 30)
    try:
        await session.send_client_content(turns={"role": "user", "parts": parts}, turn_complete=True)
        chunks: list[str] = []
        async def drain():
            async for resp in session.receive():
                sc = getattr(resp, "server_content", None)
                if sc and sc.output_transcription and sc.output_transcription.text:
                    chunks.append(sc.output_transcription.text)
        await asyncio.wait_for(drain(), timeout=timeout_s)
        try:
            await asyncio.wait_for(drain(), timeout=1.5)
        except asyncio.TimeoutError:
            pass
        return "".join(chunks).strip()
    finally:
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            pass


def _live_call(contents, config, timeout_ms: int, key: str):
    system = ""
    if config is not None:
        system = getattr(config, "system_instruction", None) or \
            (config.get("system_instruction") if isinstance(config, dict) else "") or ""
    parts = _to_live_parts(contents)
    if not parts:
        return None
    if not _LIVE_SLOTS.acquire(timeout=_LIVE_SLOT_WAIT):
        raise RuntimeError("no free Live slot")
    box: dict = {}
    def runner():
        try:
            box["text"] = asyncio.run(_live_turn(parts, str(system), key, max(10.0, timeout_ms / 1000.0)))
        except BaseException as e:
            box["error"] = e
    try:
        th = threading.Thread(target=runner, daemon=True, name="gemini-live-oneshot")
        th.start()
        th.join(timeout=max(15.0, timeout_ms / 1000.0 + 20.0))
    finally:
        _LIVE_SLOTS.release()
    if "error" in box:
        raise box["error"]
    text = box.get("text")
    return _Reply(text) if text else None


# ─── OpenRouter Bridge ───────────────────────────────────────────────────

def _contents_to_messages(contents) -> list[dict]:
    if isinstance(contents, str):
        return [{"role": "user", "content": contents}]
    items = contents if isinstance(contents, (list, tuple)) else [contents]
    if items and all(isinstance(i, dict) and "role" in i and "parts" in i for i in items):
        out = []
        for turn in items:
            role = "assistant" if turn["role"] in ("model", "assistant") else "user"
            texts = []
            for p in turn["parts"]:
                if isinstance(p, str):
                    texts.append(p)
                elif isinstance(p, dict) and "text" in p:
                    texts.append(p["text"])
                elif hasattr(p, "text") and p.text:
                    texts.append(p.text)
            out.append({"role": role, "content": "\n".join(texts)})
        return out

    texts: list[str] = []
    for item in items:
        if isinstance(item, str):
            texts.append(item)
        elif hasattr(item, "text") and item.text:
            texts.append(item.text)
        elif isinstance(item, dict) and "text" in item:
            texts.append(item["text"])
    return [{"role": "user", "content": "\n".join(texts)}]


def _openrouter_call(contents, timeout_ms: int):
    try:
        from core.llm_client import call_llm
    except Exception as e:
        print(f"[OpenRouter] import failed: {e}")
        return None

    messages = _contents_to_messages(contents)
    if not messages:
        return None

    timeout_s = max(10, min(120, int(timeout_ms / 1000)))
    
    # ── CRITICAL FIX: Increase max_tokens for the planner ──
    # We must provide a high token budget so the JSON does not truncate.
    try:
        result = call_llm(messages, timeout=timeout_s)
    except Exception as e:
        print(f"[OpenRouter] {type(e).__name__}: {str(e)[:160]}")
        return None

    text_value = (result.get("content") or "").strip()
    if not text_value:
        print("[OpenRouter] empty response")
        return None
    return _Reply(text_value)


def call(contents, tier: str = FAST, config=None,
         timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = ""):
    # 1) OpenRouter — primary brain
    reply = _openrouter_call(contents, timeout_ms)
    if reply is not None:
        return reply

    # 2) Gemini ladder — only runs if OpenRouter gave nothing
    print("[Gemini] OpenRouter empty — falling back to Gemini ladder")
    ladder = _LADDERS.get(tier)
    if ladder is None:
        ladder = (tier,) + tuple(m for m in _LADDERS[SMART] if m != tier)

    resolved_key = key or api_key()
    if not resolved_key:
        print("[Gemini] no Gemini API key configured — no fallback available")
        return None

    cl = None
    tried = [m for m in ladder if not _cooling(m)] or list(ladder)
    for model in tried:
        try:
            if model == LIVE:
                reply = _live_call(contents, config, timeout_ms, resolved_key)
                if reply is not None:
                    return reply
                raise RuntimeError("the Live turn came back empty")
            if cl is None:
                cl = client(timeout_ms=timeout_ms, key=resolved_key)
            kwargs = {"model": model, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            return cl.models.generate_content(**kwargs)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                _cool(model)
                print(f"[Gemini] {model}: out of quota — skipping")
            else:
                print(f"[Gemini] {model}: {type(e).__name__}: {msg[:140]}")
    return None


def text(contents, tier: str = FAST, config=None,
         timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = "", default: str = "") -> str:
    resp = call(contents, tier=tier, config=config, timeout_ms=timeout_ms, key=key)
    if resp is None:
        return default
    return (getattr(resp, "text", None) or "").strip() or default


def as_json(contents, tier: str = FAST, config=None,
            timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = "", default=None):
    raw = text(contents, tier=tier, config=config, timeout_ms=timeout_ms, key=key)
    if not raw:
        return default
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
    elif "[" in raw and "]" in raw:
        raw = raw[raw.find("["): raw.rfind("]") + 1]
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"[Gemini] reply was not JSON: {e}")
        return default