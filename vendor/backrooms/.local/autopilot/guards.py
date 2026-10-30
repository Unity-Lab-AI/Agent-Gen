"""Hard guards for the autopilot. These run in code, under the model, and the model cannot route around them.

Owner direction this whole autopilot exists for, verbatim:
"remember bhind the scnes you need to be building this whole thing to run on the best model possible thats open
souiurce that can basicly do everything you do that u fully set up from streaming to useing rimworld excactly all as
i do with coding knowledge but doesnt and never shall edit the mod or fix code"

What is enforced here:
  * File writes: only inside .local/autopilot/scratch, only small text files. There is no other write path.
  * File reads: a read-only allowlist (docs, src, Mod, the autopilot's own folder); secrets are never readable.
  * Bridge tools: an explicit allowlist. Lua, scripts, debug actions, mod settings, mod enable/reorder, load game,
    main menu, spawning and god mode are not callable at all.
  * Saves: forced to the rimbridge_save_ prefix.
  * Stream text: every spoken line, chat reply and caption passes the THE STREAM IS CLEAN filter (the same
    SOFTEN + CLEAN_BLOCK rules unity-voice.py uses) plus emoji, URL, path and secret stripping.
"""
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.path.join(HERE, "scratch")

# ---------------------------------------------------------------------------------------------------------------
# File writes: scratch only
# ---------------------------------------------------------------------------------------------------------------
WRITE_EXT = (".md", ".txt", ".json", ".jsonl", ".log")
MAX_WRITE = 64 * 1024


class GuardError(Exception):
    pass


def _inside(path, base):
    path, base = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(base))
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:          # different drives
        return False


def scratch_path(name):
    """Resolve a model-supplied note name to a file inside scratch/, or refuse."""
    name = str(name or "").strip().replace("\\", "/")
    if not name or name.startswith("/") or ":" in name or ".." in name.split("/"):
        raise GuardError("write refused: give a plain relative name inside the scratch folder")
    if not name.lower().endswith(WRITE_EXT):
        raise GuardError("write refused: only %s notes" % ", ".join(WRITE_EXT))
    full = os.path.join(SCRATCH, name)
    if not _inside(full, SCRATCH):
        raise GuardError("write refused: outside the scratch folder")
    return full


def scratch_write(name, text, append=False):
    full = scratch_path(name)
    text = str(text)
    if len(text.encode("utf-8")) > MAX_WRITE:
        raise GuardError("write refused: note larger than 64 KB")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a" if append else "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.relpath(full, ROOT)


# ---------------------------------------------------------------------------------------------------------------
# File reads: read-only allowlist (coding KNOWLEDGE, never coding)
# ---------------------------------------------------------------------------------------------------------------
READ_ROOTS = ["docs", "src", "Mod", "About", "README.md", "CHANGELOG.md", os.path.join(".local", "autopilot")]
READ_DENY = re.compile(r"(\.env|user\.json|secret|token|password|credential|twitch-profile|owner_twitch|\.pem|\.key$)", re.I)
MAX_READ = 24000


