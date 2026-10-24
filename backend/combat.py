"""Authoritative turn-based combat. All rolls and state changes happen here.

Turn order:
  1. Enemies show intents (tells) chosen in the previous narration step.
  2. The player picks one action. Attacks and items resolve first.
  3. Each enemy carries out its intent; the player's stance (dodge/parry/guard) is rolled per attack.
  4. Burns tick, Stamina regenerates, victory/defeat is checked.
  5. Qwen narrates the resolved events and picks next intents from the legal list (see narrator.py).
"""
import random

import combat_config as C

rng = random.Random()


class CombatError(Exception):
    pass


# ---------- helpers ----------

def kind(e):
    return C.ENEMIES[e["kind"]]


def alive(e):
    return e["hp"] > 0


def bound(c, e):
    if kind(e).get("warded"):
        return not c["mech"]["broken"]
    return kind(e).get("bound") and any(alive(x) and kind(x).get("passive") for x in c["enemies"])


def mech(c):
    return c.get("mech") or {}


def _new_enemy(eid, k, name=None):
    d = C.ENEMIES[k]
    return {"id": eid, "kind": k, "name": name or d["name"], "hp": d["hp"], "hp_max": d["hp"],
            "intent": None, "exposed": False, "statuses": []}


def _spawn_wave(c, events):
    m = c["mech"]
    n = C.WARD["waves"][min(m["wave"], len(C.WARD["waves"])) - 1]
    for i in range(1, n + 1):
        c["enemies"].append(_new_enemy(f"shila_{m['wave']}_{i}", "shilapaksha", f"Shilapaksha {m['wave']}.{i}"))
    ev(events, "effect", f"Vajraka summons wave {m['wave']}: {n} Shilapaksha. His shield is UP.",
       f"Vajraka chants and {n} stone-winged Shilapaksha tear free of the walls; his shield blazes.")


def enemy(c, eid):
    return next((e for e in c["enemies"] if e["id"] == eid), None)


def move(e, move_id):
    d = kind(e)
    if move_id in d["attacks"]:
        return {**d["attacks"][move_id], "attack": True}
    if move_id in d["idle"]:
        return {**d["idle"][move_id], "attack": False}
    if move_id == "recover":
        return {"label": "Recovering", "tell": "is off balance, struggling to recover", "attack": False}
    return None


def condition(hp, hp_max):
    r = hp / hp_max
    if hp <= 0:
        return "defeated"
    return "unhurt" if r >= 0.95 else "lightly wounded" if r > 0.6 else "wounded" if r > 0.3 else "badly wounded"


def weapon(state):
    return C.WEAPONS[state["stats"]["equipment"]["weapon_id"]]


def armour_reduction(state):
    eq = state["stats"]["equipment"]
    total = sum(C.ARMOUR.get(eq.get(slot) or "", 0) for slot in ("helmet", "cuirass", "boots"))
    return min(total, C.ARMOUR_CAP)


def resources(state):
    s = state["stats"]
    return f"Health {s['health']}/{s['health_max']} · Stamina {s['stamina']}/{s['stamina_max']} · Magicka {s['magicka']}/{s['magicka_max']}"


def ev(events, who, text, story=None):
    events.append({"who": who, "text": text, "story": story})


# ---------- setup ----------

def start(state, enc_id):
    enc = C.ENCOUNTERS[enc_id]
    enemies = [_new_enemy(eid, k, name) for eid, k, name in enc["enemies"]]
    events = []
    ev(events, "system", f"{enc['title']} begins. {enc['goal']}", f"The fight begins: {enc['goal']}")
    c = {"id": enc_id, "turn": 0, "enemies": enemies, "log": [], "outcome": None,
         "narration": None, "pending": {"turn": 0, "events": events}, "mech": None}
    if enc.get("mech") == "ward":
        c["mech"] = {"type": "ward", "wave": 1, "broken": False, "windows": 0, "left": 0}
        _spawn_wave(c, events)
    elif enc.get("mech") == "dragon":
        c["mech"] = {"type": "dragon", "phase": "air", "hits": 0,
                     "need": rng.randint(*C.DRAGON["arrows_needed"]), "ground_left": 0, "stunned": False}
    state["combat"] = c
    _log(state["combat"], 0, events)


