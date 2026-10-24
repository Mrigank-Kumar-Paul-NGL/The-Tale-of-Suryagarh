"""Fixed story facts, character options, and Stage 1 scenes.

Qwen narrates *around* these facts. It never decides them.
"""

WORLD_FACTS = [
    "The city is Suryagarh. The sun has not risen for seven days.",
    "A great brass wheel hangs in the sky. It turns at every dawn but never opens, and no light comes.",
    "Shadows creep across the rooftops. People are forgetting names and memories.",
    "Asuras (demonic attackers) are raiding the city and pressing toward the palace.",
    "The ruler publicly blames the dragon Agnivara for stealing the sun.",
    "Mira, a palace apprentice, is investigating the attacks. (The player has not met her yet.)",
]

ANCESTRIES = {
    "human": {"label": "Human",
              "flavor": "Human, of the river plains folk."},
    "vanara": {"label": "Vanara",
               "flavor": "Vanara: monkey-folk with a prehensile tail, quick hands and keen balance."},
    "naga": {"label": "Naga-blooded",
             "flavor": "Naga-blooded: faint serpent scales along the neck and wrists, eyes that catch lamplight."},
}

ORIGINS = {
    "palace_ward": {
        "label": "Palace Ward",
        "returning": True,
        "summary": "Raised as a ward inside the palace; left years ago and now returns.",
        "arrival_place": "the Lotus Gate, the palace-side entrance to the city",
        "recognition": "Old gatekeeper Bhima, who once smuggled the player sweets from the palace kitchens, "
                       "recognises them, but struggles to recall their name.",
        "callbacks": ["Remembers the dawn ceremony when the brass wheel opened from the palace balconies.",
                      "Knows the palace corridors and its servants by sight."],
    },
    "performer": {
        "label": "Traveling Performer",
        "returning": False,
        "summary": "A wandering performer arriving in Suryagarh for the first time.",
        "arrival_place": "the Caravan Road gate, with a battered props cart",
        "recognition": "Lalita, a market crier who was promised the troupe's show, greets the player, "
                       "relieved and frightened, and says the Sun Market was to be their stage.",
        "callbacks": ["Reads crowds and panic like an audience.",
                      "Came for the Festival of First Light, which never began."],
    },
    "healer": {
        "label": "Village Healer",
        "returning": False,
        "summary": "A healer from the hill village of Kesarpur, arriving in the city for the first time.",
        "arrival_place": "the river ghats, stepping off a ferry",
        "recognition": "Old ferryman Hari begs the player to look at his wife, who no longer remembers his name.",
        "callbacks": ["Notices the forgetting as a symptom, like a sickness.",
                      "Carries herbs and a satchel of village remedies."],
    },
    "temple_guard": {
        "label": "Former Temple Guard",
        "returning": True,
        "summary": "Once a guard of the Sun Temple; left the order years ago and now returns.",
        "arrival_place": "the Temple Steps above the old city",
        "recognition": "Devraj, a former comrade still in the temple guard, recognises the player, "
                       "then falters, unable to remember the oath they once swore together.",
        "callbacks": ["Knows the temple guard oaths and drills.",
                      "Remembers the temple fire that was never supposed to go out, now guttering."],
    },
}

