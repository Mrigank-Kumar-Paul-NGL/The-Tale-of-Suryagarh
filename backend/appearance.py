"""Character appearance options, grouped into creation steps.

Each option may be limited to some ancestries (`only`) or barred for some (`not`).
The server validates every choice and composes the description Qwen sees.
"""
import re


def _opt(label, only=None, not_=None):
    return {"id": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
            "label": label, "only": only or [], "not": not_ or []}


STEPS = [
    {"id": "complexion", "label": "Complexion", "groups": [
        {"id": "skin", "label": "Skin Tone", "default": "warm_brown", "options": [
            _opt("Light beige"), _opt("Warm beige"), _opt("Cool beige"),
            _opt("Light brown"), _opt("Warm brown"), _opt("Dark brown"),
            _opt("Warm black"), _opt("Deep black"), _opt("Cool black"),
            _opt("Jade-scaled", only=["naga"]), _opt("Copper-scaled", only=["naga"]),
            _opt("Ashen-scaled", only=["naga"]), _opt("Midnight-scaled", only=["naga"]),
            _opt("Golden-furred", only=["vanara"]), _opt("Russet-furred", only=["vanara"]),
            _opt("Grey-furred", only=["vanara"]), _opt("Dark-furred", only=["vanara"]),
        ]},
        {"id": "marks", "label": "Markings", "default": "none", "options": [
            _opt("None"), _opt("Freckles"), _opt("Moles"), _opt("Vitiligo"),
            _opt("A birthmark"), _opt("Ink tattoos"), _opt("Old battle scars"),
            _opt("Hood-pattern scales", only=["naga"]), _opt("A ringed tail", only=["vanara"]),
        ]},
    ]},
    {"id": "eyes", "label": "Eyes", "groups": [
        {"id": "eyes", "label": "Eye Colour", "default": "brown", "options": [
            _opt("Grey"), _opt("Blue"), _opt("Green"),
            _opt("Hazel"), _opt("Brown"), _opt("Black"),
            _opt("Slit-pupiled gold", only=["naga"]), _opt("Slit-pupiled emerald", only=["naga"]),
            _opt("Amber", only=["vanara", "naga"]), _opt("Bright copper", only=["vanara"]),
        ]},
    ]},
    {"id": "hair", "label": "Hair", "groups": [
        {"id": "hair_colour", "label": "Hair Colour", "default": "black", "options": [
            _opt("Black"), _opt("Dark brown"), _opt("Brown"), _opt("Sandy brown"),
            _opt("Auburn"), _opt("Red"), _opt("Dark blonde"), _opt("Blonde"),
            _opt("White"), _opt("Grey"),
            _opt("Blue-black", only=["naga"]), _opt("Verdigris green", only=["naga"]),
            _opt("Golden", only=["vanara"]), _opt("Russet", only=["vanara"]),
        ]},
        {"id": "hair_length", "label": "Hair Length", "default": "shoulder_length", "options": [
            _opt("Shaved"), _opt("Cropped"), _opt("Short"),
            _opt("Shoulder-length"), _opt("Long"), _opt("Waist-length"),
        ]},
        {"id": "hair_texture", "label": "Hair Texture", "default": "wavy", "options": [
            _opt("Straight"), _opt("Wavy"), _opt("Curly"),
            _opt("Coily"), _opt("Kinky"), _opt("Locs"),
        ]},
        {"id": "facial_hair", "label": "Facial Hair", "default": "none", "options": [
            _opt("None"), _opt("Stubble"), _opt("Moustache"),
            _opt("Short beard"), _opt("Full beard"), _opt("Braided beard"),
        ]},
    ]},
    {"id": "height", "label": "Height", "groups": [
        {"id": "height", "label": "Height", "default": "average", "options": [
            _opt("Very short", not_=["naga"]), _opt("Short"), _opt("Average"),
            _opt("Tall"), _opt("Very tall", not_=["vanara"]),
        ]},
        {"id": "build", "label": "Build", "default": "lean", "options": [
            _opt("Slight"), _opt("Lean"), _opt("Athletic"), _opt("Broad"), _opt("Heavyset"),
        ]},
    ]},
]

GROUPS = {g["id"]: g for step in STEPS for g in step["groups"]}


def allowed(option, ancestry):
    if option["only"] and ancestry not in option["only"]:
        return False
    return ancestry not in option["not"]


def validate(looks, ancestry):
    """Return {group_id: option} for valid choices, or raise ValueError naming the bad field."""
    if not isinstance(looks, dict):
        raise ValueError("Appearance choices are missing.")
    out = {}
    for gid, group in GROUPS.items():
        opt = next((o for o in group["options"] if o["id"] == looks.get(gid)), None)
        if opt is None:
            raise ValueError(f"Choose a {group['label'].lower()}.")
        if not allowed(opt, ancestry):
            raise ValueError(f"{opt['label']} is not available for this ancestry.")
        out[gid] = opt
    return out


def describe(chosen, details=""):
    """Compose a plain-English description for the character sheet and for Qwen."""
    L = {k: v["label"].lower() for k, v in chosen.items()}
    skin = L["skin"].replace("-furred", " fur") if "furred" in L["skin"] else f"{L['skin']} skin"
    parts = [f"{L['height'].capitalize()} and {L['build']}, {skin}"]
    if L["marks"] != "none":
        parts[0] += f" with {L['marks']}"
    parts.append(f"{L['eyes']} eyes")
    if L["hair_length"] == "shaved":
        hair = "a shaved head"
    else:
        hair = f"{L['hair_length']} {L['hair_texture']} {L['hair_colour']} hair"
        if L["hair_texture"] == "locs":
            hair = f"{L['hair_colour']} hair in {L['hair_length']} locs"
    parts.append(hair)
    text = ", ".join(parts)
    text += "; clean-shaven." if L["facial_hair"] == "none" else f"; {L['facial_hair']}."
    details = (details or "").strip()
    return f"{text} {details}".strip()
