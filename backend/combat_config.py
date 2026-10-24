"""Combat tuning. Every number the combat engine uses lives here.

Ranges are inclusive (min, max). Chances are 0..1.
Run `python3 backend/sim.py` after changing values to see win rates and health left.
"""

# ---------- Player ----------
STAMINA_REGEN = 10          # restored at the end of every turn, capped at max
RECOVER_BONUS = 15          # extra Stamina from "Catch breath" (on top of regen)

# id -> label, Stamina cost, whether it needs a target
PLAYER_ACTIONS = {
    "light":   {"label": "Light attack", "stamina": 15, "target": True},
    "heavy":   {"label": "Heavy attack", "stamina": 25, "target": True},
    "dodge":   {"label": "Dodge",        "stamina": 10, "target": False},
    "parry":   {"label": "Parry",        "stamina": 10, "target": False},
    "guard":   {"label": "Guard",        "stamina": 0,  "target": False},
    "recover": {"label": "Catch breath", "stamina": 0,  "target": False},
    "shoot":   {"label": "Shoot arrow",  "stamina": 10, "target": True, "only_mech": "dragon"},
}
ARROW = {"hit_chance": 0.85, "dmg": (5, 8)}   # arrows only matter against an airborne Agnivara

# Weapons. Swarna Heer's minimum light hit (16) one-shots archers (8 HP) and raiders (14 HP).
WEAPONS = {
    "worn_talwar":   {"label": "Worn Talwar",        "light": (8, 12),  "heavy": (14, 19), "weight": 4, "price": 0},
    "leather_khanda": {"label": "Hide-grip Khanda",  "light": (10, 13), "heavy": (16, 21), "weight": 4, "price": 40},
    "iron_talwar":   {"label": "Iron Talwar",        "light": (12, 16), "heavy": (19, 25), "weight": 5, "price": 90},
    "swarna_talwar": {"label": "Swarna Heer Talwar", "light": (16, 22), "heavy": (26, 34), "weight": 4, "price": 220},
}

CRIT_CHANCE = {"light": 0.10, "heavy": 0.15}
CRIT_MULT = 1.5
HEAVY_BLOCK_FACTOR = 0.5    # heavy attacks halve an enemy's chance to block

# ---------- Defence ----------
# Enemy attack types: quick, heavy, ranged, sweep.
# For each: (full success chance, partial chance). The rest is a failure (full damage).
DODGE = {"quick": (0.45, 0.30), "heavy": (0.65, 0.20), "ranged": (0.60, 0.25), "sweep": (0.35, 0.35)}
PARRY = {"quick": (0.60, 0.25), "heavy": (0.30, 0.35), "ranged": (0.10, 0.25), "sweep": (0.20, 0.30)}
DODGE_PARTIAL_TAKEN = 0.50  # share of damage taken on a partial dodge
PARRY_PARTIAL_TAKEN = 0.40
GUARD = {"solid_chance": 0.60, "solid_taken": 0.40, "shaky_taken": 0.75}
RIPOSTE = (6, 9)            # free counter-hit after a full parry of a melee attack

# Enemy attack quality roll: (name, chance, damage multiplier)
ATTACK_QUALITY = [("glancing", 0.25, 0.75), ("solid", 0.55, 1.0), ("brutal", 0.20, 1.25)]

# ---------- Armour (placeholder until Stage 3) ----------
# Each piece reduces incoming damage by a fraction; pieces stack. Full sets: leather 12%, iron 21%, Swarna Heer 34%.
ARMOUR_PIECES = {
    "leather_helmet":  {"label": "Leather Helmet",      "slot": "helmet",  "reduce": 0.03, "weight": 2, "price": 20},
    "leather_cuirass": {"label": "Leather Cuirass",     "slot": "cuirass", "reduce": 0.06, "weight": 4, "price": 35},
    "leather_boots":   {"label": "Leather Boots",       "slot": "boots",   "reduce": 0.03, "weight": 2, "price": 20},
    "iron_helmet":     {"label": "Iron Helmet",         "slot": "helmet",  "reduce": 0.05, "weight": 4, "price": 45},
    "iron_cuirass":    {"label": "Iron Cuirass",        "slot": "cuirass", "reduce": 0.11, "weight": 8, "price": 80},
    "iron_boots":      {"label": "Iron Boots",          "slot": "boots",   "reduce": 0.05, "weight": 4, "price": 45},
    "swarna_helmet":   {"label": "Swarna Heer Helmet",  "slot": "helmet",  "reduce": 0.09, "weight": 3, "price": 100},
    "swarna_cuirass":  {"label": "Swarna Heer Cuirass", "slot": "cuirass", "reduce": 0.16, "weight": 6, "price": 180},
    "swarna_boots":    {"label": "Swarna Heer Boots",   "slot": "boots",   "reduce": 0.09, "weight": 3, "price": 100},
}
ARMOUR = {k: v["reduce"] for k, v in ARMOUR_PIECES.items()}
ARMOUR_CAP = 0.45           # armour never removes more than this share of a hit