# Stage 1 scenes. `actions` are the only legal moves; Python checks every request against them.
# Scenes. `actions` are the only legal moves; Python checks every request against them.
# An action either moves to another scene ("to") or starts a fight ("combat", then "win" scene on victory).
# "on_enter" effects are explicit recovery events applied by Python when the scene is entered.
SCENES = {
    "arrival": {
        "title": "Arrival in Suryagarh",
        "objective": "Learn what has happened to Suryagarh.",
        "art": "arrival", "music": "city_dark",
        "actions": [{"id": "go_market", "label": "Head for the Sun Market", "to": "sun_market"}],
        "brief": ("Narrate the player arriving at {arrival_place}. {returning_line} Show the dark sky, "
                  "the closed brass wheel, and the forgetting. Include a short spoken exchange: {recognition} "
                  "Weave in one detail from the player's callbacks, and have someone notice one detail of the "
                  "player's appearance. End with screams and smoke rising "
                  "from the direction of the Sun Market."),
    },
    "sun_market": {
        "title": "The Sun Market",
        "objective": "Defend the Sun Market from the asura raid.",
        "art": "sun_market", "music": "market_tension",
        "actions": [{"id": "begin_encounter", "label": "Begin encounter",
                     "combat": "market_minions", "win": "soot_rises"}],
        "brief": ("Narrate the player reaching the Sun Market during an asura attack. Stalls burn under a "
                  "black sky. Two asura raiders with crude notched blades and two asura archers on the "
                  "awnings are attacking merchants. Further back, something soot-like and huge is bound to "
                  "three dead trees, and a sword is lodged in its chest; describe it only briefly as a "
                  "looming threat. Include one frightened line from a merchant. End at the exact moment the "
                  "nearest asuras notice the player and turn to attack. Do NOT narrate any fighting."),
    },
    "soot_rises": {
        "title": "The Creature in the Trees",
        "objective": "Free the market from the creature bound to the three trees.",
        "art": "sun_market", "music": "miniboss",
        "actions": [{"id": "face_soot", "label": "Face the Soot-Bound", "combat": "soot", "win": "market_aftermath"}],
        "brief": ("The last raiders have fallen (do not describe that fight again). Now the soot-like creature "
                  "behind them wakes. It is bound by black roots to three dead trees, west, north and east; "
                  "the roots pulse as if feeding it. A sword is lodged deep in its heart, and around the blade "
                  "its body looks thin and raw, but while the trees stand, the soot closes over it like armour. "
                  "A surviving merchant shouts that the trees are keeping it alive. End as the creature "
                  "turns its burning gaze on the player. Do NOT narrate any fighting."),
    },
    "market_aftermath": {
        "title": "Ash in the Market",
        "objective": "Catch your breath. The Arcanium is nearby.",
        "art": "sun_market", "music": "city_dark",
        "on_enter": {"heal": 20, "restore": ["stamina", "magicka"]},
        "actions": [{"id": "visit_arcanium", "label": "Visit the Arcanium", "to": "arcanium"}],
        "brief": ("The Soot-Bound has collapsed into drifting ash and the sword in its heart has crumbled "
                  "(the player does not take it). Grateful merchants share water and bind the player's "
                  "cuts. Survivors whisper that the attacks are pushing toward the palace. A merchant points "
                  "the player to the Arcanium, an apothecary and enchanter's shop off the market square, "
                  "still lit by oil lamps. End as the player turns toward its door."),
    },
    "arcanium": {
        "title": "The Arcanium",
        "objective": "Restock before moving on. (The full shop opens in a later stage.)",
        "art": "arcanium", "music": "arcanium",
        "on_enter": {"heal": 15, "items": {"health_potion": 1, "stamina_potion": 1}},
        "actions": [{"id": "go_tavern", "label": "Seek shelter at the Copper Lamp tavern", "to": "tavern"}],
        "brief": ("Inside the Arcanium: shelves of glowing phials, dried herbs, and enchanting stones. The "
                  "keeper, an old enchantress named Ketaki who keeps forgetting where she put things, "
                  "recognises the player from the market fight. She presses one health draught and one "
                  "stamina draught into the player's hands for free, and says her full stock will be for sale "
                  "once the streets are safer. She warns that survivors are sheltering at the Copper Lamp "
                  "tavern and something huge was seen prowling toward it. End as the player leaves."),
    },
    "tavern": {
        "title": "The Copper Lamp",
        "objective": "Protect the survivors sheltering in the tavern.",
        "art": "tavern", "music": "tavern_tension",
        "actions": [{"id": "face_brute", "label": "Face the brute", "combat": "brute", "win": "tavern_after"}],
        "brief": ("The Copper Lamp tavern is crowded with frightened survivors: families, a wounded guard, "
                  "the innkeeper Bhola barring the door. Moments after the player arrives, the door explodes "
                  "inward and a huge asura brute shoulders through, hide thick as tree bark, an iron collar "
                  "of plates around its throat. The player notices the collar leaves a gap at the nape of its "
                  "neck, visible only when it lunges or loses its footing. End as it roars and comes for the "
                  "player. Do NOT narrate any fighting."),
    },
    "tavern_after": {
        "title": "After the Brute",
        "objective": "Go to the palace.",
        "art": "tavern", "music": "city_dark",
        "on_enter": {"restore": ["stamina", "magicka"]},
        "actions": [{"id": "go_palace", "label": "Go to the palace", "to": "palace"}],
        "brief": ("The brute is dead on the tavern floor. The survivors gather around the player. The "
                  "wounded guard and Bhola tell the player to go to the palace: the ruler needs fighters, and "
                  "every attack seems to be converging on the old dungeon beneath the palace. Someone repeats "
                  "the ruler's claim that the dragon Agnivara stole the sun; someone else doubts it. End with "
                  "the player looking toward the palace on the hill under the dead brass wheel."),
    },
    "palace": {
        "title": "The Palace of the Wheel",
        "objective": "Descend into the dungeon beneath the palace.",
        "art": "palace", "music": "palace",
        "actions": [{"id": "descend", "label": "Descend into the dungeon", "combat": "outer_hall", "win": "hall_cleared"}],
        "brief": ("At the palace, the ruler (a proud, tired monarch on a sun-throne) tells the player that the dragon "
                  "Agnivara stole the sun and lairs beneath the palace, and orders them below. Afterwards Mira, a "
                  "young palace apprentice with ink-stained fingers, quietly stops the player. She believes the "
                  "asuras are chasing the old sun seal beneath the palace and that the ruler's story about "
                  "Agnivara is incomplete; she asks the player to look closely at whatever they find below. "
                  "End at the top of the stairs into the dungeon, with asura voices rising from the dark."),
    },
    "hall_cleared": {
        "title": "Beyond the Outer Hall",
        "objective": "Cross the Broken Causeway.",
        "art": "dungeon", "music": "dungeon",
        "actions": [{"id": "causeway", "label": "Cross the Broken Causeway", "combat": "causeway", "win": "causeway_cleared"}],
        "brief": ("In two rich paragraphs: the Outer Hall falls silent. Ahead, a stone causeway spans a black chasm, "
                  "half collapsed. Shield-bearing asuras lock shields across it; archers and two chained brutes "
                  "wait behind them. End as they advance. Do NOT narrate fighting."),
    },
    "causeway_cleared": {
        "title": "The Far Side",
        "objective": "Break Vajraka's ward.",
        "art": "dungeon", "music": "dungeon",
        "actions": [{"id": "ward", "label": "Confront Vajraka", "combat": "vajraka", "win": "vajraka_falls"}],
        "brief": ("In two rich paragraphs: past the causeway, a sanctum glows with fire-glyphs. The priest Vajraka, "
                  "Oath-Keeper of the Flame, sits in a shimmering shield of flame. Stone gargoyles called "
                  "Shilapaksha (stone-winged) line the walls. He says no one passes his oath. End as he raises "
                  "his hands and the stone wings begin to stir. Do NOT narrate fighting."),
    },
    "vajraka_falls": {
        "title": "The Six-Pillar Chamber",
        "objective": "Prepare, then challenge Agnivara.",
        "art": "crystal_chamber", "music": "boss_calm",
        "on_enter": {"heal": 25, "restore": ["stamina", "magicka"]},
        "actions": [{"id": "challenge", "label": "Challenge Agnivara", "combat": "agnivara", "win": "cliffhanger"}],
        "brief": ("Vajraka lies dying. With his last breath he warns that the crystals sustain Agnivara, and that "
                  "they also hold something beneath the city; he does not say what. Beyond him is a vast "
                  "chamber with six glowing crystal pillars; their light streams into Agnivara, a great "
                  "ember-scaled dragon circling above. Note this is the last chance to prepare. End as "
                  "Agnivara sees the player and screams. Do NOT narrate fighting."),
    },
    "cliffhanger": {
        "title": "The Seal Beneath",
        "objective": "Choose.",
        "art": "crystal_chamber", "music": "cliffhanger",
        "actions": [
            {"id": "free", "label": "Free Agnivara and follow it beneath the city", "to": "ending_free"},
            {"id": "ruler", "label": "Side with the ruler, restore the sun, leave Agnivara to die", "to": "ending_ruler"},
            {"id": "mira", "label": "Trust Mira's plan to reinforce the seal", "to": "ending_mira"},
        ],
        "brief": ("Agnivara is beaten and lies broken, but alive. The player expects the sun to return. Instead the "
                  "remaining crystal pillars crack, and a black glow rises from beneath the palace floor. "
                  "Agnivara speaks for the first time: the crystals sustained it, and through it they helped "
                  "hold a seal shut; the asura attacks were never about the sun, they were about what is "
                  "beneath the city. Mira arrives breathless, with a plan to reinforce the seal; the ruler's "
                  "voice echoes from the stairs, demanding the dragon's death so the wheel can open. End on "
                  "the player having to choose."),
    },
    "ending_free": {
        "title": "Into the Dark",
        "objective": "The demo ends here.",
        "art": "ending", "music": "ending", "actions": [], "ending": True,
        "brief": ("Ending: the player frees Agnivara. The wounded dragon lets the player climb on and dives into "
                  "the black glow beneath the city, toward what the seal held. Behind them the ruler's soldiers "
                  "shout 'traitor'. Tease the consequence: the sun stays dark, but the player may face the real "
                  "enemy at its source. Final line: something vast beneath the city opens its eyes."),
    },
    "ending_ruler": {
        "title": "The Sun Restored",
        "objective": "The demo ends here.",
        "art": "ending", "music": "ending", "actions": [], "ending": True,
        "brief": ("Ending: the player sides with the ruler. Agnivara is left to die; the brass wheel opens and "
                  "sunlight floods Suryagarh, and people begin to remember names. The city cheers the player. "
                  "Tease the consequence: Mira looks at the floor, where the black glow has not faded but "
                  "spread. Final line: under the cheering city, the seal gives a long, slow crack."),
    },
    "ending_mira": {
        "title": "The Seal Holds — For Now",
        "objective": "The demo ends here.",
        "art": "ending", "music": "ending", "actions": [], "ending": True,
        "brief": ("Ending: the player trusts Mira. Together they pour the last crystal light into the seal while "
                  "Agnivara lends its fading fire. The black glow sinks. The sun does not return yet, and the "
                  "ruler is furious. Tease the consequence: Mira admits this only buys time, maybe a season. "
                  "Final line: Agnivara whispers that the thing below has learned the player's name."),
    },
}

