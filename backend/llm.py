"""Model router. Narration, dialogue and enemy-move picks only; Python stays authoritative for game state.

Default: Gemini -> hosted Qwen 3 (OpenRouter). Local Ollama Qwen is never used on the hosted site;
on a laptop it is used only when explicitly enabled (ALLOW_LOCAL_QWEN=1, or LLM_PROVIDER=qwen to make it primary).

Each result carries {text, model, ms, tokens, provider, fallback}.
"""
import config
import gemini
import qwen
import qwen_cloud

LABELS = {"gemini": "Google Gemini", "qwen_cloud": "Qwen (hosted)", "qwen_local": "Qwen (local)"}


class LLMError(Exception):
    pass


def _order():
    order = (["gemini", "qwen_cloud", "qwen_local"] if config.LLM_PROVIDER == "gemini"
             else ["qwen_local", "gemini", "qwen_cloud"])
    if not config.ALLOW_LOCAL_QWEN:
        order = [p for p in order if p != "qwen_local"]  # never on the hosted site; opt-in on a laptop
    return order


def _available(p):
    return {"gemini": gemini.configured, "qwen_cloud": qwen_cloud.configured, "qwen_local": lambda: True}[p]()


def _call(p, system, user, kw):
    if p == "gemini":
        return gemini.chat(system, user, **kw)
    if p == "qwen_cloud":
        return qwen_cloud.chat(system, user, **kw)
    return qwen.chat(system, user, **kw)


def chat(system, user, max_tokens=None, temperature=None, json_schema=None):
    kw = {"max_tokens": max_tokens, "temperature": temperature, "json_schema": json_schema}
    order = _order()
    errors = []
    for i, p in enumerate(order):
        if not _available(p):
            continue
        try:
            res = _call(p, system, user, kw)
            return {**res, "provider": p, "fallback": p != order[0]}
        except qwen.QwenError as e:
            if not e.unavailable:  # local Qwen is up but replied badly: retry, don't switch providers
                raise LLMError(f"{e} Please retry.")
            errors.append(f"{LABELS[p]}: {e}")
        except (gemini.GeminiError, qwen_cloud.QwenCloudError) as e:
            errors.append(f"{LABELS[p]}: {e}")
    if not errors:
        raise LLMError("No narrator is configured: add GEMINI_API_KEY (and optionally OPENROUTER_API_KEY) to the server environment.")
    raise LLMError("The narrator is unavailable right now. " + " | ".join(errors) + " Please retry.")


def status():
    missing = config.setup_missing()
    if missing:
        return {"runtime": "gemini", "ok": False, "state": "setup", "model": config.GEMINI_MODEL, "chain": [],
                "setup_missing": missing,
                "error": "Server setup incomplete: " + ", ".join(missing) + " not set in the hosting environment.",
                "fallback": {"provider": "qwen_cloud", "configured": qwen_cloud.configured(), "model": config.QWEN_CLOUD_MODEL}}
    order = [p for p in _order() if _available(p)]
    primary = _order()[0]
    out = {"runtime": "gemini" if primary == "gemini" else "ollama",
           "chain": [{"id": p, "label": LABELS[p]} for p in order],
           "fallback": {"provider": "qwen_cloud", "configured": qwen_cloud.configured(), "model": config.QWEN_CLOUD_MODEL}}
    if primary == "gemini":
        ok = gemini.configured()
        out.update(model=config.GEMINI_MODEL, ok=ok or qwen_cloud.configured(),
                   state="online" if ok else ("fallback" if qwen_cloud.configured() else "missing_key"),
                   error="" if ok else "Gemini is not configured on the server.")
        return out
    s = qwen.status()
    s.update(chain=out["chain"], fallback={"provider": "gemini", "configured": gemini.configured(), "model": config.GEMINI_MODEL})
    if not s["ok"] and gemini.configured():
        s["state"] = "fallback"
    return s