def _log(c, turn, events):
    c["log"].extend({"turn": turn, "who": e["who"], "text": e["text"]} for e in events)
    c["log"] = c["log"][-120:]


# ---------- what the player may do ----------

def targets(c):
    out = []
    for e in c["enemies"]:
        if not alive(e):
            continue
        d = kind(e)
        if d.get("weak_point"):
            wp = d["weak_point"]
            out.append({"id": e["id"], "label": f"{e['name']} (body)", "enabled": True,
                        "note": f"Thick hide: body hits deal {int(d['hide'] * 100)}% damage."})
            out.append({"id": f"{e['id']}:{wp['id']}", "label": wp["label"], "enabled": e["exposed"],
                        "note": "EXPOSED — strike now!" if e["exposed"] else
                        "Covered. A clean dodge or parry throws it off balance and exposes it."})
        elif d.get("dragon"):
            m = c["mech"]
            if m["phase"] == "air":
                out.append({"id": e["id"], "label": "Agnivara (airborne)", "enabled": True,
                            "note": f"Out of blade reach: shoot arrows ({m['hits']}/{m['need']} hits to bring it down)."})
            else:
                out.append({"id": e["id"], "label": "Agnivara (grounded)", "enabled": True,
                            "note": "GROUNDED, EXPOSED to blades — strike now!"})
        elif bound(c, e):
            out.append({"id": e["id"], "label": d.get("target_label", e["name"]), "enabled": False,
                        "note": "Shielded: destroy the Shilapaksha wave to break it." if d.get("warded")
                        else "Shielded while any binding tree stands."})
        else:
            out.append({"id": e["id"], "label": d.get("target_label", e["name"]), "enabled": True, "note": ""})
    return out


def player_actions(state):
    s = state["stats"]
    ench = s["equipment"].get("enchant")
    out = []
    m = mech(state["combat"])
    for aid, a in C.PLAYER_ACTIONS.items():
        if a.get("only_mech") and a["only_mech"] != m.get("type"):
            continue
        cost = a["stamina"]
        reason = ""
        if aid == "shoot" and m.get("phase") != "air":
            reason = "Agnivara is grounded — use your blade."
        if not reason and s["stamina"] < cost:
            reason = (f"Not enough Stamina (need {cost}, have {s['stamina']}). "
                      "Guard, Catch breath, or drink a Stamina potion.")
        magicka = (C.ENCHANTMENTS[ench]["magicka"] if ench and a["target"] and aid != "shoot"
                   and "guard_bonus" not in C.ENCHANTMENTS[ench] else 0)
        if aid == "guard" and ench == "shield":
            magicka = C.ENCHANTMENTS["shield"]["magicka"]
        out.append({"id": aid, "label": a["label"], "stamina": cost, "magicka": magicka,
                    "target": a["target"], "enabled": not reason, "reason": reason})
    for iid, n in state["inventory"].items():
        if n > 0 and iid in C.ITEMS:
            out.append({"id": f"use:{iid}", "label": f"{C.ITEMS[iid]['label']} ({n})", "stamina": 0, "magicka": 0,
                        "target": False, "enabled": True, "reason": "", "item": True})
    return out


def legal_moves(c, e):
    """Moves this enemy may choose next turn. Python owns this list; Qwen picks from it."""
    if not alive(e) or kind(e).get("passive"):
        return []
    if e["exposed"]:
        return ["recover"]
    d = kind(e)
    if d.get("dragon"):
        m = c["mech"]
        if m["stunned"]:
            return ["recover"]
        return [k for k, v in {**d["attacks"], **d["idle"]}.items() if v.get("phase") == m["phase"]]
    return list(d["attacks"]) + list(d["idle"])


# ---------- resolution ----------