# ---------- Enchantments (engine supports them; none are owned yet) ----------
# Bought once at the Arcanium, then one can be active on your weapon at a time.
ENCHANTMENTS = {
    "sharpness": {"label": "Sharpness", "magicka": 10, "bonus": (3, 5), "price": 60,
                  "desc": "+3–5 weapon damage"},
    "suryataap": {"label": "Suryataap", "magicka": 15, "burn": (3, 5), "turns": 3, "price": 90,
                  "desc": "Sets the target burning: 3–5 damage for 3 turns"},
    "shield":    {"label": "Shield ward", "magicka": 10, "guard_bonus": 0.15, "price": 70,
                  "desc": "+15% chance of a solid Guard"},
}

# ---------- Items ----------
# Potions can be drunk in or out of combat. Loot is only for selling.
ITEMS = {
    "health_potion":  {"label": "Health potion",  "restore": {"health": 35},  "weight": 0.5, "price": 15},
    "stamina_potion": {"label": "Stamina potion", "restore": {"stamina": 40}, "weight": 0.5, "price": 10},
    "magicka_potion": {"label": "Magicka potion", "restore": {"magicka": 40}, "weight": 0.5, "price": 10},
}
LOOT = {
    "asura_fang":   {"label": "Asura fang",        "weight": 0.5, "value": 6},
    "soot_ember":   {"label": "Cold soot ember",   "weight": 1,   "value": 25},
    "collar_plate": {"label": "Brute collar plate", "weight": 3,  "value": 35},
    "oath_rosary":  {"label": "Vajraka's oath rosary", "weight": 1, "value": 80},
}
SELL_RATE = 0.5             # gear and potions sell for half their price; loot sells for its value

# Rewards for winning an encounter: gold range plus loot.
REWARDS = {
    "market_minions": {"gold": (25, 35), "loot": {"asura_fang": 2}},
    "soot":           {"gold": (45, 55), "loot": {"soot_ember": 1}},
    "brute":          {"gold": (60, 75), "loot": {"collar_plate": 1}},
    "outer_hall":     {"gold": (60, 80), "loot": {"asura_fang": 2}},
    "causeway":       {"gold": (80, 100), "loot": {"collar_plate": 1}},
    "vajraka":        {"gold": (150, 180), "loot": {"oath_rosary": 1}},
    "c_rooftops":     {"gold": (50, 60), "loot": {"asura_fang": 1}},
    "c_ghats":        {"gold": (60, 70), "items": {"health_potion": 2}},
    "c_stray_brute":  {"gold": (100, 120), "loot": {"collar_plate": 1}},
}

# Optional contracts: short side fights for gold. Never required by the story.
CONTRACTS = {
    "c_rooftops":    {"title": "Archers on the Rooftops", "giver": "Ketaki of the Arcanium",
                      "desc": "Three asura archers are sniping at the water carriers.", "unlock_after": "soot_rises"},
    "c_ghats":       {"title": "Raiders at the Ghats", "giver": "Hari the ferryman",
                      "desc": "Raiders are looting the ferries on the river steps.", "unlock_after": "soot_rises"},
    "c_stray_brute": {"title": "The Stray Brute", "giver": "Bhola the innkeeper",
                      "desc": "A second brute prowls the granary lanes. Dangerous, well paid.", "unlock_after": "tavern_after"},
}
STARTER_ITEMS = {"health_potion": 2, "stamina_potion": 1, "magicka_potion": 1}

