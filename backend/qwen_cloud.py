"""Hosted Qwen 3 via OpenRouter: the cloud fallback when Gemini fails.

OpenAI-compatible chat completions with JSON-schema structured output. Standard library only.
The API key goes only in the Authorization header and is scrubbed from error messages.
"""
import copy
import json
import re
import time
import urllib.error
import urllib.request

import config

_THINK = re.compile(r"<think>.*?</think>", re.S)


class QwenCloudError(Exception):
    pass


def configured():
    return bool(config.OPENROUTER_API_KEY)


def _scrub(text):
    text = str(text)
    if config.OPENROUTER_API_KEY:
        text = text.replace(config.OPENROUTER_API_KEY, "[redacted]")
    return text


def _strict(schema):
    """Strict structured output needs additionalProperties:false on every object."""
    s = copy.deepcopy(schema)
    if s.get("type") == "object":
        s["additionalProperties"] = False
        s["properties"] = {k: _strict(v) for k, v in s.get("properties", {}).items()}
    return s


def chat(system, user, max_tokens=None, temperature=None, json_schema=None):
    if not configured():
        raise QwenCloudError("Hosted Qwen fallback is not configured (OPENROUTER_API_KEY is not set).")
    payload = {
        "model": config.QWEN_CLOUD_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens or config.QWEN_MAX_TOKENS,
        "temperature": temperature or config.QWEN_TEMPERATURE,
        "provider": {"require_parameters": True},
    }
    if json_schema:
        payload["response_format"] = {"type": "json_schema",
                                      "json_schema": {"name": "game_turn", "strict": True, "schema": _strict(json_schema)}}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", method="POST",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                                          "X-Title": "The Tale of Suryagarh"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=config.GEMINI_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise QwenCloudError(_scrub(f"Hosted Qwen returned HTTP {e.code}. {msg[:200]}").strip())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise QwenCloudError(_scrub(f"Cannot reach hosted Qwen ({type(e).__name__})."))
    try:
        text = _THINK.sub("", data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        raise QwenCloudError("Hosted Qwen returned an unexpected response.")
    if len(text) < 20:
        raise QwenCloudError("Hosted Qwen returned an empty reply.")
    return {"text": text, "model": data.get("model") or config.QWEN_CLOUD_MODEL,
            "ms": int((time.time() - t0) * 1000), "tokens": (data.get("usage") or {}).get("completion_tokens")}
