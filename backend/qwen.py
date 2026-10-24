"""Minimal client for the local Ollama server running Qwen 3 8B Q4_K_M.

Uses Ollama's native /api/chat endpoint. No fallback text: on failure a QwenError
is raised and the caller reports it to the UI.
"""
import json
import re
import time
import urllib.error
import urllib.request

import config


class QwenError(Exception):
    def __init__(self, message, unavailable=False):
        super().__init__(message)
        self.unavailable = unavailable  # True = runtime down/unreachable/model missing -> Gemini fallback may be used


def _request(path, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        config.OLLAMA_URL + path, data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        missing = e.code == 404 and "not found" in body.lower()
        raise QwenError(f"Ollama returned HTTP {e.code} for {path}: {body}", unavailable=missing)
    except urllib.error.URLError as e:
        raise QwenError(f"Cannot reach Ollama at {config.OLLAMA_URL} ({e.reason}). "
                        "Start the Ollama app or run `ollama serve`.", unavailable=True)
    except (TimeoutError, ConnectionError) as e:
        raise QwenError(f"Ollama did not respond on {path} ({type(e).__name__}).", unavailable=True)


def status():
    """Report whether Ollama is up, the model is installed, and whether it is loaded in memory."""
    out = {"runtime": "ollama", "url": config.OLLAMA_URL, "model": config.QWEN_MODEL}
    try:
        tags = _request("/api/tags")
    except QwenError as e:
        return {**out, "ok": False, "state": "unreachable", "error": str(e)}
    names = [m.get("name") for m in tags.get("models", [])]
    if config.QWEN_MODEL not in names:
        return {**out, "ok": False, "state": "missing",
                "error": f"Model {config.QWEN_MODEL} is not installed. Run: ollama pull {config.QWEN_MODEL}"}
    loaded = False
    try:
        loaded = any(m.get("name") == config.QWEN_MODEL for m in _request("/api/ps").get("models", []))
    except QwenError:
        pass
    return {**out, "ok": True, "state": "loaded" if loaded else "idle"}


_THINK = re.compile(r"<think>.*?</think>", re.S)


def chat(system, user, max_tokens=None, temperature=None, json_schema=None):
    payload = {
        "model": config.QWEN_MODEL,
        "stream": False,
        "think": False,  # Qwen 3 thinking mode is slow and not needed for narration
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "options": {"num_predict": max_tokens or config.QWEN_MAX_TOKENS,
                    "temperature": temperature or config.QWEN_TEMPERATURE},
    }
    if json_schema:
        payload["format"] = json_schema  # Ollama constrains output to this JSON schema
    t0 = time.time()
    data = _request("/api/chat", payload, timeout=config.QWEN_TIMEOUT_S)
    text = _THINK.sub("", data.get("message", {}).get("content", "")).strip()
    if len(text) < 40:
        raise QwenError(f"Qwen returned an empty or truncated reply: {text!r}")
    return {
        "text": text,
        "model": data.get("model"),
        "ms": int((time.time() - t0) * 1000),
        "tokens": data.get("eval_count"),
    }
