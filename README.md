# The Tale of Suryagarh

### ▶ [Play now: tale-of-suryagarh.vercel.app](https://tale-of-suryagarh.vercel.app)

*Suryagarh has not seen the sun for seven days.* A brass wheel turns in the sky each dawn but never opens.
Shadows creep across the rooftops, people are forgetting their own names, and asura raiders are pushing
toward the palace. The ruler blames the dragon **Agnivara** for stealing the sun. Not everyone believes it.

**The Tale of Suryagarh** is a dark-fantasy text RPG inspired by ancient India, narrated live by an AI
dungeon master. Every playthrough is told fresh, but the rules are real: every roll, hit and coin is decided
by the game engine, and bad decisions can get you killed.

**What you do**

- **Forge your hero.** Pick a name, ancestry (Human, Vanara or Naga-blooded), origin, and appearance.
  The story remembers who you are and where you came from.
- **Fight with your wits.** Read each enemy's tell, then strike, dodge, parry or guard. Manage Stamina
  and Magicka, and drink potions at the right moment.
- **Earn your gear.** Loot gold, take optional contracts, and buy potions, enchantments (Sharpness,
  Suryataap, Shield ward) and armour up to the legendary **Swarna Heer** set.
- **Descend beneath the palace.** Fight through the Sun Market, a soot creature bound to three trees,
  a tavern brute, the Outer Hall, the Broken Causeway, and the priest Vajraka's ward of stone-winged
  Shilapaksha.
- **Face Agnivara**, then make a choice that decides what wakes beneath the city. There are three endings.

No install or account needed. Your progress saves automatically in your browser.

---

## Architecture

```
browser (web/, static on Vercel)
   │  fetch /api/*  + X-Player-Token (random id kept in the browser)
   ▼
Vercel Python function  api/index.py  →  backend/server.py (game engine, stdlib only)
   │                         │
   │                         ├── Gemini API (primary narrator)
   │                         └── OpenRouter hosted Qwen 3 (fallback narrator)
   ▼
Supabase Postgres: player_saves (one row per player), rate_limits
```

- Every browser gets an anonymous player id; the server stores `sha256(id)` → save in Supabase.
- Tables have Row Level Security on and no browser access; only the server (secret key) reads/writes.
- Model calls are rate-limited per player and per IP (`RATE_LIMITS` in `backend/config.py`).
- If no narrator is available the game shows a retryable error. It never substitutes fixed text.

## Deploy (Vercel + Supabase)

1. **Supabase:** create a project and run the migration in `supabase/migrations/` (tables + `hit_rate_limit`).
2. **Vercel:** import this repo (no build step; `vercel.json` serves `web/` and routes `/api/*` to `api/index.py`).
3. **Environment variables** (Vercel → Project → Settings → Environment Variables):

   | Name | Required | Notes |
   | --- | --- | --- |
   | `GEMINI_API_KEY` | yes | https://aistudio.google.com/apikey |
   | `SUPABASE_URL` | yes | `https://<ref>.supabase.co` |
   | `SUPABASE_SECRET_KEY` | yes | Supabase → Project Settings → API Keys → **secret** key (`sb_secret_…`) |
   | `OPENROUTER_API_KEY` | no | enables the hosted Qwen fallback (https://openrouter.ai/keys) |
   | `GEMINI_MODEL` | no | default `gemini-3.5-flash-lite` |
   | `QWEN_CLOUD_MODEL` | no | default `qwen/qwen3-30b-a3b-instruct-2507` |

   Redeploy after changing variables. Secrets live only in Vercel; never in the repo or the browser.

## Run locally

```
cp .env.example .env        # fill in GEMINI_API_KEY (and optionally the others); .env is git-ignored
python3 backend/server.py   # Python 3.9+, no packages needed
open http://127.0.0.1:8000
```

Without `SUPABASE_URL`/`SUPABASE_SECRET_KEY` the game saves to `saves/save.json`.
Local Ollama Qwen is never used on the hosted site. On a laptop it is opt-in only: install Ollama,
`ollama pull qwen3:8b-q4_K_M`, then set `ALLOW_LOCAL_QWEN=1` (last-resort fallback) or `LLM_PROVIDER=qwen` (primary).

## Code map

- `backend/game.py` – game state, scenes, checkpoints; `backend/storage.py` – Supabase / file saves
- `backend/combat.py`, `backend/combat_config.py` – combat engine and every tunable number (`python3 backend/sim.py` for balance)
- `backend/shop.py` – gold, gear, weight, contracts; `backend/story.py` – story facts, scenes, prompts
- `backend/llm.py` – narrator chain; `gemini.py`, `qwen_cloud.py`, `qwen.py` – model clients; `narrator.py` – combat prompts
- `backend/server.py` – HTTP API (also run directly for local play); `api/index.py` – Vercel entry point
- `web/` – HTML/CSS/JS-module frontend (no build step)

## Assets (optional)

Scene art: `web/assets/art/<key>.jpg` (keys: `arrival`, `sun_market`, `arcanium`, `tavern`, `palace`, `dungeon`,
`crystal_chamber`, `ending`). Missing files are ignored.

## License

MIT — see [LICENSE](LICENSE).