# ---------- Enemies ----------
# attacks: id -> label, type, damage range, tell (what the player sees before it happens)
# idle:    non-attacking moves an enemy may choose instead
ENEMIES = {
    "asura_raider": {
        "name": "Asura Raider", "hp": 14, "block": 0.0, "block_reduce": (0.0, 0.0),
        "attacks": {
            "slash": {"label": "Notched slash", "type": "quick", "dmg": (5, 8),
                      "tell": "raises its notched blade for a quick cut"},
            "lunge": {"label": "Lunging stab", "type": "heavy", "dmg": (8, 12),
                      "tell": "drops low and draws its blade back to lunge"},
        },
        "idle": {"circle": {"label": "Circle", "tell": "circles you, looking for a gap"}},
    },
    "asura_archer": {
        "name": "Asura Archer", "hp": 8, "block": 0.0, "block_reduce": (0.0, 0.0),
        "attacks": {
            "arrow": {"label": "Arrow", "type": "ranged", "dmg": (4, 7),
                      "tell": "nocks an arrow and sights along it at you"},
        },
        "idle": {"reposition": {"label": "Reposition", "tell": "scrambles along the awnings to a new perch"}},
    },
    "binding_tree": {
        "name": "Binding Tree", "hp": 10, "block": 0.0, "passive": True,
        "attacks": {}, "idle": {},
    },
    "soot_bound": {
        "name": "The Soot-Bound", "hp": 24, "block": 0.0, "bound": True,
        "target_label": "Sword in its heart",
        "attacks": {
            "ash_lash":    {"label": "Ash lash", "type": "quick", "dmg": (6, 9),
                            "tell": "cracks a whip of ash back over its shoulder"},
            "cinder_slam": {"label": "Cinder slam", "type": "heavy", "dmg": (11, 15),
                            "tell": "rears up, embers gathering in both fists"},
            "soot_breath": {"label": "Soot breath", "type": "sweep", "dmg": (5, 8),
                            "tell": "draws in a long, rattling breath of soot"},
        },
        "idle": {"strain": {"label": "Strain", "tell": "strains against its bindings, the trees groaning"}},
    },
    "asura_shieldbearer": {
        "name": "Shield-bearer", "hp": 14, "block": 0.35, "block_reduce": (0.50, 0.80),
        "shields_allies": 0.5,  # while alive, other enemies (except weak-point hits) take half damage
        "attacks": {
            "shield_bash": {"label": "Shield bash", "type": "quick", "dmg": (6, 9),
                            "tell": "plants its feet and draws its tower shield back"},
            "spear_thrust": {"label": "Spear thrust", "type": "heavy", "dmg": (9, 13),
                             "tell": "levels its spear over the shield rim"},
        },
        "idle": {"brace": {"label": "Brace", "tell": "locks shields with its allies"}},
    },
    "shilapaksha": {
        "name": "Shilapaksha", "hp": 8, "block": 0.0,
        "attacks": {
            "talon_dive": {"label": "Talon dive", "type": "heavy", "dmg": (7, 11),
                           "tell": "folds its stone wings and drops toward you"},
            "wing_slash": {"label": "Wing slash", "type": "quick", "dmg": (5, 8),
                           "tell": "sweeps a razor-edged stone wing back"},
        },
        "idle": {},
    },
    "vajraka": {
        "name": "Vajraka, Oath-Keeper of the Flame", "hp": 45, "block": 0.0, "warded": True,
        "target_label": "Vajraka",
        "attacks": {
            "flame_lash": {"label": "Flame lash", "type": "quick", "dmg": (8, 12),
                           "tell": "flicks his rosary and a lash of flame uncoils"},
            "oath_fire": {"label": "Oath-fire", "type": "sweep", "dmg": (10, 15),
                          "tell": "raises both hands as the floor glyphs ignite"},
        },
        "idle": {"chant": {"label": "Chant", "tell": "chants, his shield brightening"}},
    },
    "sun_crystal": {
        "name": "Sun Crystal", "hp": 10, "block": 0.0, "passive": True, "heals": 1,
        "attacks": {}, "idle": {},
    },
    "agnivara": {
        "name": "Agnivara", "hp": 80, "block": 0.0, "dragon": True,
        "attacks": {
            "fire_rain":  {"label": "Fire rain", "type": "ranged", "dmg": (10, 15), "phase": "air",
                           "tell": "climbs high, fire gathering in its throat"},
            "dive":       {"label": "Dive", "type": "heavy", "dmg": (16, 22), "phase": "air",
                           "tell": "folds its wings and plunges toward you"},
            "claw":       {"label": "Claw", "type": "quick", "dmg": (16, 22), "phase": "ground",
                           "tell": "rears back one taloned forefoot"},
            "tail_sweep": {"label": "Tail sweep", "type": "sweep", "dmg": (19, 25), "phase": "ground",
                           "tell": "coils its tail low across the floor"},
            "inferno":    {"label": "Inferno", "type": "heavy", "dmg": (25, 33), "phase": "ground",
                           "tell": "draws a breath until its throat glows white-hot"},
        },
        "idle": {"circle": {"label": "Circle", "phase": "air", "tell": "circles above, drinking the crystals' light"}},
    },
    "tavern_brute": {
        "name": "Tavern Brute", "hp": 40, "block": 0.0,
        "hide": 0.25,  # body hits deal this share of damage
        "weak_point": {"id": "nape", "label": "Nape of the neck", "mult": 2.5},
        # a full dodge of these types, or a full parry of these, leaves the nape exposed for one turn
        "opens_on": {"dodge": ["quick", "heavy", "sweep"], "parry": ["quick", "heavy", "sweep"]},
        "attacks": {
            "backhand":       {"label": "Backhand", "type": "quick", "dmg": (9, 13),
                               "tell": "shifts its weight, one arm swinging wide"},
            "overhead_smash": {"label": "Overhead smash", "type": "heavy", "dmg": (15, 21),
                               "tell": "raises both fists high above its head"},
            "charge":         {"label": "Charge", "type": "sweep", "dmg": (12, 17),
                               "tell": "lowers its head and scrapes the floor with one foot"},
        },
        "idle": {"roar": {"label": "Roar", "tell": "beats its chest and roars"}},
    },
}