def resolve(state, action_id, target_id=None):
    c = state.get("combat")
    if not c:
        raise CombatError("You are not in combat.")
    if c["outcome"]:
        raise CombatError("This fight is over.")
    if c["pending"]:
        raise CombatError("Wait for the Fates to finish weaving the last turn.")
    s = state["stats"]
    events = []
    c["turn"] += 1
    turn = c["turn"]
    stance = None

    if action_id.startswith("use:"):
        _use_item(state, action_id[4:], events)
    elif action_id in C.PLAYER_ACTIONS:
        a = C.PLAYER_ACTIONS[action_id]
        if s["stamina"] < a["stamina"]:
            c["turn"] -= 1
            raise CombatError(f"Not enough Stamina for {a['label']} (need {a['stamina']}, have {s['stamina']}). "
                              "Try Guard, Catch breath, or a Stamina potion.")
        if a["target"]:
            tgt, part = _check_target(c, target_id)
            m = mech(c)
            if action_id == "shoot":
                if not kind(tgt).get("dragon") or m.get("phase") != "air":
                    c["turn"] -= 1
                    raise CombatError("Arrows are only for bringing down an airborne Agnivara.")
                s["stamina"] -= a["stamina"]
                _shoot(c, tgt, events)
            else:
                if kind(tgt).get("dragon") and m.get("phase") == "air":
                    c["turn"] -= 1
                    raise CombatError("Agnivara is airborne and out of blade reach. Shoot arrows, or break crystals.")
                s["stamina"] -= a["stamina"]
                _player_attack(state, action_id, tgt, part, events)
        else:
            s["stamina"] -= a["stamina"]
            stance = action_id if action_id in ("dodge", "parry", "guard") else None
            if action_id == "recover":
                ev(events, "player", f"You catch your breath (+{C.RECOVER_BONUS} Stamina at end of turn, no defence).",
                   "You step back to catch your breath, leaving yourself open.")
            else:
                ev(events, "player", f"You ready a {a['label'].lower()} (−{a['stamina']} Stamina).",
                   f"You prepare to {a['label'].lower()}.")
    else:
        c["turn"] -= 1
        raise CombatError(f"Unknown action '{action_id}'.")

    # An opening lasts for one player action only.
    for e in c["enemies"]:
        if e["exposed"] and e.get("exposed_turn", turn) < turn:
            e["exposed"] = False

    if stance == "guard":
        _maybe_shield_ward(state, events)

    # Enemy phase
    for e in c["enemies"]:
        if s["health"] <= 0:
            break
        if not alive(e) or not e["intent"]:
            continue
        m = move(e, e["intent"])
        if m and m["attack"]:
            _enemy_attack(state, e, m, stance, events, turn)
        elif m and e["intent"] == "recover":
            ev(events, "enemy", f"{e['name']} recovers its footing.", f"{e['name']} hauls itself back upright.")
        elif m:
            ev(events, "enemy", f"{e['name']}: {m['label'].lower()} (no attack).", f"{e['name']} {m['tell']}.")
        e["last"] = e["intent"]
        e["intent"] = None

    # Burns
    for e in c["enemies"]:
        if not alive(e):
            continue
        for st in list(e["statuses"]):
            if st["id"] == "burn":
                dmg = rng.randint(*st["dmg"])
                e["hp"] = max(0, e["hp"] - dmg)
                st["turns"] -= 1
                ev(events, "effect", f"Suryataap burns {e['name']} for {dmg} ({e['hp']}/{e['hp_max']}).",
                   f"Sun-fire sears {e['name']}.")
                if st["turns"] <= 0:
                    e["statuses"].remove(st)
                if not alive(e):
                    ev(events, "effect", f"{e['name']} is destroyed by the flames.", f"{e['name']} collapses in flame.")

    _mechanics(c, events)

    # Regen and outcome
    s["health"] = max(0, s["health"])
    if s["health"] > 0:
        regen = C.STAMINA_REGEN + (C.RECOVER_BONUS if action_id == "recover" else 0)
        s["stamina"] = min(s["stamina_max"], s["stamina"] + regen)
    if s["health"] <= 0:
        c["outcome"] = "defeat"
        ev(events, "system", "You have fallen. Defeat.", "The player falls and does not rise.")
    elif all(not alive(e) for e in c["enemies"] if not kind(e).get("passive")):
        c["outcome"] = "victory"
        ev(events, "system", "Victory.", "The last enemy is beaten.")
    ev(events, "status", f"You — {resources(state)}")

    _log(c, turn, events)
    c["pending"] = {"turn": turn, "events": events}
    return events


