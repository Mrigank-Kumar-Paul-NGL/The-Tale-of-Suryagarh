"""Gold, inventory, weight, equipment, shops, rewards and contracts. Python is authoritative for all of it."""
import random

import combat_config as C
import story

SLOTS = ("helmet", "cuirass", "boots")


class ShopError(Exception):
    pass


# ---------- lookups ----------

def item_def(iid):
    """Any carryable thing: potion, loot, armour piece, or weapon."""
    if iid in C.ITEMS:
        return {**C.ITEMS[iid], "kind": "potion"}
    if iid in C.LOOT:
        return {**C.LOOT[iid], "kind": "loot", "price": C.LOOT[iid]["value"]}
    if iid in C.ARMOUR_PIECES:
        return {**C.ARMOUR_PIECES[iid], "kind": "armour"}
    if iid in C.WEAPONS:
        return {**C.WEAPONS[iid], "kind": "weapon"}
    return None


def label(iid):
    d = item_def(iid) or C.ENCHANTMENTS.get(iid)
    return d["label"] if d else iid


def ensure(state):
    """Fill fields added in Stage 3 (keeps older saves working)."""
    eq = state["stats"]["equipment"]
    eq.setdefault("weapon_id", "worn_talwar")
    eq.setdefault("enchant", None)
    for slot in SLOTS:
        if eq.get(slot) and eq[slot] not in C.ARMOUR_PIECES:
            eq[slot] = None
    eq["weapon"] = C.WEAPONS[eq["weapon_id"]]["label"]
    state.setdefault("enchants_owned", [])
    state.setdefault("contracts_done", [])
    state.setdefault("notice", None)


def weight(state):
    eq = state["stats"]["equipment"]
    w = C.WEAPONS[eq["weapon_id"]]["weight"]
    w += sum(C.ARMOUR_PIECES[eq[s]]["weight"] for s in SLOTS if eq.get(s))
    w += sum(item_def(i)["weight"] * n for i, n in state["inventory"].items() if n > 0 and item_def(i))
    return round(w, 1)


def _fits(state, extra):
    return weight(state) + extra <= state["stats"]["weight_max"] + 1e-9


def _owned(state, iid):
    eq = state["stats"]["equipment"]
    return state["inventory"].get(iid, 0) > 0 or eq["weapon_id"] == iid or iid in [eq.get(s) for s in SLOTS]


# ---------- transactions ----------

def buy(state, iid):
    s = state["stats"]
    if iid in C.ENCHANTMENTS:
        en = C.ENCHANTMENTS[iid]
        if iid in state["enchants_owned"]:
            raise ShopError(f"You already know {en['label']}.")
        if s["gold"] < en["price"]:
            raise ShopError(f"{en['label']} costs {en['price']} gold; you have {s['gold']}.")
        s["gold"] -= en["price"]
        state["enchants_owned"].append(iid)
        if not s["equipment"].get("enchant"):
            s["equipment"]["enchant"] = iid
        return f"Learned {en['label']} (−{en['price']} gold)."
    d = item_def(iid)
    if not d or d["kind"] == "loot" or not d.get("price"):
        raise ShopError("That isn't for sale.")
    if d["kind"] in ("armour", "weapon") and _owned(state, iid):
        raise ShopError(f"You already own the {d['label']}.")
    if s["gold"] < d["price"]:
        raise ShopError(f"{d['label']} costs {d['price']} gold; you have {s['gold']}.")
    if not _fits(state, d["weight"]):
        raise ShopError(f"Too heavy: the {d['label']} weighs {d['weight']} and you carry "
                        f"{weight(state)}/{s['weight_max']}. Sell or drop something first.")
    s["gold"] -= d["price"]
    state["inventory"][iid] = state["inventory"].get(iid, 0) + 1
    return f"Bought {d['label']} (−{d['price']} gold)."


def sell(state, iid):
    d = item_def(iid)
    if not d or state["inventory"].get(iid, 0) <= 0:
        raise ShopError("You aren't carrying that (unequip it first if you're wearing it).")
    price = d["price"] if d["kind"] == "loot" else max(1, int(d["price"] * C.SELL_RATE))
    state["inventory"][iid] -= 1
    state["stats"]["gold"] += price
    return f"Sold {d['label']} (+{price} gold)."


def equip(state, iid):
    eq = state["stats"]["equipment"]
    if iid in C.ENCHANTMENTS:
        if iid not in state["enchants_owned"]:
            raise ShopError("You haven't learned that enchantment.")
        eq["enchant"] = iid
        return f"{C.ENCHANTMENTS[iid]['label']} now flows through your weapon."
    d = item_def(iid)
    if not d or d["kind"] not in ("armour", "weapon") or state["inventory"].get(iid, 0) <= 0:
        raise ShopError("You aren't carrying that.")
    state["inventory"][iid] -= 1
    if d["kind"] == "weapon":
        old = eq["weapon_id"]
        eq["weapon_id"] = iid
    else:
        old = eq.get(d["slot"])
        eq[d["slot"]] = iid
    if old:
        state["inventory"][old] = state["inventory"].get(old, 0) + 1
    eq["weapon"] = C.WEAPONS[eq["weapon_id"]]["label"]
    return f"Equipped {d['label']}."


def unequip(state, slot):
    eq = state["stats"]["equipment"]
    if slot == "enchant":
        eq["enchant"] = None
        return "Enchantment removed."
    if slot not in SLOTS or not eq.get(slot):
        raise ShopError("Nothing to remove there.")
    iid = eq[slot]
    eq[slot] = None
    state["inventory"][iid] = state["inventory"].get(iid, 0) + 1
    return f"Removed {C.ARMOUR_PIECES[iid]['label']}."