def read_allowed(rel):
    rel = str(rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ":" in rel or ".." in rel.split("/"):
        raise GuardError("read refused: give a repo-relative path")
    full = os.path.join(ROOT, rel)
    if READ_DENY.search(rel):
        raise GuardError("read refused: secrets are not readable")
    if not any(_inside(full, os.path.join(ROOT, r)) for r in READ_ROOTS):
        raise GuardError("read refused: readable roots are " + ", ".join(READ_ROOTS))
    if not os.path.exists(full):
        raise GuardError("no such file: " + rel)
    return full


# ---------------------------------------------------------------------------------------------------------------
# Bridge allowlist
# ---------------------------------------------------------------------------------------------------------------
# Read-only: executed even in --dry-run (they change nothing the live player relies on).
BRIDGE_READ = {
    "rimworld/list_colonists", "rimworld/list_letters", "rimworld/list_alerts", "rimworld/list_messages",
    "rimworld/get_cells_info", "rimworld/get_cell_info", "rimworld/get_map_target_info", "rimworld/get_ui_state",
    "rimworld/get_ui_layout", "rimworld/get_camera_state", "rimworld/list_zones", "rimworld/list_areas",
    "rimworld/list_architect_categories", "rimworld/list_architect_designators", "rimworld/list_main_tabs",
    "rimworld/list_inspect_tabs", "rimworld/get_selected_pawn_inventory_state", "rimworld/get_designator_state",
    "rimworld/get_game_info", "rimworld/find_random_cell_near",
}
# Game actions: printed, not executed, in --dry-run.
BRIDGE_ACT = {
    "rimworld/select_pawn", "rimworld/deselect_pawn", "rimworld/clear_selection", "rimworld/right_click_cell",
    "rimworld/get_context_menu_options",   # needs a right_click first, and opening a menu is a UI change
    "rimworld/execute_context_menu_option", "rimworld/close_context_menu", "rimworld/set_draft",
    "rimworld/frame_pawns", "rimworld/jump_camera_to_pawn", "rimworld/jump_camera_to_cell", "rimworld/frame_cell_rect",
    "rimworld/set_camera_zoom", "rimworld/move_camera", "rimworld/set_time_speed", "rimworld/pause_game",
    "rimworld/play_for", "rimworld/play_until_letter", "rimworld/save_game", "rimworld/apply_architect_designator",
    "rimworld/select_architect_designator", "rimworld/drag_cell", "rimworld/click_cell", "rimworld/open_main_tab",
    "rimworld/close_main_tab", "rimworld/click_ui_target", "rimworld/open_letter",
    "rimworld/dismiss_letter", "rimworld/execute_gizmo", "rimworld/list_selected_gizmos", "rimworld/open_inspect_tab",
    "rimworld/close_window", "rimworld/press_accept", "rimworld/activate_alert", "rimworld/set_zone_target",
    "rimworld/take_screenshot",
}
BRIDGE_ALLOWED = BRIDGE_READ | BRIDGE_ACT
# Belt and braces: even if someone widens the allowlist later, these never pass.
BRIDGE_NEVER = re.compile(r"(lua|script|debug|dpa_|mod_|_mod\b|mods\b|reorder|load_game|main_menu|god_mode|spawn|"
                          r"language|job_logging|start_debug|update_mod|reload_mod|compile|set_debug)", re.I)
# Labels a UI click or context-menu option may never carry.
UI_NEVER = re.compile(r"(\bmods?\b|dev ?mode|debug|\bquit\b|main menu|load|delete|overwrite|language|options|"
                      r"\bdev:|god mode|abandon|banish|release (?:prisoner|to the wild)|execute prisoner)", re.I)

PLAY_FOR_MAX_MS = 30000
GIZMO_LIST_MIN_GAP_S = 20.0   # PLAYSCRIPT: "List gizmos over and over -- the bridge read from the wrong thread and the game crashed"


def check_bridge(name, args):
    if name not in BRIDGE_ALLOWED or BRIDGE_NEVER.search(name.split("/", 1)[-1]):
        raise GuardError("bridge tool not allowed: " + name)
    args = dict(args or {})
    if name == "rimworld/save_game":
        args["saveName"] = save_name(args.get("saveName"))
    if name == "rimworld/play_for":
        args.pop("ticks", None)        # PLAYSCRIPT: ticks are rejected and the game does not move
        args["durationMs"] = max(500, min(int(args.get("durationMs") or 5000), PLAY_FOR_MAX_MS))
    if name == "rimworld/execute_context_menu_option":
        if UI_NEVER.search(str(args.get("label") or "")):
            raise GuardError("menu option refused by guard")
    if name == "rimworld/take_screenshot":
        args.pop("fileName", None)
        args["suppressMessage"] = True
    return args


def save_name(raw):
    tail = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "autopilot")).strip("_") or "autopilot"
    tail = re.sub(r"^(rimbridge_save_)+", "", tail, flags=re.I)
    return ("rimbridge_save_" + tail)[:60]