def _check_target(c, target_id):
    if not target_id:
        raise CombatError("Choose a target first.")
    eid, _, part = target_id.partition(":")
    e = enemy(c, eid)
    if not e or not alive(e):
        raise CombatError("That target is not available.")
    t = next((t for t in targets(c) if t["id"] == target_id), None)
    if not t:
        raise CombatError("That target is not available.")
    if not t["enabled"]:
        raise CombatError(f"You can't strike that yet: {t['note']}")
    return e, part or None


def _player_attack(state, kind_id, e, part, events):
    s = state["stats"]
    d = kind(e)
    w = weapon(state)
    label = C.PLAYER_ACTIONS[kind_id]["label"]
    base = rng.randint(*w[kind_id])
    dmg = float(base)
    notes = [f"rolled {base}"]
    blow = {"light": "quick cut", "heavy": "heavy two-handed blow"}[kind_id]
    story = [f"Your {blow} strikes {e['name']}"]

    if rng.random() < C.CRIT_CHANCE[kind_id]:
        dmg *= C.CRIT_MULT
        notes.append(f"CRITICAL ×{C.CRIT_MULT}")
        story.append("a critical blow")

    burn = None
    ench_id = s["equipment"].get("enchant")
    if ench_id and "guard_bonus" in C.ENCHANTMENTS[ench_id]:
        ench_id = None  # the shield ward only works (and only costs Magicka) when guarding
        en = C.ENCHANTMENTS[ench_id]
        if s["magicka"] >= en["magicka"]:
            s["magicka"] -= en["magicka"]
            if "bonus" in en:
                b = rng.randint(*en["bonus"])
                dmg += b
                notes.append(f"{en['label']} +{b} (−{en['magicka']} Magicka)")
            if "burn" in en:
                burn = {"id": "burn", "dmg": en["burn"], "turns": en["turns"]}
                notes.append(f"{en['label']} ignites (−{en['magicka']} Magicka)")
            story.append(f"the {en['label']} enchantment flares")
        elif "guard_bonus" not in en:
            notes.append(f"not enough Magicka for {en['label']} — normal damage only")
            story.append("the enchantment sputters out for lack of magicka")

    if part and d.get("weak_point"):
        dmg *= d["weak_point"]["mult"]
        notes.append(f"weak point ×{d['weak_point']['mult']}")
        story = [f"Your {blow} drives into the {d['weak_point']['label'].lower()} of {e['name']}"] + story[1:]
    elif d.get("hide"):
        dmg *= d["hide"]
        notes.append(f"thick hide ×{d['hide']}")
        story.append("but it barely bites through the thick hide")
    elif d.get("block"):
        chance = d["block"] * (C.HEAVY_BLOCK_FACTOR if kind_id == "heavy" else 1)
        if rng.random() < chance:
            frac = rng.uniform(*d["block_reduce"])
            dmg *= 1 - frac
            notes.append(f"BLOCKED ({int(frac * 100)}% absorbed)")
            story.append("but it blocks part of the blow")

    wall = [x for x in state["combat"]["enemies"] if alive(x) and kind(x).get("shields_allies") and x is not e]
    if wall and not part and not d.get("shields_allies"):
        dmg *= kind(wall[0])["shields_allies"]
        notes.append(f"shield wall ×{kind(wall[0])['shields_allies']}")
        story.append("but the shield-bearers' wall absorbs much of it")

    dmg = max(1, round(dmg))
    floor = 0
    if d.get("warded"):
        floor = int(e["hp_max"] * (1 - min(3, state["combat"]["mech"]["windows"]) / 3))
        if e["hp"] - dmg < floor:
            notes.append("the ward reforms around him before more harm lands")
    e["hp"] = max(floor, e["hp"] - dmg)
    if burn and alive(e):
        e["statuses"] = [x for x in e["statuses"] if x["id"] != "burn"] + [burn]
    ev(events, "player",
       f"{label} → {e['name']}{' (' + d['weak_point']['label'] + ')' if part else ''}: {', '.join(notes)} → {dmg} damage. "
       f"{e['name']} {e['hp']}/{e['hp_max']}.",
       ", ".join(story) + f". It is now {condition(e['hp'], e['hp_max'])}.")
    if not alive(e):
        ev(events, "effect", f"{e['name']} is defeated.", f"{e['name']} falls.")


