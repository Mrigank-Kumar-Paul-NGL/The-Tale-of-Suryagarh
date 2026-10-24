"""Qwen's role in combat: narrate resolved events and pick enemy intents from Python's legal list.

Qwen never sees or decides numbers. Its JSON output is constrained by a schema (enum of legal
move ids per enemy) and then re-validated by combat.apply_intents.
"""
import json

import combat
import combat_config as C
import llm
import story

SYSTEM = """You are the narrator and enemy tactician of a dark-fantasy RPG set in Suryagarh, a city inspired by ancient India.
Setting detail (do not state it as a rule): the sky is dark; light comes only from fires, embers and lamps.
The game engine has ALREADY resolved this turn. Reply with JSON containing three fields, in this order:
1. "narration": 3 to 4 vivid, cinematic sentences with sensory detail (the clash of steel, heat, sparks, the enemy's motion), second person, PRESENT tense ("You strike", never "You struck"), in your own words, that retell EVERY numbered event, in order.
   - Cover each numbered event. If the player hit, wounded or killed an enemy, say so. If the player was hurt, say so.
   - Do not add any hit, miss, wound, death, or arrow that is not a numbered event.
   - Never mention numbers, damage, health, stamina, dice, or game terms such as "light attack" or "heavy attack". Do not invent items, spells or allies.
2. "intents": each enemy's NEXT move, chosen only from its listed move ids. Fight cleverly: vary attacks,
   press a tired or wounded player, do not repeat the same move every turn.
3. "foreshadow": ONE evocative sentence hinting at what the enemies are now preparing, matching the moves you chose.
   It describes preparation only; nothing lands yet."""

END_SYSTEM = """You are the narrator of a dark-fantasy RPG set in Suryagarh, a city inspired by ancient India.
Setting detail (do not state it as a rule): the sky is dark; light comes only from fires, embers and lamps.
The game engine has ALREADY resolved the final turn of a fight. Reply with JSON: {"narration": "..."}.
Write 4 to 5 vivid, cinematic sentences rich in sensory detail, second person, PRESENT tense ("You strike", never "You struck"), IN YOUR OWN WORDS (never copy the event lines):
- Retell the numbered events in order, then the moment the fight ends.
- VICTORY: the last foe falls; show the sudden quiet and what the player sees around them.
- DEFEAT: the player falls and the world goes dark. Do not suggest rescue or survival.
- Never mention numbers or game terms. Do not invent items or allies."""


def _player_summary(state):
    c, s = state["character"], state["stats"]
    tired = "exhausted" if s["stamina"] < 25 else "winded" if s["stamina"] < 50 else "steady"
    return (f"{c['name']} ({c['pronouns']}), {story.ANCESTRIES[c['ancestry']]['label']}; {c['appearance']} "
            f"Condition: {combat.condition(s['health'], s['health_max'])}, {tired}.")


def build(state):
    cs = state["combat"]
    enc = C.ENCOUNTERS[cs["id"]]
    events = [e["story"] for e in cs["pending"]["events"] if e.get("story")]
    if not cs["turn"]:
        events = ["The enemies close in and square up to the player. No blows have been exchanged yet."]
    lines = [
        f"ENCOUNTER: {enc['title']}. {enc['goal']}",
        f"PLAYER: {_player_summary(state)}",
        *([f"BATTLE STATE: {combat.status_line(cs)}"] if combat.status_line(cs) else []),
        "NUMBERED EVENTS (already resolved):",
        *[f"{i}. {x}" for i, x in enumerate(events, 1)],
        "",
        "ENEMIES:",
    ]
    choices = {}
    for e in cs["enemies"]:
        cond = combat.condition(e["hp"], e["hp_max"])
        tag = " [object, cannot act]" if combat.kind(e).get("passive") else ""
        last = f" (last move: {e['last']}; prefer a different move)" if e.get("last") and combat.alive(e) else ""
        lines.append(f"- {e['id']}: {e['name']}, {cond}{tag}{last}")
        legal = combat.legal_moves(cs, e)
        if legal:
            choices[e["id"]] = legal
            for mid in legal:
                m = combat.move(e, mid)
                lines.append(f"    move '{mid}': {m['label']} — {m['tell']}" + ("" if m["attack"] else " (not an attack)"))
    over = cs["outcome"] is not None
    if over:
        lines.append(f"\nOUTCOME: {'VICTORY — the player wins this fight.' if cs['outcome'] == 'victory' else 'DEFEAT — the player has fallen.'}")
        schema = {"type": "object", "properties": {"narration": {"type": "string"}}, "required": ["narration"]}
        lines.append('Respond as JSON: {"narration": "..."}')
        return END_SYSTEM, "\n".join(lines), schema, choices
    lines.append(f"\nAt most {enc['max_attackers']} enemies may choose an attack this turn.")
    lines.append('Respond as JSON: {"narration": "...", "intents": {"<enemy id>": "<move id>", ...}, "foreshadow": "..."}')
    schema = {
        "type": "object",
        "properties": {
            "narration": {"type": "string"},
            "intents": {"type": "object",
                        "properties": {eid: {"type": "string", "enum": ids} for eid, ids in choices.items()},
                        "required": list(choices)},
            "foreshadow": {"type": "string"},
        },
        "required": ["narration", "intents", "foreshadow"],
    }
    return SYSTEM, "\n".join(lines), schema, choices


def narrate_turn(state):
    """Call the model (Qwen, or Gemini fallback) for the pending turn. Raises llm.LLMError on failure; state is untouched until success."""
    cs = state["combat"]
    system, user, schema, _ = build(state)
    res = llm.chat(system, user, max_tokens=450, json_schema=schema)
    try:
        data = json.loads(res["text"])
        text = str(data["narration"]).strip()
        hint = str(data.get("foreshadow") or "").strip()
    except (ValueError, KeyError, TypeError):
        raise llm.LLMError(f"The {res['provider']} model returned malformed JSON; please retry.")
    if len(text) < 20:
        raise llm.LLMError(f"The {res['provider']} model returned an empty narration; please retry.")
    notes = []
    if cs["outcome"] is None:
        notes = combat.apply_intents(cs, data.get("intents") or {}, C.ENCOUNTERS[cs["id"]]["max_attackers"])
        if notes:
            combat._log(cs, cs["turn"], [{"who": "system", "text": n} for n in notes])
    cs["narration"] = {"text": text, "foreshadow": hint if cs["outcome"] is None else "", "model": res["model"], "provider": res["provider"], "fallback": res.get("fallback", False), "ms": res["ms"], "tokens": res["tokens"], "turn": cs["turn"]}
    cs["pending"] = None
    return notes