SYSTEM_PROMPT = """You are the narrator and dungeon master of a dark-fantasy RPG set in Suryagarh, a city inspired by ancient India.
Rules you must follow:
- Write in second person, present tense, addressing the player as "you". Other characters refer to the player by name and their stated pronouns.
- 3 paragraphs, about 200 to 260 words total. Plain prose, no headings, no lists, no markdown.
- Make it vivid and immersive: concrete sensory detail (sound, smell, heat, texture), motion, and atmosphere.
- Give named characters a distinct voice through short, natural dialogue. Vary sentence rhythm; end on tension.
- Stay strictly consistent with the WORLD FACTS and the CHARACTER. Never contradict them or invent new major plot facts.
- Never mention numbers, statistics, dice, health, damage, gold amounts, or game mechanics.
- Never give the player items, weapons, or abilities, and never decide the outcome of a fight. The game engine does that.
- Only the named characters in the scene brief may speak.
- Follow the SCENE BRIEF and end exactly where it says to end."""


def build_prompt(state, scene_id):
    c = state["character"]
    origin = ORIGINS[c["origin"]]
    scene = SCENES[scene_id]
    returning_line = ("They are returning after years away; show what they recognise and what has changed."
                      if origin["returning"] else
                      "This is their first time in the city; show it through fresh eyes.")
    brief = scene["brief"].format(arrival_place=origin["arrival_place"],
                                  recognition=origin["recognition"],
                                  returning_line=returning_line)
    memory = [f"- {e['title']}: {e['text'][:600]}" for e in state["journal"][-2:]]
    user = "\n".join([
        "WORLD FACTS:", *[f"- {f}" for f in WORLD_FACTS], "",
        "CHARACTER:",
        f"- Name: {c['name']}",
        f"- Pronouns: {c['pronouns']}",
        f"- Appearance: {c['appearance']}",
        f"- Ancestry: {ANCESTRIES[c['ancestry']]['flavor']}",
        f"- Origin: {origin['label']}. {origin['summary']}",
        *[f"- Callback: {cb}" for cb in origin["callbacks"]], "",
        "STORY SO FAR:", *(memory or ["- (This is the opening scene.)"]), "",
        f"SCENE: {scene['title']}",
        f"SCENE BRIEF: {brief}",
    ])
    return SYSTEM_PROMPT, user