# ---------------------------------------------------------------------------------------------------------------
# THE STREAM IS CLEAN
# ---------------------------------------------------------------------------------------------------------------
def _voice_rules():
    try:
        spec = importlib.util.spec_from_file_location("unity_voice_rules", os.path.join(ROOT, ".claude", "tools", "unity-voice.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SOFTEN, mod.CLEAN_BLOCK
    except Exception:
        return [], re.compile(r"(f+u+c+k|sh+i+t|c+u+n+t|n+i+g+g|\b(?:bitch\w*|damn\w*|hell|ass|asshole\w*|crap\w*|"
                              r"piss\w*|dick\w*|cock\w*|pussy|sex\w*|whore\w*|slut\w*|bastard\w*|retard\w*|fag\w*|"
                              r"weed|joint|stoned|cocaine|meth|wtf|stfu|losers?|idiots?|morons?)\b)", re.I)


SOFTEN, CLEAN_BLOCK = _voice_rules()
EXTRA_BLOCK = re.compile(r"(\bkill yourself\b|\bkys\b|\bshut up\b|\bstupid\b|\bdumb\b|\bugly\b|\btrash\b(?= (?:viewer|chat|person|people)))", re.I)


def _secret_words():
    """Words that must never be said on stream: the owner's Twitch handle (kept out of this source on purpose)."""
    words = []
    path = os.path.join(HERE, "secret-words.txt")     # one per line, owner-maintained, never shown to the model
    try:
        words += [w.strip() for w in open(path, encoding="utf-8") if w.strip() and not w.startswith("#")]
    except OSError:
        pass
    return [w for w in words if len(w) >= 3]


# Owner: "dont strip urls, like she yould say for example instead of https://www.unityailab.com she would say unity ai
# lab dot com". A link is turned into how a person says it: no https or www, "dot" between the parts, known names split
# into their words, the path left off.
SPOKEN_NAMES = {"unityailab": "unity ai lab", "rimworld": "rim world", "twitch": "twitch", "github": "git hub",
                "youtube": "you tube", "discord": "discord", "ludeon": "ludeon"}


def spoken_domain(domain):
    parts = [SPOKEN_NAMES.get(p.lower(), p.lower().replace("-", " ")) for p in domain.split(".")]
    return " " + " dot ".join(parts) + " "



def clean_for_stream(text, max_len=320):
    """Stream-safe version of `text`, or None when it cannot be made clean (then nothing is said)."""
    if text is None:
        return None
    t = str(text)
    t = re.sub(r"\*[^*]{0,120}\*|\[[^\]]{0,200}\]|<[^>]{0,120}>", " ", t)         # stage directions, tags
    t = re.sub(r"(?:https?://)?(?:www\.)?([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|net|org|io|ai|gg|tv|co|dev|app|lab|me))(?:/\S*)?",
               lambda m: spoken_domain(m.group(1)), t)
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)   # anything left that is still a raw link is not sayable
    t = re.sub(r"(?:[A-Za-z]:)?(?:[\\/][\w.\-]+){2,}", " ", t)                     # file paths
    t = re.sub(r"\b[\w\-]+\.(?:py|cjs|js|cs|xml|json|md|dll|bat|cmd)\b", " ", t)   # filenames
    t = re.sub(r"#\w+", " ", t)
    t = t.replace("’", "'").replace("‘", "'").replace("“", "").replace("”", "")
    t = re.sub(r"\s*[–—]\s*", ", ", t)
    t = "".join(ch for ch in t if ord(ch) < 0x2190)                                # emoji, pictographs, arrows
    t = re.sub(r"[_~`^|\\{}]+", " ", t)
    for w in _secret_words():
        t = re.sub(re.escape(w), "my friend", t, flags=re.I)
    for pat, rep in SOFTEN:
        t = re.sub(pat, rep, t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -,")
    if len(t) > max_len:
        cut = t[:max_len]
        t = cut[:cut.rfind(" ")] if " " in cut else cut
    if len(t) < 2 or CLEAN_BLOCK.search(t) or EXTRA_BLOCK.search(t) or TECH_BLOCK.search(t):
        return None
    return t


# Owner, 2026-10-10: "tell chat whats up too not the details tho" -- and live, she told chat "the bridge server is
# being a total brat again and refusing connections, so I can't load the Backrooms mod". The plumbing is never
# stream material (and that line was not even true). A line that talks about it is not said at all.
TECH_BLOCK = re.compile(r"\b(bridge|server|servers|connection|connections|socket|port|api|script|scripts|"
                        r"python|ollama|model|tokens?|prompt|mod loader|load(?:ing)? the (?:backrooms )?mod|"
                        r"rimbridge|automation|autopilot|crash(?:ed|ing)?(?!\s*-?\s*land)|bug(?:gy|s)?|error|exception|code)\b", re.I)
# "crash landed" / "Crashlanded" is the scenario, not the plumbing (run 5, 01:57: her hello line blocked twice for it)


def clean_viewer_name(who):
    """A viewer's name, safe to say: letters/digits only, and never one of the secret words."""
    w = re.sub(r"[^A-Za-z0-9_]", "", str(who or ""))[:25]
    if not w or any(s.lower() == w.lower() for s in _secret_words()):
        return None
    w = w.replace("_", " ").strip()
    return w if clean_for_stream(w) else None