def _enemy_attack(state, e, m, stance, events, turn):
    s = state["stats"]
    d = kind(e)
    roll = rng.random()
    acc = 0
    for qname, chance, mult in C.ATTACK_QUALITY:
        acc += chance
        if roll < acc:
            break
    raw = rng.randint(*m["dmg"]) * mult
    taken, defence, dstory = 1.0, "unguarded", "you are caught unguarded"
    full = False

    if stance in ("dodge", "parry"):
        table = C.DODGE if stance == "dodge" else C.PARRY
        f, p = table[m["type"]]
        r = rng.random()
        if r < f:
            taken, full = 0.0, True
            defence = f"{stance} FULL SUCCESS"
            dstory = "you slip it completely" if stance == "dodge" else "you turn it aside cleanly"
        elif r < f + p:
            taken = C.DODGE_PARTIAL_TAKEN if stance == "dodge" else C.PARRY_PARTIAL_TAKEN
            defence = f"{stance} partial ({int(taken * 100)}% taken)"
            dstory = "you only half avoid it"
        else:
            defence = f"{stance} mistimed"
            dstory = "you mistime it and take the full blow"
    elif stance == "guard":
        chance = C.GUARD["solid_chance"] + state["combat"].get("ward_bonus", 0)
        if rng.random() < chance:
            taken, defence, dstory = C.GUARD["solid_taken"], f"guard solid ({int(C.GUARD['solid_taken'] * 100)}% taken)", "your guard holds"
        else:
            taken, defence, dstory = C.GUARD["shaky_taken"], f"guard shaky ({int(C.GUARD['shaky_taken'] * 100)}% taken)", "your guard buckles"

    arm = armour_reduction(state)
    dmg = round(raw * taken * (1 - arm))
    s["health"] = max(0, s["health"] - dmg)
    arm_note = f", armour −{int(arm * 100)}%" if arm else ""
    ev(events, "enemy",
       f"{e['name']} — {m['label']} ({m['type']}, {qname}): {defence}{arm_note} → you take {dmg}. Health {s['health']}/{s['health_max']}.",
       f"{e['name']} uses {m['label'].lower()} ({qname}); {dstory}"
       + ("" if dmg else ", taking no harm") + ".")

    if full and m["type"] != "ranged" and s["health"] > 0:
        opens = d.get("opens_on", {})
        if m["type"] in opens.get(stance, []):
            e["exposed"], e["exposed_turn"] = True, turn
            ev(events, "effect", f"{e['name']} is off balance — its {d['weak_point']['label'].lower()} is EXPOSED next turn!",
               f"{e['name']} overcommits and staggers, its {d['weak_point']['label'].lower()} left exposed.")
        elif stance == "parry" and not d.get("weak_point") and not bound(state["combat"], e):
            r = rng.randint(*C.RIPOSTE)
            e["hp"] = max(0, e["hp"] - r)
            ev(events, "player", f"Riposte! {e['name']} takes {r}. {e['name']} {e['hp']}/{e['hp_max']}.",
               f"You riposte into the opening and cut {e['name']}.")
            if not alive(e):
                ev(events, "effect", f"{e['name']} is defeated.", f"{e['name']} falls.")


def _maybe_shield_ward(state, events):
    s = state["stats"]
    state["combat"]["ward_bonus"] = 0
    if s["equipment"].get("enchant") != "shield":
        return
    en = C.ENCHANTMENTS["shield"]
    if s["magicka"] >= en["magicka"]:
        s["magicka"] -= en["magicka"]
        state["combat"]["ward_bonus"] = en["guard_bonus"]
        ev(events, "player", f"Shield ward hums (−{en['magicka']} Magicka, +{int(en['guard_bonus'] * 100)}% solid guard).")
    else:
        ev(events, "player", "Not enough Magicka for the shield ward — plain guard.")


