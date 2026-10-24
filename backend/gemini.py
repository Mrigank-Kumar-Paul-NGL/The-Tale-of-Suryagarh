"""Gemini fallback client (used only when the local Qwen runtime is unavailable).

Uses the Gemini API's generateContent REST endpoint with the standard library; no extra dependency.
The API key is sent only in the x-goog-api-key header and is scrubbed from every error message.
"""
import json
import time
import urllib.error
import urllib.request

import config


class GeminiError(Exception):
    pass


def configured():
    return bool(config.GEMINI_API_KEY)


def _scrub(text):
    text = str(text)
    if config.GEMINI_API_KEY:
        text = text.replace(config.GEMINI_API_KEY, "[redacted]")
    return text


def _to_gemini_schema(schema):
    """Convert our small JSON Schema (object/string/enum/required) to the Gemini responseSchema format."""
    out = {}
    t = schema.get("type")
    if t:
        out["type"] = t.upper()
    if "enum" in schema:
        out["format"] = "enum"
        out["enum"] = list(schema["enum"])
    if "properties" in schema:
        out["properties"] = {k: _to_gemini_schema(v) for k, v in schema["properties"].items()}
        out["propertyOrdering"] = list(schema["properties"])
    if schema.get("required"):
        out["required"] = list(schema["required"])
    return out


def chat(system, user, max_tokens=None, temperature=None, json_schema=None):
    if not configured():
        raise GeminiError("Gemini fallback is not configured (GEMINI_API_KEY is not set).")
    gen = {
        "maxOutputTokens": max_tokens or config.QWEN_MAX_TOKENS,
        "temperature": temperature or config.QWEN_TEMPERATURE,
    }
    if json_schema:
        gen["responseMimeType"] = "application/json"
        gen["responseSchema"] = _to_gemini_schema(json_schema)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": gen,
    }
    url = f"{config.GEMINI_BASE_URL}/models/{config.GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "x-goog-api-key": config.GEMINI_API_KEY})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=config.GEMINI_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise GeminiError(_scrub(f"Gemini returned HTTP {e.code}. {msg[:200]}").strip())
    except urllib.error.URLError as e:
        raise GeminiError(_scrub(f"Cannot reach the Gemini API ({e.reason}). Gemini fallback needs internet access."))
    except TimeoutError:
        raise GeminiError(f"Gemini timed out after {config.GEMINI_TIMEOUT_S}s.")
    except (ValueError, OSError) as e:
        raise GeminiError(_scrub(f"Gemini request failed: {e}"))

    block = (data.get("promptFeedback") or {}).get("blockReason")
    if block:
        raise GeminiError(f"Gemini blocked the request ({block}).")
    cands = data.get("candidates") or []
    if not cands:
        raise GeminiError("Gemini returned no candidates.")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if len(text) < 20:
        raise GeminiError(f"Gemini returned an empty or truncated reply (finishReason {cands[0].get('finishReason')}).")
    return {
        "text": text,
        "model": data.get("modelVersion") or config.GEMINI_MODEL,
        "ms": int((time.time() - t0) * 1000),
        "tokens": (data.get("usageMetadata") or {}).get("candidatesTokenCount"),
    }
