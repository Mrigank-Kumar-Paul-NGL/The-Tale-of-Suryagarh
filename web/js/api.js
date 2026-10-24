// Thin wrapper around the Python backend. All game rules live in Python.
//
// Where the backend lives:
//   - Cloud (Vercel) and local play: same origin, apiBase "".
//   - Hosted frontend: web/config.js sets window.GAME_CONFIG.apiBase, or open the page with
//     ?api=https://<your-tunnel-host> (remembered in this browser).
// Remote access needs the host's access key, typed by the player and kept in this browser session only.

const params = new URLSearchParams(location.search);
const fromQuery = params.get("api");
if (fromQuery) {
  try { localStorage.setItem("gameApiBase", fromQuery); } catch {}
}
let saved = "";
try { saved = localStorage.getItem("gameApiBase") || ""; } catch {}
export const API_BASE = (fromQuery || saved || window.GAME_CONFIG?.apiBase || "").replace(/\/+$/, "");

// Anonymous player id: random, generated once per browser, used by the server to find this player's save.
function playerToken() {
  let t = "";
  try { t = localStorage.getItem("playerToken") || ""; } catch {}
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(t)) {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    t = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    try { localStorage.setItem("playerToken", t); } catch {}
  }
  return t;
}
const PLAYER = playerToken();

function getKey() {
  try { return sessionStorage.getItem("gameKey") || ""; } catch { return ""; }
}

let keyPrompt = null;
function askKey(message) {
  // One prompt at a time, even if several requests fail together.
  keyPrompt ||= Promise.resolve().then(() => {
    const k = window.prompt(message || "Enter the access key from the game host:");
    keyPrompt = null;
    if (k) {
      try { sessionStorage.setItem("gameKey", k.trim()); } catch {}
    }
    return Boolean(k);
  });
  return keyPrompt;
}

async function call(method, path, body, retried = false) {
  let res;
  try {
    const headers = body ? { "Content-Type": "application/json" } : {};
    headers["X-Player-Token"] = PLAYER;
    const key = getKey();
    if (key) headers["X-Game-Key"] = key;
    res = await fetch(API_BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw Object.assign(new Error(API_BASE
      ? `Cannot reach the game server at ${API_BASE}. The host's laptop or tunnel may be offline.`
      : "Cannot reach the game server. Check your connection and retry."), { server: true });
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !retried) {
    if (await askKey(getKey() ? "That access key was rejected. Enter the access key from the game host:" : undefined)) {
      return call(method, path, body, true);
    }
  }
  if (!res.ok) throw Object.assign(new Error(data.error || `Request failed (${res.status})`), data);
  return data;
}

export const api = {
  status: () => call("GET", "/api/status"),
  state: () => call("GET", "/api/state"),
  newGame: (fields) => call("POST", "/api/new", fields),
  reset: () => call("POST", "/api/reset"),
  action: (id) => call("POST", "/api/action", { id }),
  narrate: () => call("POST", "/api/narrate"),
  combat: (action, target) => call("POST", "/api/combat", { action, target }),
  retry: () => call("POST", "/api/retry"),
  shop: (op, id) => call("POST", "/api/shop", { op, id }),
};