def _use_item(state, item_id, events):
    inv = state["inventory"]
    if item_id not in C.ITEMS or inv.get(item_id, 0) <= 0:
        raise CombatError("You don't have that item.")
    inv[item_id] -= 1
    s = state["stats"]
    parts = []
    for stat, amt in C.ITEMS[item_id]["restore"].items():
        before = s[stat]
        s[stat] = min(s[f"{stat}_max"], s[stat] + amt)
        parts.append(f"+{s[stat] - before} {stat.capitalize()}")
    ev(events, "player", f"You drink a {C.ITEMS[item_id]['label']}: {', '.join(parts)} (no defence this turn).",
       f"You gulp down a {C.ITEMS[item_id]['label'].lower()}, leaving yourself open.")


def _shoot(c, e, events):
    m = c["mech"]
    if rng.random() >= C.ARROW["hit_chance"]:
        ev(events, "player", f"Arrow at {e['name']}: MISS ({int(C.ARROW['hit_chance'] * 100)}% chance).",
           "Your arrow streaks past the dragon's wing.")
        return
    dmg = rng.randint(*C.ARROW["dmg"])
    e["hp"] = max(1, e["hp"] - dmg)
    m["hits"] += 1
    ev(events, "player", f"Arrow HITS {e['name']} for {dmg} ({m['hits']}/{m['need']} to bring it down). "
       f"{e['name']} {e['hp']}/{e['hp_max']}.", "Your arrow punches through the dragon's wing membrane.")
    if m["hits"] >= m["need"]:
        m.update(phase="ground", ground_left=C.DRAGON["ground_turns"], stunned=True, fell_turn=c["turn"])
        e["intent"] = None
        ev(events, "effect", f"{e['name']} CRASHES to the ground! Grounded for {C.DRAGON['ground_turns']} turns after it recovers.",
           "Wounded wings fold and Agnivara crashes to the chamber floor.")
        crystals = [x for x in c["enemies"] if alive(x) and kind(x).get("heals")]
        for x in crystals[:C.DRAGON["crash_shatters"]]:
            x["hp"] = 0
            ev(events, "effect", f"The impact shatters {x['name']}.", f"Its crash shatters {x['name']}.")


def _mechanics(c, events):
    m = mech(c)
    turn = c["turn"]
    if m.get("type") == "ward":
        v = enemy(c, "vajraka")
        if not alive(v):
            for x in c["enemies"]:
                if x["kind"] == "shilapaksha" and alive(x):
                    x["hp"] = 0
            ev(events, "effect", "With Vajraka fallen, the Shilapaksha crumble to rubble.", "The Shilapaksha crumble to rubble.")
            return
        summons = [x for x in c["enemies"] if x["kind"] == "shilapaksha" and alive(x)]
        if not m["broken"] and not summons:
            m.update(broken=True, windows=m["windows"] + 1, left=C.WARD["window_turns"], broke_turn=turn)
            ev(events, "effect", f"Vajraka's SHIELD SHATTERS — window {m['windows']}/3, open for {m['left']} turns. Strike him!",
               "With the last Shilapaksha down, Vajraka's shield shatters like glass.")
        elif m["broken"] and m.get("broke_turn") != turn:
            m["left"] -= 1
            floor = int(v["hp_max"] * (1 - min(3, m["windows"]) / 3))
            if v["hp"] <= floor and m["windows"] < 3:
                m["left"] = 0  # this window's share of damage is dealt; the next wave comes at once
            if m["left"] <= 0:
                m.update(broken=False, wave=m["wave"] + 1)
                _spawn_wave(c, events)
    elif m.get("type") == "dragon":
        a = enemy(c, "agnivara")
        if not alive(a):
            return
        heal = sum(kind(x)["heals"] for x in c["enemies"] if alive(x) and kind(x).get("heals"))
        if heal and a["hp"] < a["hp_max"]:
            before = a["hp"]
            a["hp"] = min(a["hp_max"], a["hp"] + heal)
            ev(events, "effect", f"The crystals pour light into Agnivara: +{a['hp'] - before} ({a['hp']}/{a['hp_max']}).",
               "The surviving crystals pour light into Agnivara's wounds.")
        if m["phase"] == "ground" and m.get("fell_turn") != turn:
            m["stunned"] = False
            m["ground_left"] -= 1
            if m["ground_left"] <= 0:
                m.update(phase="air", hits=0, need=rng.randint(*C.DRAGON["arrows_needed"]))
                ev(events, "effect", f"Agnivara beats its wings and climbs back into the sky ({m['need']} arrow hits to bring it down).",
                   "Agnivara beats its great wings and climbs back into the dark.")


