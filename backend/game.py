"""Authoritative game state: creation, save/load, scene transitions, combat entry/exit, checkpoints."""
import copy
import json
import time

import appearance
import combat
import combat_config as CC
import config
import shop
import storage
import story

MAX_FIELD = {"name": 40, "pronouns": 30}
MAX_DETAILS = 200
SAVE_VERSION = 2
RETRY_HEALTH_FLOOR = 70

# Gold and armour slots are display values until the economy arrives in Stage 3.
START = {
    "health": 100, "health_max": 100,
    "stamina": 100, "stamina_max": 100,
    "magicka": 100, "magicka_max": 100,
    "gold": 25,
    "weight_max": 60,
    "equipment": {"weapon": "Worn Talwar", "weapon_id": "worn_talwar", "enchant": None,
                  "helmet": None, "cuirass": None, "boots": None},
}


class GameError(Exception):
    pass


def new_game(fields):
    clean = {}
    for key, limit in MAX_FIELD.items():
        val = str(fields.get(key, "")).strip()
        if not val:
            raise GameError(f"{key.capitalize()} is required.")
        clean[key] = val[:limit]
    if fields.get("ancestry") not in story.ANCESTRIES:
        raise GameError("Choose an ancestry.")
    if fields.get("origin") not in story.ORIGINS:
        raise GameError("Choose an origin.")
    clean["ancestry"] = fields["ancestry"]
    clean["origin"] = fields["origin"]
    try:
        chosen = appearance.validate(fields.get("looks"), clean["ancestry"])
    except ValueError as e:
        raise GameError(str(e))
    clean["looks"] = {k: v["id"] for k, v in chosen.items()}
    clean["details"] = str(fields.get("details", "")).strip()[:MAX_DETAILS]
    clean["appearance"] = appearance.describe(chosen, clean["details"])
    state = {
        "version": SAVE_VERSION,
        "created": time.time(),
        "character": clean,
        "stats": copy.deepcopy(START),
        "inventory": dict(CC.STARTER_ITEMS),
        "flags": {"returning": story.ORIGINS[clean["origin"]]["returning"]},
        "scene": "arrival",
        "narration": {},      # scene_id -> {text, model, ms, tokens}
        "journal": [],        # story memory passed back to Qwen
        "scene_effects": [],  # recovery messages shown on entering a scene
        "combat": None,
        "checkpoint": None,   # snapshot taken just before each fight
        "enchants_owned": [],
        "contracts_done": [],
        "notice": None,
    }
    shop.ensure(state)
    save(state)
    return state


def _migrate(state):
    """Bring Stage 1 saves forward."""
    if state.get("version", 1) < 2:
        eq = state["stats"].setdefault("equipment", {})
        eq.setdefault("weapon_id", "worn_talwar")
        eq.setdefault("enchant", None)
        state["stats"].pop("weight", None)
        state.setdefault("inventory", dict(CC.STARTER_ITEMS))
        state.setdefault("scene_effects", [])
        state.setdefault("combat", None)
        state.setdefault("checkpoint", None)
        if state["scene"] not in story.SCENES:  # old "encounter_ready" placeholder
            state["scene"] = "sun_market"
        state["version"] = SAVE_VERSION
    return state


def load():
    raw = storage.load_raw()
    if raw is None:
        return None
    try:
        state = _migrate(raw)
        shop.ensure(state)
        return state
    except (KeyError, TypeError):
        return None


def save(state):
    storage.save_raw(state)


def delete():
    storage.delete_raw()


# ---------- narration bookkeeping ----------

def needs_narration(state):
    if state.get("combat"):
        return state["combat"]["pending"] is not None
    return story.SCENES[state["scene"]]["brief"] is not None and state["scene"] not in state["narration"]


def record_narration(state, result):
    scene_id = state["scene"]
    state["narration"][scene_id] = result
    state["journal"].append({"scene": scene_id, "title": story.SCENES[scene_id]["title"], "text": result["text"]})
    save(state)


# ---------- scene actions ----------

def _find_action(state, action_id):
    return next((a for a in story.SCENES[state["scene"]]["actions"] if a["id"] == action_id), None)


def _enter_scene(state, scene_id):
    state["scene"] = scene_id
    state["scene_effects"] = []
    fx = story.SCENES[scene_id].get("on_enter") or {}
    s = state["stats"]
    if fx.get("heal"):
        before = s["health"]
        s["health"] = min(s["health_max"], s["health"] + fx["heal"])
        if s["health"] > before:
            state["scene_effects"].append(f"Recovered {s['health'] - before} Health.")
    for stat in fx.get("restore", []):
        if s[stat] < s[f"{stat}_max"]:
            s[stat] = s[f"{stat}_max"]
            state["scene_effects"].append(f"{stat.capitalize()} fully restored.")
    for item, n in (fx.get("items") or {}).items():
        state["inventory"][item] = state["inventory"].get(item, 0) + n
        state["scene_effects"].append(f"Received {n} × {CC.ITEMS[item]['label']}.")