def drink(state, iid):
    if iid not in C.ITEMS or state["inventory"].get(iid, 0) <= 0:
        raise ShopError("You don't have that potion.")
    s = state["stats"]
    parts = []
    for stat, amt in C.ITEMS[iid]["restore"].items():
        before = s[stat]
        s[stat] = min(s[f"{stat}_max"], s[stat] + amt)
        parts.append(f"+{s[stat] - before} {stat.capitalize()}")
    state["inventory"][iid] -= 1
    return f"Drank a {C.ITEMS[iid]['label']}: {', '.join(parts)}."


def grant_rewards(state, enc_id):
    """Gold and loot for a won encounter. Loot that doesn't fit is left behind, with a message."""
    r = C.REWARDS.get(enc_id)
    if not r:
        return []
    msgs = []
    gold = random.randint(*r["gold"])
    state["stats"]["gold"] += gold
    msgs.append(f"Looted {gold} gold.")
    for group in ("loot", "items"):
        for iid, n in (r.get(group) or {}).items():
            d = item_def(iid)
            taken = 0
            for _ in range(n):
                if _fits(state, d["weight"]):
                    state["inventory"][iid] = state["inventory"].get(iid, 0) + 1
                    taken += 1
            if taken:
                msgs.append(f"Took {taken} × {d['label']}.")
            if taken < n:
                msgs.append(f"Too heavy to carry {n - taken} × {d['label']}; left behind.")
    return msgs


# ---------- contracts ----------

def contract_status(state, cid):
    c = C.CONTRACTS[cid]
    order = list(story.SCENES)
    if cid in state["contracts_done"]:
        return "done"
    if order.index(state["scene"]) < order.index(c["unlock_after"]):
        return "locked"
    return "open"


# ---------- view ----------

def _row(state, iid, d, price):
    s = state["stats"]
    reason = ""
    if d.get("kind") in ("armour", "weapon") and _owned(state, iid):
        reason = "Owned"
    elif iid in C.ENCHANTMENTS and iid in state["enchants_owned"]:
        reason = "Known"
    elif s["gold"] < price:
        reason = f"Need {price - s['gold']} more gold"
    elif d.get("weight") and not _fits(state, d["weight"]):
        reason = "Too heavy to carry"
    return {"id": iid, "label": d["label"], "price": price, "weight": d.get("weight", 0),
            "can_buy": not reason, "reason": reason}


def view(state):
    eq = state["stats"]["equipment"]
    arcanium = []
    for iid, d in C.ITEMS.items():
        restore = ", ".join(f"+{v} {k.capitalize()}" for k, v in d["restore"].items())
        arcanium.append({**_row(state, iid, {**d, "kind": "potion"}, d["price"]), "desc": restore,
                         "group": "Potions"})
    for eid, en in C.ENCHANTMENTS.items():
        arcanium.append({**_row(state, eid, {"label": en["label"]}, en["price"]),
                         "desc": f"{en['desc']} · costs {en['magicka']} Magicka per use", "group": "Enchantments"})
    armoury = []
    for iid, w in C.WEAPONS.items():
        if w["price"]:
            armoury.append({**_row(state, iid, {**w, "kind": "weapon"}, w["price"]),
                            "desc": f"Light {w['light'][0]}–{w['light'][1]} · Heavy {w['heavy'][0]}–{w['heavy'][1]}",
                            "group": "Weapons"})
    for iid, a in C.ARMOUR_PIECES.items():
        armoury.append({**_row(state, iid, {**a, "kind": "armour"}, a["price"]),
                        "desc": f"{a['slot'].capitalize()} · −{int(a['reduce'] * 100)}% damage taken",
                        "group": {"leather": "Leather", "iron": "Iron", "swarna": "Swarna Heer"}[iid.split("_")[0]]})
    satchel = []
    for iid, n in state["inventory"].items():
        d = item_def(iid)
        if n <= 0 or not d:
            continue
        sell_price = d["price"] if d["kind"] == "loot" else max(1, int(d["price"] * C.SELL_RATE))
        satchel.append({"id": iid, "label": d["label"], "count": n, "kind": d["kind"], "weight": d["weight"],
                        "sell": sell_price, "can_equip": d["kind"] in ("armour", "weapon"),
                        "can_drink": d["kind"] == "potion"})
    equipped = [{"slot": "weapon", "id": eq["weapon_id"], "label": C.WEAPONS[eq["weapon_id"]]["label"]}]
    equipped += [{"slot": s, "id": eq.get(s), "label": C.ARMOUR_PIECES[eq[s]]["label"] if eq.get(s) else None}
                 for s in SLOTS]
    contracts = [{"id": cid, **{k: c[k] for k in ("title", "giver", "desc")},
                  "status": contract_status(state, cid),
                  "reward": f"{C.REWARDS[cid]['gold'][0]}–{C.REWARDS[cid]['gold'][1]} gold"}
                 for cid, c in C.CONTRACTS.items()]
    armour = min(sum(C.ARMOUR.get(eq.get(s) or "", 0) for s in SLOTS), C.ARMOUR_CAP)
    return {
        "gold": state["stats"]["gold"], "weight": weight(state), "weight_max": state["stats"]["weight_max"],
        "armour_pct": int(armour * 100),
        "arcanium": arcanium, "armoury": armoury, "satchel": satchel, "equipped": equipped,
        "enchants": [{"id": e, "label": C.ENCHANTMENTS[e]["label"], "active": eq.get("enchant") == e,
                      "magicka": C.ENCHANTMENTS[e]["magicka"]} for e in state["enchants_owned"]],
        "contracts": contracts,
    }