def status_line(c):
    m = mech(c)
    if m.get("type") == "ward":
        shield = f"BROKEN — {m['left']} turn(s) to strike" if m["broken"] else "UP"
        return f"Wave {m['wave']} · Shield {shield} · Windows {m['windows']}/3"
    if m.get("type") == "dragon":
        left = sum(1 for x in c["enemies"] if alive(x) and kind(x).get("heals"))
        phase = (f"AIRBORNE — arrows {m['hits']}/{m['need']}" if m["phase"] == "air"
                 else "GROUNDED — recovering" if m["stunned"] else f"GROUNDED — {m['ground_left']} turn(s) to strike")
        return f"{phase} · Crystals {left}/6"
    return ""


# ---------- after narration ----------

def apply_intents(c, chosen, max_attackers):
    """Validate Qwen's picks against the legal list and the attacker cap. Returns notes on any changes."""
    notes = []
    attackers = 0
    for e in c["enemies"]:
        legal = legal_moves(c, e)
        if not legal:
            e["intent"] = None
            continue
        pick = chosen.get(e["id"])
        if pick not in legal:
            fallback = legal[0]
            notes.append(f"Engine: {e['name']} chose an illegal move ({pick!r}); using {move(e, fallback)['label']}.")
            pick = fallback
        if move(e, pick)["attack"]:
            if attackers >= max_attackers:
                idle = next((m for m in legal if not move(e, m)["attack"]), None)
                if idle:
                    notes.append(f"Engine: {e['name']} holds back (at most {max_attackers} attack at once).")
                    pick = idle
            else:
                attackers += 1
        e["intent"] = pick
    return notes


def view(state):
    c = state["combat"]
    enc = C.ENCOUNTERS[c["id"]]
    enemies = []
    for e in c["enemies"]:
        d = kind(e)
        m = move(e, e["intent"]) if e["intent"] and alive(e) else None
        tags = []
        if not alive(e):
            tags.append("Destroyed" if d.get("passive") else "Defeated")
        if d.get("passive") and alive(e) and not d.get("heals"):
            tags.append("Binding")
        if d.get("heals") and alive(e):
            tags.append("Heals Agnivara")
        if d.get("shields_allies") and alive(e):
            tags.append("Shield wall")
        if d.get("warded") and alive(e):
            tags.append("SHIELD BROKEN — EXPOSED" if c["mech"]["broken"] else "Shield up — invulnerable")
        elif d.get("dragon") and alive(e):
            tags.append("Airborne" if c["mech"]["phase"] == "air" else "GROUNDED — EXPOSED")
        elif bound(c, e):
            tags.append("Bound — invulnerable")
        if e["exposed"]:
            tags.append("Nape EXPOSED")
        tags += [f"Burning ({st['turns']})" for st in e["statuses"] if st["id"] == "burn"]
        enemies.append({
            "id": e["id"], "name": e["name"], "hp": e["hp"], "hp_max": e["hp_max"], "alive": alive(e),
            "passive": bool(d.get("passive")), "tags": tags,
            "intent": None if not m else {"label": m["label"], "tell": m["tell"], "type": m.get("type"),
                                          "attack": m["attack"],
                                          "dmg": m.get("dmg")},
        })
    return {
        "id": c["id"], "title": enc["title"], "goal": enc["goal"], "turn": c["turn"], "outcome": c["outcome"],
        "status": status_line(c),
        "enemies": enemies, "targets": targets(c), "actions": player_actions(state),
        "narration": c["narration"], "log": c["log"][-60:],
        "enchant": state["stats"]["equipment"].get("enchant"),
    }
