"""Balance check for combat_config.py. Not used by the game.

Plays each encounter many times with simple bot players. Enemy intents are picked at random from the
legal list here (in the real game Qwen picks them), so treat results as a rough guide.

    python3 backend/sim.py [runs]
"""
import copy
import random
import statistics
import sys

import combat
import combat_config as C
import game


def fresh_state(health=100):
    s = {"stats": copy.deepcopy(game.START), "inventory": dict(C.STARTER_ITEMS), "combat": None}
    s["stats"]["health"] = health
    return s


AGGRESSIVE = False


def pick_intents(c, enc):
    chosen = {}
    for e in c["enemies"]:
        legal = combat.legal_moves(c, e)
        if not legal:
            continue
        attacks = [m for m in legal if combat.move(e, m)["attack"]]
        chosen[e["id"]] = random.choice(attacks if AGGRESSIVE and attacks and random.random() < 0.85 else legal)
    combat.apply_intents(c, chosen, enc["max_attackers"])


def incoming(c):
    out = []
    for e in c["enemies"]:
        if combat.alive(e) and e["intent"]:
            m = combat.move(e, e["intent"])
            if m["attack"]:
                out.append(m["type"])
    return out


def reckless(state):
    s, c = state["stats"], state["combat"]
    tgt = next(t for t in combat.targets(c) if t["enabled"])
    if s["stamina"] >= 25:
        return "heavy", tgt["id"]
    if s["stamina"] >= 15:
        return "light", tgt["id"]
    return "recover", None


def sensible(state):
    s, c, inv = state["stats"], state["combat"], state["inventory"]
    ts = [t for t in combat.targets(c) if t["enabled"]]
    exposed = next((t for t in ts if "EXPOSED" in t["note"]), None)
    if exposed and s["stamina"] >= 25:
        return "heavy", exposed["id"]
    if exposed and s["stamina"] >= 15:
        return "light", exposed["id"]
    inc = incoming(c)
    if s["health"] < 40 and inv.get("health_potion") and len(inc) <= 1:
        return "use:health_potion", None
    if inc and random.random() < 0.4:
        if s["stamina"] >= 10:
            heavyish = sum(t in ("heavy", "ranged", "sweep") for t in inc)
            return ("dodge" if heavyish >= len(inc) / 2 else "parry"), None
        return "guard", None
    # prefer non-body targets on hide enemies
    good = [t for t in ts if "Thick hide" not in t["note"]] or ts
    if not good:
        return "guard", None
    tgt = min(good, key=lambda t: combat.enemy(c, t["id"].split(":")[0])["hp"])
    if all("Thick hide" in t["note"] for t in good) and not exposed:
        return ("recover" if s["stamina"] < 60 else "guard"), None
    if s["stamina"] >= 40:
        return "heavy", tgt["id"]
    if s["stamina"] >= 15:
        return "light", tgt["id"]
    return ("use:stamina_potion", None) if inv.get("stamina_potion") else ("recover", None)


def run(enc_id, policy, runs, health=100):
    wins, hp_left, turns, potions = 0, [], [], []
    for _ in range(runs):
        st = fresh_state(health)
        combat.start(st, enc_id)
        enc = C.ENCOUNTERS[enc_id]
        c = st["combat"]
        while c["outcome"] is None and c["turn"] < 80:
            c["pending"] = None
            pick_intents(c, enc)
            a, t = policy(st)
            try:
                combat.resolve(st, a, t)
            except combat.CombatError:
                combat.resolve(st, "guard", None)
        c["pending"] = None
        if c["outcome"] == "victory":
            wins += 1
            hp_left.append(st["stats"]["health"])
        turns.append(c["turn"])
        potions.append(2 - st["inventory"]["health_potion"])
    hp = f"{statistics.mean(hp_left):5.1f}" if hp_left else "  -  "
    print(f"  {enc_id:15} {policy.__name__:9} start HP {health:3}: win {wins / runs:6.1%}  "
          f"HP left {hp}  turns {statistics.mean(turns):4.1f}  health potions used {statistics.mean(potions):.2f}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    AGGRESSIVE = "--aggressive" in sys.argv
    print("enemy intents:", "aggressive (85% attack)" if AGGRESSIVE else "random")
    for enc in C.ENCOUNTERS:
        for pol in (reckless, sensible):
            run(enc, pol, n)
    print("  -- starting hurt --")
    run("soot", sensible, n, health=60)
    run("brute", sensible, n, health=70)
