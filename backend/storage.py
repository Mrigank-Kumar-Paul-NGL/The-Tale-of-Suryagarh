"""Where saves live.

Cloud (SUPABASE_URL + SUPABASE_SECRET_KEY set): one row per player in Supabase `player_saves`,
keyed by sha256(player token). The token is a random value the browser generates and keeps.
Local (no Supabase config): the single file saves/save.json, as before.

The Supabase secret key is used only server-side, in the `apikey` header, and never logged or returned.
"""
import contextvars
import datetime
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import config

_player = contextvars.ContextVar("player_hash", default=None)
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class StorageError(Exception):
    pass


def set_player(token):
    """Bind the current request to a player. Returns the player hash, or None if the token is invalid."""
    if not token or not TOKEN_RE.match(token):
        _player.set(None)
        return None
    h = hashlib.sha256(token.encode()).hexdigest()
    _player.set(h)
    return h


def player():
    return _player.get()


# ---------- Supabase REST (PostgREST) ----------

def _sb(method, path, body=None, prefer=None):
    key = config.SUPABASE_SECRET_KEY
    headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
    if key.startswith("eyJ"):  # legacy service_role JWT
        headers["Authorization"] = f"Bearer {key}"
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(f"{config.SUPABASE_URL}/rest/v1/{path}", method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise StorageError(f"Save service returned HTTP {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise StorageError("Save service unreachable.")


def _require_player():
    h = _player.get()
    if not h:
        raise StorageError("Missing player id.")
    return h


# ---------- public API used by game.py / server.py ----------

def load_raw():
    if config.CLOUD:
        h = _require_player()
        rows = _sb("GET", f"player_saves?player_hash=eq.{h}&select=state")
        return rows[0]["state"] if rows else None
    if not config.SAVE_FILE.exists():
        return None
    try:
        return json.loads(config.SAVE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_raw(state):
    if config.CLOUD:
        h = _require_player()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _sb("POST", "player_saves", {"player_hash": h, "state": state, "updated_at": now},
            prefer="resolution=merge-duplicates,return=minimal")
        return
    config.SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.SAVE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(config.SAVE_FILE)


def delete_raw():
    if config.CLOUD:
        h = _require_player()
        _sb("DELETE", f"player_saves?player_hash=eq.{h}", prefer="return=minimal")
        return
    if config.SAVE_FILE.exists():
        config.SAVE_FILE.unlink()


def rate_ok(bucket, window_s, limit):
    """Count one hit against a bucket; False if over the limit. Always allowed when running locally."""
    if not config.CLOUD:
        return True
    bucket = hashlib.sha256(bucket.encode()).hexdigest()[:40]  # don't store raw IPs
    return bool(_sb("POST", "rpc/hit_rate_limit",
                    {"p_bucket": bucket, "p_window_seconds": window_s, "p_limit": limit}))