def apply_action(state, action_id):
    cs = state.get("combat")
    if action_id == "retry":
        if not cs or cs["outcome"] != "defeat":
            raise GameError("You can only return to the checkpoint after a defeat.")
        return retry(state)
    if needs_narration(state):
        raise GameError("The Fates are still weaving this moment.")
    if cs:
        if action_id == "continue" and cs["outcome"] == "victory":
            state["journal"].append({"scene": cs["id"], "title": combat.C.ENCOUNTERS[cs["id"]]["title"],
                                     "text": cs["narration"]["text"]})
            state["combat"] = None
            state["checkpoint"] = None
            if cs.get("contract"):
                state["contracts_done"].append(cs["contract"])
                state["scene_effects"] = [f"Contract complete: {CC.CONTRACTS[cs['contract']]['title']}."]
            else:
                _enter_scene(state, _find_action(state, cs["action"])["win"])
            state["scene_effects"] += shop.grant_rewards(state, cs["id"])
            save(state)
            return state
        raise GameError("Finish the fight first.")
    state["notice"] = None
    a = _find_action(state, action_id)
    if not a:
        raise GameError(f"Action '{action_id}' is not available here.")
    if "combat" in a:
        snap = copy.deepcopy(state)
        snap["checkpoint"] = None
        state["checkpoint"] = snap
        combat.start(state, a["combat"])
        state["combat"]["action"] = action_id
    else:
        _enter_scene(state, a["to"])
    save(state)
    return state


def shop_op(state, op, item_id):
    if state.get("combat"):
        raise GameError("You can't trade or change gear in the middle of a fight.")
    if needs_narration(state):
        raise GameError("The Fates are still weaving this moment.")
    try:
        if op == "contract":
            if item_id not in CC.CONTRACTS or shop.contract_status(state, item_id) != "open":
                raise GameError("That contract isn't available.")
            snap = copy.deepcopy(state)
            snap["checkpoint"] = None
            state["checkpoint"] = snap
            combat.start(state, item_id)
            state["combat"]["action"] = None
            state["combat"]["contract"] = item_id
            state["notice"] = None
        else:
            fn = {"buy": shop.buy, "sell": shop.sell, "equip": shop.equip,
                  "unequip": shop.unequip, "drink": shop.drink}.get(op)
            if not fn:
                raise GameError("Unknown shop action.")
            state["notice"] = fn(state, item_id)
    except shop.ShopError as e:
        raise GameError(str(e))
    save(state)
    return state


def retry(state):
    snap = state.get("checkpoint")
    if not snap:
        raise GameError("No checkpoint to return to.")
    restored = copy.deepcopy(snap)
    restored["checkpoint"] = None
    restored["scene_effects"] = ["Returned to the checkpoint before the fight."]
    # A second chance must be winnable: top Health up to a floor, refill Stamina and Magicka.
    rs = restored["stats"]
    if rs["health"] < RETRY_HEALTH_FLOOR:
        restored["scene_effects"].append(f"The Fates mend you to {RETRY_HEALTH_FLOOR} Health.")
        rs["health"] = RETRY_HEALTH_FLOOR
    rs["stamina"], rs["magicka"] = rs["stamina_max"], rs["magicka_max"]
    save(restored)
    return restored


def combat_turn(state, action_id, target_id):
    if not state.get("combat"):
        raise GameError("You are not in combat.")
    try:
        combat.resolve(state, action_id, target_id)
    except combat.CombatError as e:
        raise GameError(str(e))
    save(state)
    return state


# ---------- view ----------



def view(state):
    """What the browser is allowed to see and do."""
    if state is None:
        return {"has_save": False, "options": options()}
    scene = story.SCENES[state["scene"]]
    c = state["character"]
    cs = state.get("combat")
    pending = needs_narration(state)
    if cs:
        actions = []
    else:
        actions = [] if pending else [{"id": a["id"], "label": a["label"], "combat": "combat" in a}
                                      for a in scene["actions"]]
    return {
        "has_save": True,
        "character": {**c,
                      "ancestry_label": story.ANCESTRIES[c["ancestry"]]["label"],
                      "origin_label": story.ORIGINS[c["origin"]]["label"]},
        "stats": {**state["stats"], "weight": shop.weight(state)},
        "inventory": [{"id": i, "label": shop.label(i), "count": n}
                      for i, n in state["inventory"].items() if n > 0 and shop.item_def(i)],
        "flags": state["flags"],
        "scene": {"id": state["scene"], "title": scene["title"], "objective": scene["objective"],
                  "art": scene["art"], "music": scene["music"], "final": not scene["actions"],
                  "ending": bool(scene.get("ending"))},
        "scene_effects": state.get("scene_effects", []),
        "narration": state["narration"].get(state["scene"]),
        "narration_pending": pending,
        "actions": actions,
        "combat": combat.view(state) if cs else None,
        "shop": None if cs or pending else shop.view(state),
        "notice": state.get("notice"),
        "has_checkpoint": bool(state.get("checkpoint")),
        "journal": [{"title": e["title"]} for e in state["journal"]],
        "options": options(),
    }


def options():
    return {
        "ancestries": [{"id": k, "label": v["label"], "flavor": v["flavor"]} for k, v in story.ANCESTRIES.items()],
        "origins": [{"id": k, "label": v["label"], "summary": v["summary"],
                     "returning": v["returning"]} for k, v in story.ORIGINS.items()],
        "appearance": appearance.STEPS,
    }
