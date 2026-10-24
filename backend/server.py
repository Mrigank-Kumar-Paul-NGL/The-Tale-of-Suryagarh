"""HTTP API for the game (and the static UI when run locally).

Local:  python3 backend/server.py   then open http://127.0.0.1:8000
Cloud:  api/index.py exposes the same Handler as a Vercel Python function; Supabase stores saves.
Standard library only.
"""
import fnmatch
import hmac
import json
import mimetypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config   # noqa: E402
import game     # noqa: E402
import llm      # noqa: E402
import narrator  # noqa: E402
import storage  # noqa: E402
import story    # noqa: E402

mimetypes.add_type("text/javascript", ".js")
LOCK = threading.Lock()  # one state mutation / model call at a time per process


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[http] " + (fmt % args) + "\n")

    # ---------- routing ----------
    def _route(self):
        """Return the API path. On Vercel, /api/<x> is rewritten to /api/index?route=<x>."""
        u = urlparse(self.path)
        route = parse_qs(u.query).get("route", [None])[0]
        if u.path in ("/api/index", "/api/index.py", "/api") and route:
            return "/api/" + route.strip("/")
        return u.path

    def _client_ip(self):
        fwd = self.headers.get("X-Forwarded-For") or self.headers.get("X-Real-Ip") or ""
        return fwd.split(",")[0].strip() or (self.client_address[0] if self.client_address else "unknown")

    # ---------- access guard ----------
    def _origin_allowed(self):
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if not origin or origin in config.LOCAL_ORIGINS:
            return True
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").lower()
        if host and urlparse(origin).netloc.lower() == host:
            return True  # same-origin request (cloud build serves UI and API from one domain)
        return any(fnmatch.fnmatchcase(origin, pat) for pat in config.ALLOWED_ORIGINS)

    def _is_remote(self):
        """True if the request came through a tunnel/proxy rather than straight from this machine."""
        if any(self.headers.get(h) for h in ("Cf-Connecting-Ip", "Cf-Ray", "X-Forwarded-For", "X-Forwarded-Host")):
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host not in ("127.0.0.1", "localhost", "::1")

    def _guard(self):
        """Return (code, error) if the request must be refused, else None."""
        if not self._origin_allowed():
            return 403, "This website is not allowed to use this game server."
        if config.PUBLIC_PLAY or not self._is_remote():
            return None
        # Laptop exposed through a tunnel: require the host's access key.
        if len(config.ACCESS_KEY) < config.ACCESS_KEY_MIN_LEN:
            return 403, "Remote play is disabled: the host has not set GAME_ACCESS_KEY."
        given = self.headers.get("X-Game-Key") or ""
        if not hmac.compare_digest(given.encode(), config.ACCESS_KEY.encode()):
            return 401, "Access key required."
        return None

    def _bind_player(self):
        """Attach this request to the browser's anonymous player id. Required for saves in the cloud."""
        h = storage.set_player(self.headers.get("X-Player-Token"))
        if config.CLOUD and not h:
            return 400, "Missing or invalid player id. Reload the page."
        return None

    def _limit(self, name, key):
        window, limit = config.RATE_LIMITS[name]
        if not storage.rate_ok(f"{name}:{key}", window, limit):
            return 429, "Too many requests for now. Take a breath and try again in a while."
        return None

    # ---------- responses ----------
    def _cors(self):
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        if not self._origin_allowed():
            self.send_error(403)
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Game-Key, X-Player-Token")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except json.JSONDecodeError:
            return {}

    # ---------- handlers ----------
    def do_GET(self):
        path = self._route()
        if path.startswith("/api/"):
            denied = self._guard()
            if denied:
                return self._json(denied[0], {"error": denied[1]})
            if path == "/api/status":
                return self._json(200, llm.status())
            if path == "/api/state":
                denied = self._bind_player()
                if denied:
                    return self._json(denied[0], {"error": denied[1]})
                try:
                    return self._json(200, game.view(game.load()))
                except storage.StorageError as e:
                    return self._json(503, {"error": f"{e} Please retry."})
            return self._json(404, {"error": "Unknown endpoint."})
        if self._is_remote() and not config.PUBLIC_PLAY:
            self.send_error(404)  # a tunnel only exposes the API
            return
        return self._static(path)

    def do_POST(self):
        path = self._route()
        denied = self._guard() or self._bind_player()
        if denied:
            return self._json(denied[0], {"error": denied[1]})
        body = self._body()
        try:
            with LOCK:
                if path == "/api/new":
                    denied = self._limit("new_ip", self._client_ip())
                    if denied:
                        return self._json(denied[0], {"error": denied[1]})
                    return self._json(200, game.view(game.new_game(body)))
                if path == "/api/reset":
                    game.delete()
                    return self._json(200, game.view(None))
                state = game.load()
                if state is None:
                    return self._json(400, {"error": "No saved game."})
                if path == "/api/action":
                    return self._json(200, game.view(game.apply_action(state, body.get("id"))))
                if path == "/api/combat":
                    game.combat_turn(state, str(body.get("action", "")), body.get("target"))
                    return self._json(200, game.view(state))
                if path == "/api/shop":
                    game.shop_op(state, str(body.get("op", "")), str(body.get("id", "")))
                    return self._json(200, game.view(state))
                if path == "/api/retry":
                    return self._json(200, game.view(game.apply_action(state, "retry")))
                if path == "/api/narrate":
                    if game.needs_narration(state):
                        denied = (self._limit("narrate_player", storage.player() or "local")
                                  or self._limit("narrate_ip", self._client_ip()))
                        if denied:
                            return self._json(denied[0], {"error": denied[1], "model_error": True})
                        if state.get("combat"):
                            narrator.narrate_turn(state)  # raises before touching state if the model fails
                            game.save(state)
                        else:
                            system, user = story.build_prompt(state, state["scene"])
                            game.record_narration(state, llm.chat(system, user))
                    return self._json(200, game.view(state))
            return self._json(404, {"error": "Unknown endpoint."})
        except game.GameError as e:
            return self._json(400, {"error": str(e)})
        except llm.LLMError as e:
            return self._json(503, {"error": str(e), "model_error": True})
        except storage.StorageError as e:
            return self._json(503, {"error": f"{e} Please retry."})

    def _static(self, path):
        if path == "/":
            path = "/index.html"
        target = (config.WEB_DIR / path.lstrip("/")).resolve()
        if config.WEB_DIR.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    s = llm.status()
    print("Narrator chain:", " -> ".join(c["label"] for c in s["chain"]) or "NONE CONFIGURED")
    if not s["ok"]:
        print("  WARNING:", s.get("error"))
    print(f"Saves: {'Supabase (cloud)' if config.CLOUD else config.SAVE_FILE}")
    print(f"Game running at http://{config.HOST}:{config.PORT}")
    if config.PUBLIC_PLAY:
        print("Public play ON (no access key; per-player saves and rate limits).")
    elif len(config.ACCESS_KEY) >= config.ACCESS_KEY_MIN_LEN:
        print(f"Remote play ON: tunnel requests need the access key. Allowed origins: {config.ALLOWED_ORIGINS or 'none'}")
    else:
        print("Remote play OFF (set GAME_ACCESS_KEY, 16+ chars, to allow tunnel requests).")
    ThreadingHTTPServer((config.HOST, config.PORT), Handler).serve_forever()