# ---------- Boss mechanics ----------
WARD = {"waves": [1, 2, 2], "window_turns": 2}   # Shilapaksha per wave; player turns the shield stays broken
DRAGON = {"arrows_needed": (2, 3), "ground_turns": 3, "crash_shatters": 3}

# ---------- Encounters ----------
# enemies: (instance id, enemy kind, display name or None)
ENCOUNTERS = {
    "market_minions": {
        "title": "Sun Market Raiders",
        "goal": "Defeat the asura raiders and the archers on the awnings.",
        "max_attackers": 2,
        "enemies": [("raider_1", "asura_raider", "Asura Raider"),
                    ("raider_2", "asura_raider", "Scarred Raider"),
                    ("archer_1", "asura_archer", "Awning Archer"),
                    ("archer_2", "asura_archer", "Stall-roof Archer")],
    },
    "soot": {
        "title": "The Soot-Bound",
        "goal": "Destroy the three binding trees, then strike the sword in its heart.",
        "max_attackers": 1,
        "enemies": [("tree_west", "binding_tree", "Western Tree"),
                    ("tree_north", "binding_tree", "Northern Tree"),
                    ("tree_east", "binding_tree", "Eastern Tree"),
                    ("soot", "soot_bound", None)],
    },
    "outer_hall": {
        "title": "The Outer Hall", "goal": "Clear the hall: raiders, archers and a brute.", "max_attackers": 2,
        "enemies": [("raider_1", "asura_raider", "Hall Raider"), ("raider_2", "asura_raider", "Torch Raider"),
                    ("archer_1", "asura_archer", "Gallery Archer"), ("archer_2", "asura_archer", "Pillar Archer"),
                    ("brute", "tavern_brute", "Hall Brute")],
    },
    "causeway": {
        "title": "The Broken Causeway",
        "goal": "Shield-bearers halve damage to their allies: break them first. Then the archers and two brutes.",
        "max_attackers": 2,
        "enemies": [("shield_1", "asura_shieldbearer", "Left Shield-bearer"),
                    ("shield_2", "asura_shieldbearer", "Right Shield-bearer"),
                    ("archer_1", "asura_archer", "Causeway Archer"),
                    ("brute_1", "tavern_brute", "Chained Brute"), ("brute_2", "tavern_brute", "Scarred Brute")],
    },
    "vajraka": {
        "title": "Vajraka's Ward", "mech": "ward", "max_attackers": 1,
        "goal": "Destroy each Shilapaksha wave to shatter Vajraka's shield, then strike him before it reforms. Three windows.",
        "enemies": [("vajraka", "vajraka", None)],
    },
    "agnivara": {
        "title": "Agnivara", "mech": "dragon", "max_attackers": 1,
        "goal": "Shatter the six crystals that heal it. Shoot it down from the sky, then strike while it is grounded.",
        "enemies": [(f"crystal_{i}", "sun_crystal", f"Sun Crystal {i}") for i in range(1, 7)] + [("agnivara", "agnivara", None)],
    },
    "c_rooftops": {
        "title": "Archers on the Rooftops", "goal": "Shoot down the three archers.", "max_attackers": 2,
        "enemies": [("archer_1", "asura_archer", "Chimney Archer"), ("archer_2", "asura_archer", "Ridge Archer"),
                    ("archer_3", "asura_archer", "Bell-tower Archer")],
    },
    "c_ghats": {
        "title": "Raiders at the Ghats", "goal": "Drive the raiders off the river steps.", "max_attackers": 2,
        "enemies": [("raider_1", "asura_raider", "Ghat Raider"), ("raider_2", "asura_raider", "Boat-hook Raider"),
                    ("archer_1", "asura_archer", "Ferry-roof Archer")],
    },
    "c_stray_brute": {
        "title": "The Stray Brute", "goal": "Cleanly dodge or parry a blow to expose its nape, then strike it.",
        "max_attackers": 1, "enemies": [("brute", "tavern_brute", "Granary Brute")],
    },
    "brute": {
        "title": "The Tavern Brute",
        "goal": "Cleanly dodge or parry a blow to expose its nape, then strike it.",
        "max_attackers": 1,
        "enemies": [("brute", "tavern_brute", None)],
    },
}
