"""The autopilot's whole world: a fixed tool registry. If a capability is not in TOOLS, the model does not have it.

There is NO shell tool, NO generic file-write tool, NO build/compile/git tool, NO lua/script/debug bridge tool.
The only write the model can cause is a note inside .local/autopilot/scratch (guards.scratch_write). Scripts it can
run are a fixed list of absolute paths with typed, validated arguments, never a shell string.
"""
import base64
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

import guards
from guards import GuardError

HERE = guards.HERE
ROOT = guards.ROOT
QA = os.path.join(ROOT, ".local", "qa")
CT = os.path.join(ROOT, ".claude", "tools")
STUDIO = os.environ.get("STUDIO_URL", "http://127.0.0.1:4317")
OUTBOX = os.path.join(ROOT, ".claude", ".studio-outbox.jsonl")
PY = sys.executable
SCRIPTS = {   # the ONLY scripts the autopilot ever runs; every one is an existing, owner-made stream/game tool
    "run_list": os.path.join(QA, "run-list.py"),
    "empire": os.path.join(QA, "empire.py"),
    "play": os.path.join(QA, "play.py"),
    "api_prio": os.path.join(QA, "api-prio.py"),
    "speak": os.path.join(CT, "unity-speak.py"),
    "glance": os.path.join(CT, "unity-glance.py"),
    "cam": os.path.join(CT, "unity-cam.py"),
    "snap": os.path.join(CT, "unity-snap.py"),
    "automate": os.path.join(QA, "automate.py"),                     # the mod's own command channel: no mouse, no screen
    "twitch": os.path.join(ROOT, ".local", "tw", "twitch-say.py"),  # the real Twitch chat, title, category
}
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles choke on emoji in model output
except Exception:
    pass
MOODS = ("chill", "hype", "angry", "focus", "laugh", "smug", "scared", "sad")


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    try:
        guards.scratch_write("autopilot.log", line + "\n", append=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------------
# Bridge: one persistent session (same pattern as run-list.py / frontier.py)
# ---------------------------------------------------------------------------------------------------------------
class Bridge:
    def __init__(self, offline=False):
        self.offline = offline
        self.sock = None
        self.buf = bytearray()
        spec = importlib.util.spec_from_file_location("qa_bridge", os.path.join(QA, "bridge.py"))
        self.b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.b)

    def _connect(self):
        port, tok = self.b.endpoint()
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = bytearray()
        self.b.exchange(self.sock, self.buf, "session/hello", {"token": tok, "bridgeVersion": "autopilot/1",
                                                               "platform": "windows", "launchId": str(uuid.uuid4())})

    def call(self, name, args=None):
        if self.offline:
            return {"offline": True, "note": "no bridge in --offline mode"}
        for attempt in range(2):
            try:
                if self.sock is None:
                    self._connect()
                r = self.b.exchange(self.sock, self.buf, "tools/call", {"name": name, "arguments": args or {}})
                r = r.get("result", r) if isinstance(r, dict) else r
                return r.get("structuredContent", r) if isinstance(r, dict) else r
            except (SystemExit, OSError, ValueError) as e:     # bridge.py raises SystemExit on bridge errors
                try:
                    self.sock and self.sock.close()
                except Exception:
                    pass
                self.sock = None
                if attempt:
                    return {"error": str(e)[:600]}
        return {"error": "bridge unavailable"}

    def schemas(self):
        """Input schemas of the allowlisted bridge tools, live if possible, else the cached copy."""
        listed = None
        if not self.offline:
            try:
                if self.sock is None:
                    self._connect()
                listed = self.b.exchange(self.sock, self.buf, "tools/list", {})
                listed = listed.get("tools", listed)
            except (SystemExit, OSError, ValueError):
                self.sock = None
        if not listed:
            listed = json.load(open(os.path.join(HERE, "bridge-tools.json"), encoding="utf-8"))
        return {t["name"]: t for t in listed if t.get("name") in guards.BRIDGE_ALLOWED}


def run_script(key, args, timeout=300, env_extra=None):
    """Run one of the fixed SCRIPTS with a list of already-validated string args. Never a shell."""
    path = SCRIPTS[key]
    env = dict(os.environ, **(env_extra or {}))
    try:
        p = subprocess.run([PY, path] + [str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=ROOT, env=env, shell=False)
        return (p.stdout or "")[-6000:] + (("\nSTDERR: " + p.stderr[-1500:]) if p.returncode else "")
    except subprocess.TimeoutExpired:
        return "timed out after %ds" % timeout


def _walk_targets(node, out):
    if isinstance(node, dict):
        tid = node.get("targetId") or node.get("id")
        label = " ".join(str(node.get(k) or "") for k in ("label", "text", "tooltip", "name")).strip()
        if node.get("targetId"):
            out[str(tid)] = label
        for v in node.values():
            _walk_targets(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_targets(v, out)


def _trim(obj, limit=5000):
    s = json.dumps(obj, ensure_ascii=False, default=str)
    s = re.sub(r"<color=[^>]*>|</color>", "", s)
    return s if len(s) <= limit else s[:limit] + " ...[truncated]"


# Words no spoken sentence ends on: a say line that stops on one of them (and carries no full stop) arrived cut.
_DANGLING = frozenset("""a an the and or but nor so yet until till unless if when whenever while because since
    as than that which who whom whose where of to in on at by for with from into onto upon over under about
    between through during before after without within along across behind beyond toward towards against
    per via my your our their his her its this these those every each some any no not very""".split())


def _not_said(result):
    """True for the strings _speak hands back when a line was NOT said (the brain acts on them as-is)."""
    return isinstance(result, str) and result.startswith(("CUT:", "REPEAT:", "SPEAK FAILED:"))


# ---------------------------------------------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------------------------------------------
class Toolbox:
    def __init__(self, dry_run=False, offline=False, raw_voice=True):
        self.dry = dry_run or offline
        self.offline = offline
        self.raw_voice = raw_voice
        self.bridge = Bridge(offline=offline)
        self.bridge_schemas = self.bridge.schemas()
        self.ui_targets = {}          # targetId -> label, from the last get_ui_layout (click guard)
        self.last_gizmo_list = 0.0
        self.last_speech = 0.0
        self.pending_images = []      # base64 PNGs for the next model message (vision)
        self.spoken = []              # what was said this tick
        self.live_top = None          # (rung id, family, priority) of the live top rung, set by the loop every turn
        self.last_menu = {}           # (pawn_id, x, z) -> the real context-menu labels, from the last option-less order_pawn
        self.known_gizmos = set()     # gizmo ids from the last list_selected_gizmos, the only ones execute_gizmo takes
        self._empire_at = 0.0         # empire_pass: when it last ran and what it reported (the cooldown guard)
        self._empire_report = ""
        self.greeted_this_tick = set()
        self.wants_time = None        # the speed she asked for this turn; applied when the turn ends (owner: never run while planning)
        self.paused_on_purpose = False
        self.last_speed = ""
        self.time_was_running = False
        self.local = self._local_tools()

    # -- tool specs for Ollama --------------------------------------------------------------------------------
    # The tools that actually play the colony. Owner: "no she has to do it" -- so she has to be fast, and 72 tool
    # definitions (~9k tokens) were re-read on CPU every turn. Camera minutiae, UI layout, tab and save plumbing
    # stay registered (a call to them still works) but are not offered in the prompt.
    CORE = {"ladder", "ladder_set", "pawn_priorities", "new_colony", "game_state", "look", "pawn_check", "order_pawn", "game_set", "say", "reply_chat", "reply_owner", "plan", "webcam", "snap",
            "twitch_chat", "note", "read_doc", "run_list", "empire_pass", "play_slices",
            # the dialog rung and the prompt's HOW TO WORK need these; they were never sent to her (2026-10-13 audit)
            "game_get_ui_layout", "game_click_ui_target", "game_open_main_tab", "game_list_main_tabs", "game_close_main_tab", "game_click_cell",
            "game_apply_architect_designator", "game_select_architect_designator", "game_list_architect_designators",
            "game_list_architect_categories", "game_set_zone_target", "game_list_zones", "game_list_areas",
            "game_get_cell_info", "game_get_cells_info", "game_select_pawn", "game_set_draft", "game_execute_gizmo",
            "game_list_selected_gizmos", "game_get_context_menu_options", "game_execute_context_menu_option",
            "game_right_click_cell", "game_drag_cell", "game_list_letters", "game_open_letter", "game_dismiss_letter",
            "game_pause_game", "game_set_time_speed", "game_jump_camera_to_cell", "game_list_colonists",
            "game_take_screenshot", "game_list_alerts", "game_close_window", "game_press_accept"}

    def specs(self):
        return [sp for sp in self._all_specs() if sp["function"]["name"] in self.CORE]

    def _all_specs(self):
        specs = []
        for name, t in sorted(self.bridge_schemas.items()):
            params = json.loads(json.dumps(t.get("inputSchema") or {"type": "object", "properties": {}}))
            for prop in (params.get("properties") or {}).values():   # keep the prompt small for a local model
                if isinstance(prop, dict) and len(prop.get("description", "")) > 110:
                    prop["description"] = prop["description"][:110]
            kind = "READ-ONLY" if name in guards.BRIDGE_READ else "GAME ACTION"
            specs.append({"type": "function", "function": {
                "name": self.ollama_name(name),
                "description": "[%s] %s" % (kind, (t.get("description") or name)[:180]),
                "parameters": params}})
        for name, (desc, params, _fn) in self.local.items():
            specs.append({"type": "function", "function": {"name": name, "description": desc, "parameters": params}})
        return specs

    @staticmethod
    def ollama_name(bridge_name):
        return bridge_name.replace("rimworld/", "game_").replace("rimbridge/", "bridge_")

    def _bridge_name(self, oname):
        for n in self.bridge_schemas:
            if self.ollama_name(n) == oname:
                return n
        return None

    # -- dispatch ----------------------------------------------------------------------------------------------
    def dispatch(self, oname, args):
        if not isinstance(args, dict):
            try:
                args = json.loads(args or "{}")
            except Exception:
                args = {}
        try:
            if oname in self.local:
                return self.local[oname][2](**args)
            bname = self._bridge_name(oname)
            if not bname:
                return "unknown tool %s -- you only have the listed tools" % oname
            return self._bridge(bname, args)
        except GuardError as e:
            log("GUARD", oname, e)
            return "REFUSED BY GUARD: %s" % e
        except TypeError as e:
            return "bad arguments for %s: %s" % (oname, e)
        except Exception as e:
            return "error in %s: %s" % (oname, str(e)[:400])

    def _bridge(self, name, args):
        args = guards.check_bridge(name, args)
        if name in ("rimworld/list_letters", "rimworld/open_letter", "rimworld/dismiss_letter"):
            self._mark_letters_seen()
        if name == "rimworld/execute_context_menu_option":
            # live, 10-10: she clicked option 1 of a menu that was not there, turn after turn ("quest accepted")
            m = self.bridge.call("rimworld/get_context_menu_options", {})
            m = m.get("result", m); m = m.get("structuredContent", m) if isinstance(m, dict) else {}
            if m.get("success") is False or not (m.get("options") or m.get("menuOptions") or m.get("items") or m.get("success")):
                raise GuardError("no context menu is open -- nothing was clicked. Letters are read with game_open_letter "
                                 "(real ids from game_list_letters) and answered by their own buttons, not a menu option")
        # owner: "why did she unpause beforee seeting all the pawn settings" -- time stays stopped until she
        # has marked pawns_set and assign_set true on her ladder (ladder_set mark) after doing them.
        starts_time = (name == "rimworld/pause_game" and not args.get("pause", True)) or \
                      (name == "rimworld/set_time_speed" and str(args.get("speed", "")).lower() not in ("", "0", "paused")) or \
                      name in ("rimworld/play_for", "rimworld/play_until_letter")
        if starts_time:
            why = self._time_blocked()
            if why:
                raise GuardError(why)
            # owner (run 5, 2026-10-14 02:40): "she can NOT [let the game run] while she plans" -- the game stays paused for the
            # whole turn; the wish is kept and the loop applies it when the turn ends (autopilot._time_plan_end), only with work queued
            if name in ("rimworld/pause_game", "rimworld/set_time_speed"):
                sp = str(args.get("speed", "")) if name == "rimworld/set_time_speed" else ""
                self.wants_time = sp or getattr(self, "last_speed", "") or "Normal"
                self.paused_on_purpose = False
                return ("noted: time runs at %s the moment this turn ends (the game stays paused while you plan -- owner's rule) "
                        "and only if the crew has work queued; finish your orders, then end the turn" % self.wants_time)
        if name == "rimworld/pause_game" and args.get("pause", True):
            self.paused_on_purpose = True
            self.wants_time = None
        if name == "rimworld/click_ui_target":
            tid = str(args.get("targetId") or "")
            if tid not in self.ui_targets:
                raise GuardError("unknown ui target: call game_get_ui_layout first and click only a listed targetId")
            if guards.UI_NEVER.search(self.ui_targets[tid] or "") or guards.UI_NEVER.search(tid):
                raise GuardError("that button is off limits to the autopilot")
        if name == "rimworld/list_selected_gizmos":
            if time.time() - self.last_gizmo_list < guards.GIZMO_LIST_MIN_GAP_S:
                raise GuardError("gizmos were listed under 20 s ago; reuse that list (listing them repeatedly crashed the game)")
            self.last_gizmo_list = time.time()
        if name == "rimworld/execute_gizmo":
            # run 3 (2026-10-13 21:46, 22:04): a gizmo executed blind on whatever was selected. Only an id from the last list.
            gid = str(args.get("gizmoId") or "")
            if gid not in self.known_gizmos:
                raise GuardError("unknown gizmo id: list_selected_gizmos first (on the thing you mean) and execute only an id from that list")
        if name in ("rimworld/apply_architect_designator", "rimworld/select_architect_designator"):
            # run 5 (2026-10-14 00:31): a made-up roof designator id applied three times ("the tool cannot find it")
            did = str(args.get("designatorId") or "")
            if did not in getattr(self, "known_designators", set()):
                raise GuardError("unknown designator id: game_list_architect_designators <category> first and use only an id from that list")
        if self.dry and name not in guards.BRIDGE_READ:
            log("DRY-RUN would call", name, json.dumps(args))
            return "dry-run: not executed (%s %s)" % (name, json.dumps(args))
        log("CALL", name, json.dumps(args)[:300])
        r = self.bridge.call(name, args)
        if name == "rimworld/list_selected_gizmos":
            try: self.known_gizmos = set(re.findall(r'selection-gizmo:[A-Za-z0-9:_-]+', json.dumps(r)))
            except Exception: self.known_gizmos = set()
        if name == "rimworld/list_architect_designators":
            try: self.known_designators = getattr(self, "known_designators", set()) | set(re.findall(r'architect-designator:[A-Za-z0-9:_-]+', json.dumps(r)))
            except Exception: pass
        if name == "rimworld/get_ui_layout" and isinstance(r, dict):
            found = {}
            _walk_targets(r, found)
            self.ui_targets = found
        if name == "rimworld/take_screenshot" and isinstance(r, dict) and r.get("path"):
            self._attach(r["path"])
            return "screenshot attached as an image for your next look"
        return _trim(r)

    def _attach(self, path):
        try:
            from PIL import Image
            im = Image.open(path).convert("RGB")
            im.thumbnail((1280, 1280))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            self.pending_images = [base64.b64encode(buf.getvalue()).decode()]
        except Exception as e:
            log("image attach failed", e)

    # -- local tools -------------------------------------------------------------------------------------------
    def _local_tools(self):
        S = lambda props, req=(): {"type": "object", "properties": props, "required": list(req)}
        s, i, b = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
        # Voice delivery for say/reply_chat: the exact emotions and speech acts Unity's own voice model is trained on
        # (training/voice/dataset_contract.py). Optional; "[laughter]" may appear in the text itself.
        EMO = {"type": "string", "enum": ["neutral", "warm", "happy", "amused", "excited", "sad", "concerned", "frustrated", "surprised"]}
        ACT = {"type": "string", "enum": ["statement", "yes_no_question", "wh_question", "exclamation", "instruction", "reassurance", "aside"]}
        return {
            "look": ("[READ-ONLY] Take a screenshot of the game exactly as the stream sees it and SEE it (vision).",
                     S({}), self.t_look),
            "game_state": ("[READ-ONLY] One-shot brief: colonists (map, position, job, drafted/downed/mental state), "
                           "letters, alerts, recent messages, UI window stack.", S({}), self.t_state),
            "pawn_check": ("[READ-ONLY-ish: selects the pawn] Select a colonist, open its Needs or Health tab and SEE it "
                           "so you can find the worst need/injury.",
                           S({"pawn": s, "tab": {"type": "string", "enum": ["Needs", "Health", "Gear", "Character"]}}, ["pawn"]),
                           self.t_pawn_check),
            "order_pawn": ("[GAME ACTION] Right-click order for one pawn at a cell through the in-game menu "
                           "(.local/qa/api-prio.py). Omit option to list the menu; option is a label prefix like "
                           "'Haul' or 'Prioritize'. queue=true adds after current orders.",
                           S({"pawn_id": s, "x": i, "z": i, "option": s, "queue": b}, ["pawn_id", "x", "z"]),
                           self.t_order_pawn),
            "play_slices": ("[GAME ACTION] Let the game run N x 10 s at Superfast (1-6) via play.py; it stops on any "
                            "letter or dialog that needs a decision and prints it.", S({"slices": i}, ["slices"]),
                            self.t_play),
            "run_list": ("[MAINTENANCE] Run the maintenance list (.local/qa/run-list.py). Prints OK/FIX lines; the "
                         "first FIX is your current goal. Note: it changes the selected pawn.", S({}), self.t_run_list),
            "empire_pass": ("[MAINTENANCE] One empire.py pass (stock orders, arms, self-tend, hunt, power and food "
                            "checks). report_only=true only reports.", S({"report_only": b}), self.t_empire),
            "say": ("[STREAM] Say a line out loud on stream in Unity's voice (TTS + overlay chat + an auto picture). "
                    "Clean only: no swearing, no degrading, no emoji, one to three short sentences.",
                    S({"text": s, "emotion": EMO, "act": ACT}, ["text"]), self.t_say),
            "reply_chat": ("[STREAM] Answer a Twitch viewer by name, out loud and in the overlay chat. chat_id is the "
                           "number given with their message.", S({"chat_id": i, "viewer": s, "text": s, "emotion": EMO, "act": ACT},
                                                                  ["chat_id", "viewer", "text"]), self.t_reply),
            "reply_owner": ("[PRIVATE] Answer the OWNER in the private admin channel (Persona Studio window / admin "
                            "panel). Never spoken, never on stream. msg_id is the number given with their message.",
                            S({"msg_id": i, "text": s}, ["msg_id", "text"]), self.t_reply_owner),
            "new_colony": ("Start a brand-new colony on the company scenario, set up the owner's way (world 30%, 300x300, "
                           "Spring, pollution 0, factions, mountainous forest tile, the Godsmultiplayer ideoligion, the "
                           "Preset3 crew, day one). ONLY when the owner orders it. It abandons the current colony.",
                           S({"reason": s}, ["reason"]), self.t_new_colony),
            "plan": ("Big planning only (a new base layout, a raid plan, the mountain move, the gate, the space push). "
                     "Owner: \"thinking only for massive plaanning needs and she voice it first and pouses\". Say on "
                     "stream what you are planning, the game is paused, and your NEXT turn thinks deeply. Never for "
                     "ordinary moves.", S({"what": s}, ["what"]), self.t_plan),
            "webcam": ("[STREAM] Re-render Unity's webcam with a mood and a short clean caption (raids, deaths, wins, "
                       "chat moments). Optional scene: a few words of what you are doing, holding or wearing right now -- "
                       "your own idea or where chat took the talk. Write what the camera SEES, not the question: 'holding a "
                       "fluffy cat', 'wearing a green crop top', 'jumping in mid air', 'peace sign', 'eating pizza'. "
                       "Never nudity: you stay dressed on stream.",
                       S({"mood": {"type": "string", "enum": list(MOODS)}, "caption": s, "scene": s},
                                           ["mood", "caption"]), self.t_webcam),
            "snap": ("[STREAM] Post an annotated screenshot of a map rect to the webcam panel with up to 3 circled "
                     "marks. Moves the camera to the rect.",
                     S({"x": i, "z": i, "w": i, "h": i, "caption": s,
                        "marks": {"type": "array", "items": {"type": "object", "properties": {"x": i, "z": i, "note": s}}}},
                       ["x", "z", "w", "h", "caption"]), self.t_snap),
            "read_doc": ("[READ-ONLY] Read a repo file for knowledge (docs/, src/, Mod/ ...). Reading only: you can "
                         "never edit, build or fix code. offset/limit are line numbers.",
                         S({"path": s, "offset": i, "limit": i}, ["path"]), self.t_read),
            "ladder": ("Read your PLC ladder: the live rung(s) for what is measured right now, every rung that holds, the "
                       "tag table (constants + live setpoints) and your own marks and rungs. Check it at the start of a turn.",
                       S({}, []), self.t_ladder),
            "ladder_set": ("Edit your ladder on the fly (open-ended, for the whole empire): op 'mark' (name, value true/false "
                           "or a number, e.g. title_rank 4) records what the game cannot measure; op 'tag' (name, value) "
                           "moves a variable setpoint within its bounds (constants are owner-only); op 'add_rung' (rung: "
                           "{id, priority, when: {measured_key: value or '<X' '>X' '<=X' '>=X' '!=X'}, then: [actions], "
                           "why, latch}) adds or replaces a rung of your own; op 'remove_rung' (name) removes one of "
                           "yours. Book rungs from the owner cannot be deleted.",
                           S({"op": {"type": "string", "enum": ["mark", "tag", "add_rung", "remove_rung"]}, "name": s,
                              "value": {"type": ["string", "number", "boolean"]}, "rung": {"type": "object"}}, ["op"]),
                           self.t_ladder_set),
            "pawn_priorities": ("[GAME ACTION, NO MOUSE] Set ONE pawn's whole work grid in one step, the owner's way: every work "
                                "type from Firefighter through Cooking = 1, then the levels you give in 'custom' (work name -> "
                                "1-4, 0 = off) for the rest. Names: Firefighter Patient Doctor PatientBedRest BasicWorker Warden "
                                "Handling Cooking Hunting Construction Growing Mining PlantCutting Smithing Tailoring Art "
                                "Crafting Hauling Cleaning Research. Do one call per pawn.",
                                S({"pawn": s, "custom": {"type": "object", "description": "work name -> level 0-4 for types after Cooking"}},
                                  ["pawn"]), self.t_pawn_priorities),
            "game_set": ("[GAME ACTION, NO MOUSE] Set a field directly through the mod's own automation channel -- works "
                         "with the window minimised. cmd is one of set_zone_plant (x,z,plant e.g. Plant_Rice), "
                         "set_zone_sowing (x,z,allow), set_work_priority (pawn,work,level 0-4), set_bed_owner "
                         "(x,z,owner colonist|prisoner|slave), add_bill (recipe e.g. CookMealSimple, count; x,z optional -- it finds the nearest built table), "
                         "set_area (pawn,area label or empty). SETUP, one call each, no clicking: explore (every pawn "
                         "through every door, digs into sealed rooms -- repeat until it says nothing left), rooms (lists "
                         "explored rooms), stockpile_room (room id, mode food|nofood -- a stockpile filling that room), "
                         "stockpile_filter (x,z,mode food|nofood|all, priority), beds, shelves, stove, crops (plant), "
                         "hunt, day_one, assign (the Assign tab: pawn or empty for all, food Fine, medicine Best, hostility Attack). "
                         "OPEN-GROUND CAMP (Crashlanded, no rooms): unforbid (every starting item), chop (count = wood wanted, nearest trees to the crew), "
                         "shelter (w,h inside size; a wood room + door + roof beside the crew), stockpile_camp (nofood: the Main store over the supply pile; food: a corner carved out of it, same walls, same roof -- never a zone in the open), "
                         "dump (a dumping zone on open ground outside the rooms; corpses switched OFF in every other store -- bodies go nowhere else), "
                         "haul (every loose stack within 30 cells unforbidden + Hauling priority 1 for all: the pile goes into the store first), "
                         "cancel (x,z,w,h: every planned building and designation in the rect is cancelled -- the owner's 'delete that wall'), "
                         "camp_plan (the ground survey: rock per side, the open FRONT where raids come, the mountain BACK, the door lanes kept clear), "
                         "free (everyone walled in gets a way out: a plan cancelled or a wall marked to deconstruct). "
                         "BUILD AND MANAGE: build (def, x, z, rot 0-3, stuff -- any architect thing, e.g. TorchLamp, Sandbags, Barricade, Cooler, "
                         "SimpleResearchBench, Battery; read refused/ok), build_room (x,z inside corner, w, h, stuff -- walls+door+roof), deconstruct "
                         "(def or x,z), harvest (what food|medicine|all -- wild plants), tame (def), slaughter (def, count; never milkers or bonded), "
                         "allow_area (x,z,w,h -- unforbid a rect), self_tend (pawn or all, on), schedule (pawn or all, hours 0-23, assignment Anything|Work|Sleep|Joy), "
                         "drug_policy (pawn or all, policy -- colonists 'No drugs'), research (project defName or label), bed_medical / bed_prisoner (x,z,on), "
                         "cooler_temp (x,z,celsius -- freezer -5). "
                         "MORE: equip (pawn + x,z or def; sidearm true carries it), capture (pawn -- nearest downed enemy to a prisoner bed), "
                         "bill_count (recipe, count -- raise an existing bill's target), zone_create (kind stockpile|growing, x,z,w,h, priority, plant, label), "
                         "roof_area (x,z,w,h, mode roof|noroof|clear), firebreak (w), pen (x,z,w,h -- fence + gate), bury (a grave outside home), "
                         "ideo_role (role leader|moral guide, pawn), save_game (name; always Unity-*), "
                         "terraform (mode bridge|smooth|remove_floor, x,z,w,h -- bridge over water/marsh; smooth or strip floor; map on screen for smooth/remove_floor). "
                         "KITCHEN/DEFENCE: freezer (cooler in a small sealed room, -5 C once built), butcher (butcher table near the food store), kitchen (meal / butcher bill on every built table with none), "
                         "arm (guns on the unarmed, melee sidearms, craft bill for a shortfall), draft (pawn all|names, on true|false), hold (armed colonists to embrasure cells, nearest the threat first), tower (x,z a perimeter corner, size, stuff -- a roofed corner tower, embrasures outward, base door + sally port), power (optional x,z -- one conduit line from each unpowered building to the nearest grid with a generator or battery), hall (x1,z1 to x2,z2, width -- a straight walled, roofed hall), research_next (the next project by the playbook order, else the cheapest; names researched upgrades not built), generator (kind wood|solar|chemfuel -- generator + touching battery outside the colony; then power), prisoner (mode recruit|chat|enslave|convert|release|maintain|interrogate|reducewill, pawn all|name), trade (no args: list traders in reach; with ship|caravan, sell Def:n,.., buy Def:n,.. -- the negotiator walks there first, call again to deal; never spacer tech), gate_posture (posture Mild|Balanced|Strict), guest_beds (no args: list guest beds and fees; fee n sets every guest bed), security_room (x,z the tower corner, size, w, h, stuff -- a room off the tower base door), room_cooler (x,z inside a room, celsius default 21 -- sets its cooler or places one in its wall), call_trader (no args: askable factions and caravan kinds; faction, kind asks one -- negotiator walks to the console; goodwill cost and cooldown are the game's). "
                         "map (optional, e.g. Map_0) picks the map; without it the home map is used. The result comes back from the game: read it.",
                         S({"cmd": {"type": "string", "enum": ["explore", "rooms", "stockpile_room", "stockpile_filter",
                                                               "beds", "shelves", "stove", "crops", "hunt", "day_one", "assign",
                                                               "set_zone_plant", "set_zone_sowing", "set_work_priority",
                                                               "set_bed_owner", "add_bill", "set_area",
                                                               "unforbid", "chop", "shelter", "stockpile_camp", "haul", "cancel", "camp_plan", "free", "dump", "build", "build_room", "deconstruct", "harvest", "tame",
                                                               "slaughter", "allow_area", "self_tend", "schedule", "drug_policy", "research", "bed_medical", "bed_prisoner", "cooler_temp",
                                                               "equip", "capture", "bill_count", "zone_create", "roof_area", "firebreak", "pen", "bury", "ideo_role", "save_game",
                                                               "stockpile_priority", "stockpile_copy", "crew_setup", "terraform",
                                                               "camp", "storage_room", "mine", "room_plan", "wall_swap", "home_area",
                                                               "freezer", "butcher", "kitchen", "arm", "draft", "hold", "tower", "power", "hall", "research_next", "generator", "prisoner", "trade", "gate_posture", "guest_beds", "security_room", "room_cooler", "call_trader"]},
                            "x": i, "z": i, "plant": s, "allow": b, "pawn": s, "work": s, "level": i,
                            "owner": s, "recipe": s, "count": i, "area": s, "room": s, "mode": s, "priority": s, "food": s, "medicine": s, "hostility": s, "map": s, "w": i, "h": i, "def": s, "rot": i, "stuff": s, "what": s, "on": b, "hours": s, "assignment": s, "policy": s, "project": s, "celsius": i, "sidearm": b, "kind": s, "label": s, "role": s, "name": s, "zone": s, "from": s, "to": s, "size": i, "x1": i, "z1": i, "x2": i, "z2": i, "width": i, "with": s, "sell": s, "buy": s, "posture": s, "fee": i, "faction": s},
                          ["cmd"]), self.t_game_set),
            "twitch_chat": ("[STREAM] Type into the REAL Twitch chat (not just out loud). action: say | reply (needs "
                            "viewer) | title | category. Every line is filtered clean or refused.",
                            S({"action": {"type": "string", "enum": ["say", "reply", "title", "category"]},
                               "text": s, "viewer": s}, ["action", "text"]), self.t_twitch),
            "note": ("[SCRATCH] Write or append a note in your own scratch folder (the ONLY place you can write).",
                     S({"name": s, "text": s, "append": b}, ["name", "text"]), self.t_note),
        }

    def t_look(self):
        if self.dry:
            # take_screenshot writes a file in the game's folder, so dry-run reuses the last saved frame instead
            p = os.path.join(QA, "_w.png")
            if os.path.exists(p) and not self.offline:
                self._attach(p)
                return "dry-run: attached the last saved screenshot (.local/qa/_w.png)"
            return "dry-run: no screenshot"
        return self._bridge("rimworld/take_screenshot", {"suppressMessage": True})

    def t_state(self):
        out = {}
        for k, n, a in (("colonists", "rimworld/list_colonists", {}), ("letters", "rimworld/list_letters", {"limit": 15}),
                        ("alerts", "rimworld/list_alerts", {"limit": 20}), ("messages", "rimworld/list_messages", {"limit": 8}),
                        ("ui", "rimworld/get_ui_state", {})):
            r = self.bridge.call(n, a)
            if k == "colonists" and isinstance(r, dict):
                r = [{f: c.get(f) for f in ("pawnId", "name", "mapId", "position", "job", "drafted", "downed", "dead",
                                             "mentalState")} for c in r.get("colonists", [])]
            out[k] = r
        return _trim(out, 7000)

    def t_pawn_check(self, pawn, tab="Needs"):
        if self.dry:
            return "dry-run: would select %s, open the %s tab and look" % (pawn, tab)
        self._bridge("rimworld/select_pawn", {"pawnName": pawn})
        self._bridge("rimworld/open_inspect_tab", {"inspectTabId": tab})
        time.sleep(0.4)
        self.t_look()
        return "selected %s, %s tab open; the screenshot is attached -- read the bars and fix the worst one" % (pawn, tab)

    def t_order_pawn(self, pawn_id, x, z, option=None, queue=False):
        args = [str(pawn_id), str(int(x)), str(int(z))]
        if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", args[0]):
            raise GuardError("pawn_id must be an id like Thing_Human1080")
        key = (args[0], args[1], args[2])
        if option:
            if guards.UI_NEVER.search(option):
                raise GuardError("menu option refused by guard")
            # run 3 (2026-10-13 21:56-21:58): twelve guessed options (Take, Haul, Hunt, Combat, Tend, Rest, Eat, Sleep, Work,
            # Joy, Build, Prioritize) fired as real orders. An option must come from the menu read for that cell first.
            menu = self.last_menu.get(key)
            if menu is None:
                raise GuardError("read the menu first: order_pawn %s %s %s with no option lists what that cell offers; then pick one of those labels" % key)
            want = str(option).strip().lower()
            if not any(m.lower().startswith(want) for m in menu):
                raise GuardError("'%s' is not on that cell's menu; it offers: %s" % (option, "; ".join(menu[:10]) or "nothing"))
            args.append(str(option)[:60])
        if queue:
            args.append("--queue")
        if self.dry:
            log("DRY-RUN would run api-prio.py", args)
            return "dry-run: not executed"
        out = run_script("api_prio", args, timeout=120)
        if not option:
            labels = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith(("no entry", "done:", "STDERR"))]
            self.last_menu[key] = labels
            return ("menu for %s at %s,%s: " % key) + ("; ".join(labels) if labels else "nothing -- that cell offers no order for this pawn")
        return out

    def _time_blocked(self):
        """Why time may not run yet, or None. Every route that advances game time asks this one question
        (pause_game, set_time_speed, play_for, play_until_letter and play_slices alike)."""
        try:
            marks = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "scratch", "ladder.json"), encoding="utf-8")).get("marks", {})
        except Exception:
            marks = {}
        # owner's order: explore every room and door FIRST with time running, THEN pause and set the pawns.
        # So time may run while exploring; once exploring is done it stays stopped until the pawns are set.
        explored = os.path.exists(os.path.join(ROOT, ".local", "qa", "_explore_done.flag"))
        if explored and not (marks.get("pawns_set") and marks.get("assign_set")):
            return ("time stays stopped until every pawn's priorities, schedule, drugs and Assign tab "
                    "are done -- then ladder_set mark pawns_set true and assign_set true, then unpause")
        # Run 5 (2026-10-13 23:20-23:26): day 0 to day 2 at Superfast with nothing laid out -- play_slices "to let the arming
        # land", then "plans are all drawn, time runs". Owner: "pause is her friend should should not unpause until inistal
        # setup and zoneing is done and buildings are layed out" / "she should have beend buildt by the end of day one".
        # A new colony's setup hold (keep-playing writes it at day one) locks every time-starting route until the mod has
        # confirmed the crew (pawns_set, assign_set) and the layout (layout_set: storage_room, shelter AND stove ordered).
        # Hostiles on the map are the one exception: a raid is fought with time running.
        if os.path.exists(os.path.join(ROOT, ".local", "qa", "_setup_hold.flag")):
            try:
                cm = self.confirmed_marks()
            except Exception:
                cm = {}
            missing = [k for k in ("pawns_set", "assign_set", "layout_set") if not cm.get(k)]
            if missing:
                # LIVE readings from RimPLC (the mod's sensors.json is written on game ticks, so while the game is held it
                # is a snapshot from the pause -- run 5, 00:21: hostiles and designations read from a 24-minute-old file)
                live = {}
                try:
                    r = subprocess.run([PY, os.path.join(ROOT, ".local", "qa", "bridge.py"), "call", "rimplc/read_state",
                                        json.dumps({"keys": "hostiles_on_map,designations_mine"})], capture_output=True,
                                       text=True, timeout=30, cwd=ROOT, shell=False)
                    t = r.stdout or ""; i = t.find("{")
                    d = json.loads(t[i:]) if i >= 0 else {}
                    live = d.get("state") if isinstance(d.get("state"), dict) else {}
                except Exception:
                    live = {}
                hostile = live.get("hostiles_on_map") or 0
                # the one setup exception besides a raid: rock inside the pile's box is mined with time running (run 5,
                # 00:21:21: `mine` ok, one cell -- and the lock held time until the layout the rock was blocking)
                mining = (live.get("designations_mine") or 0) > 0 and not cm.get("storage_room_set")
                if not hostile and not mining:
                    return ("the game stays PAUSED until the camp is laid out and the crew is set (owner: pause is your friend; "
                            "the camp stands by the end of day one). Not yet confirmed by the mod: %s. Orders you place now are "
                            "QUEUED and run the moment setup-6-run starts time -- keep laying out. layout_set = the mod's ok to "
                            "storage_room, shelter AND stove; pawns_set = the work grid; assign_set = game_set cmd assign"
                            % ", ".join(missing))
        return None

    def t_play(self, slices=1):
        n = max(1, min(int(slices), 6))
        if self.dry:
            log("DRY-RUN would run play.py", n)
            return "dry-run: not executed"
        why = self._time_blocked()
        if why:
            return "not run: " + why
        # live, 10-10: a "can they stay?" message box froze time and she kept calling play_slices for minutes
        try:
            u = self.bridge.call("rimworld/get_ui_state", {})
            u = u.get("result", u); u = u.get("structuredContent", u) if isinstance(u, dict) else {}
            if u.get("nonImmediateDialogWindowOpen") and u.get("windowsForcePause"):
                return ("not run: a dialog (%s) is open and freezes time -- call game_get_ui_layout, read its buttons, "
                        "and click one with click_ui_target first" % (u.get("topWindowType") or "message box"))
        except Exception:
            pass
        return run_script("play", [n], timeout=60 + 40 * n)

    def t_run_list(self):
        if self.dry:
            log("DRY-RUN would run run-list.py")
            return "dry-run: run-list.py not executed (it changes the selection); pretend the first FIX is the top goal in .claude/.stream-goals.json"
        return run_script("run_list", [], timeout=240)

    EMPIRE_COOLDOWN_S = 600

    def t_empire(self, report_only=False):
        if self.dry:
            log("DRY-RUN would run empire.py", "--dry" if report_only else "")
            return "dry-run: not executed"
        # test run 2026-10-13 19:02 / 19:18 / 19:23: three passes at ~70 s each re-issued jobs already in progress and
        # read "Still unarmed" over the mod's "3 armed". The pass clicks the procurement and assign UI, so it is also
        # never run while the owner's hands are on the game.
        if not report_only:
            # run 4 (2026-10-13 22:40): the pass marked six animals to hunt on day 0 with no butcher table, no camp -- it is
            # maintenance for a standing colony, never a setup tool (and never a hunting tool before meat can be processed)
            try:
                r = subprocess.run([PY, os.path.join(ROOT, ".local", "qa", "bridge.py"), "call", "rimplc/read_state",
                                    json.dumps({"keys": "butcher_tables,stoves"})], capture_output=True, text=True, timeout=30, cwd=ROOT, shell=False)
                t = r.stdout or ""; i = t.find("{"); d = json.loads(t[i:]) if i >= 0 else {}
                stt = d.get("state") if isinstance(d.get("state"), dict) else {}
                if (stt.get("butcher_tables") or 0) < 1:
                    return ("refused: empire_pass is maintenance for a standing colony -- no butcher table yet, so it would only mark animals "
                            "to hunt that nobody can process. Camp first: camp, stockpile_camp, storage_room, shelter, stove, butcher. "
                            "Self-tend and hostility are set by game_set cmd assign (self-tend on, Attack) and game_set cmd self_tend.")
            except Exception:
                pass
            import gates
            if gates.host_inputs().get("owner_input_active"):
                return "refused: the owner is at the controls (owner_input_active) -- empire_pass clicks the game UI; a quiet turn until the rung drops"
            age = time.time() - self._empire_at
            if age < self.EMPIRE_COOLDOWN_S:
                return ("refused: empire_pass ran %d s ago and its jobs are still being worked -- not again for %d s; read the sensors "
                        "(able_shooters_armed, unarmed_colonists, needs_tend_count, designations_hunt) and the ladder instead. Its last report:\n%s"
                        % (age, self.EMPIRE_COOLDOWN_S - age, self._empire_report or "-"))
        out = run_script("empire", ["--dry"] if report_only else [], timeout=300)
        if not report_only:
            self._empire_at, self._empire_report = time.time(), out[-2500:]
        return out

    # -- stream output: every path goes through guards.clean_for_stream -----------------------------------------
    def _speak(self, text, reply_to=None, emotion=None, act=None):
        """The stream-safe line once it has PLAYED; None when the filter blocked it; a 'CUT: ...' / 'REPEAT: ...' /
        'SPEAK FAILED: ...' string when it was not said (the brain reads that string and acts on it)."""
        # Voice tags ([laughter], [breath], [sigh]) are instructions for Unity's own voice model, never words for
        # Twitch chat or the overlay. Owner: "its better not print [laughter} in the chat of twitch". They are cut
        # from everything shown; voice_text keeps them for the new voice (today's Piper would read them out loud,
        # so it also gets the stripped line until the own voice is live).
        self.voice_text = text
        text = re.sub(r"\s*\[(laughter|breath|sigh)\]\s*", " ", text, flags=re.I).strip()
        # 2026-10-13 19:43: "Give me a minute, I cannot do anything until" went out on stream, cut. The text arrived
        # from the brain already ending there (the TOOL log line shows it), and the next two turns copied the same
        # cut call out of the conversation. A line that stops on a word no sentence ends on is handed back unsaid.
        tail = re.sub(r"[\"'’”)\]]+$", "", text.rstrip())
        last = re.findall(r"[A-Za-z']+$", tail)
        if last and last[0].lower() in _DANGLING and not re.search(r"[.!?]$", tail):
            return "CUT: your line stops mid-sentence at '...%s' -- finish the sentence and say it again" % text[-40:]
        clean = guards.clean_for_stream(text)
        if not clean:
            log("STREAM FILTER blocked:", repr(text)[:200])
            return None
        gap = time.time() - self.last_speech
        if gap < 3.0:
            time.sleep(3.0 - gap)
        self.last_speech = time.time()
        if self.dry:
            log("DRY-RUN would SAY:", clean, "(reply to %s)" % reply_to if reply_to else "")
            self.spoken.append(clean)
            return clean
        # the chat row is posted by unity-speak the moment this line starts playing (owner: "she is still sending like
        # 3-4 messages at once"); posting here ran chat ahead of her voice
        if reply_to is None:
            # a picture with every narrated line (owner: "make some images more offten like as much as you talk")
            subprocess.Popen([PY, SCRIPTS["glance"], clean], cwd=ROOT, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, shell=False)
        # Owner: "but she still has to laugh when it comes through". Chat and overlay get the clean line; the voice
        # gets the tagged line (same words, already passed the stream filter) once her own voice is live
        # (UNITY_OWN_VOICE=1), so the laugh is heard, never read. (Piper is retired; her own voice is the only voice.)
        voice_line = self.voice_text if os.environ.get("UNITY_OWN_VOICE") == "1" else clean
        # her own voice takes the delivery the brain chose (the same trained emotions/acts as the tool enums)
        # the emotion and act are exactly what she chose in the say/reply_chat call (owner 2026-10-13: "not edit her fucking outputs")
        speak_env = dict(os.environ, UNITY_SPEAK_EMOTION=emotion or "", UNITY_SPEAK_ACT=act or "",
                         UNITY_SPEAK_CHAT=clean, UNITY_SPEAK_REPLY_TO=str(reply_to) if reply_to is not None else "")
        # Owner: "she need training on how not to over respond. waiting for vocie to play out becasue the last
        # stream at time see was speaking over herself sending messages before the last finished". Speaking BLOCKS:
        # the tool returns only after the line has finished playing (unity-speak holds its turn for the whole
        # line), so her next line can never start or show in chat before this one is done.
        started = time.time()
        try:
            r = subprocess.run([PY, SCRIPTS["speak"], voice_line], cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True, shell=False, timeout=300, env=speak_env)
            failed = None
            if r.returncode != 0:
                failed = (r.stderr or "").strip()[-200:] or ("exit %d" % r.returncode)
        except subprocess.TimeoutExpired:
            failed = "timed out after 300 s"
        self.last_speech = time.time()
        self.last_spoken_seconds = round(self.last_speech - started, 1)
        if failed:
            # 2026-10-13 19:07-19:16: three refused lines were each logged SAID and returned as said, so the brain
            # believed the stream heard them. A failed line is logged ONCE as a failure and handed back as one;
            # unity-speak answers "REPEAT: ..." for a line the stream already heard, and the brain rephrases.
            if failed.startswith("REPEAT:"):
                log("SPEAK REFUSED:", failed)
                return failed
            log("SPEAK FAILED (no fallback voice):", failed)
            return "SPEAK FAILED: " + failed + " -- nothing was heard on stream"
        self.spoken.append(clean)
        log("SAID:", clean)
        return clean

    def t_reply_owner(self, msg_id, text):
        line = re.sub(r"\s*\[(laughter|breath|sigh)\]\s*", " ", str(text)).strip()
        if not line:
            return "nothing to send"
        # run 5 (2026-10-14 00:57-00:58): replies to msg_id 146 and 147 with an inbox that ends at 49 -- invented ids answer
        # nobody and the unread line stays unread. 0 = the owner-orders file (Twitch-chat / panel orders); else a real inbox id.
        try:
            ids = {r["msg_id"] for r in read_owner(0)}
        except Exception:
            ids = set()
        if int(msg_id) != 0 and int(msg_id) not in ids:
            raise GuardError("no owner message with msg_id %s: the private lines are %s (use their msg_id), or msg_id 0 for an order from the OWNER ORDERS list"
                             % (msg_id, sorted(ids)[-6:] if ids else "none"))
        if self.dry:
            log("DRY-RUN would REPLY TO OWNER:", line)
        else:
            _outbox(line, int(msg_id))          # replyTo = the owner's message: the stream feed never shows it
        # the acknowledgement of the owner-orders FILE too (Twitch-chat orders land there, not in the studio inbox):
        # host_inputs() counts the file as unread until a reply_owner follows its last growth (run 5, 00:26-00:40:
        # four owner orders sat unanswered while the owner-message rung read 0)
        try:
            n = os.path.getsize(os.path.join(HERE, "owner-orders.txt"))
            json.dump({"len": n, "ts": time.time()}, open(os.path.join(HERE, "scratch", "_orders_ack.json"), "w"))
        except OSError:
            pass
        log("TO OWNER:", line[:200])
        return "sent privately to the owner"

    def t_say(self, text, emotion=None, act=None):
        said = self._speak(text, emotion=emotion, act=act)
        if _not_said(said):
            return said
        return ("said: " + said) if said else "BLOCKED by the stream filter (no swearing, no degrading, no emoji); say it cleaner"

    def t_reply(self, chat_id, viewer, text, emotion=None, act=None):
        name = guards.clean_viewer_name(viewer)
        if name and name.lower().split()[0] not in text.lower():
            text = name + ", " + text
        said = self._speak(text, reply_to=int(chat_id), emotion=emotion, act=act)
        if _not_said(said):
            return said
        if said:
            self.greeted_this_tick.add(str(viewer).lower())
            if not self.dry:
                try: run_script("twitch", ["reply", name or str(viewer), said], timeout=60)
                except Exception as e: log("twitch reply failed:", str(e)[:80])
        return ("replied: " + said) if said else "BLOCKED by the stream filter; reply cleaner"

    # names she reaches for that the game does not use (live: "Medicine", "Harvesting", "Medical", "Firefighting")
    WORK_ALIASES = {"medicine": "Doctor", "medical": "Doctor", "doctoring": "Doctor", "firefighting": "Firefighter",
                    "harvesting": "PlantCutting", "plantcut": "PlantCutting", "cutting": "PlantCutting", "farming": "Growing",
                    "plants": "Growing", "cook": "Cooking", "handle": "Handling", "animals": "Handling",
                    "construct": "Construction", "building": "Construction", "mine": "Mining", "haul": "Hauling",
                    "clean": "Cleaning", "craft": "Crafting", "smith": "Smithing", "tailor": "Tailoring",
                    "research": "Research", "rest": "PatientBedRest", "bedrest": "PatientBedRest", "basic": "BasicWorker"}
    ORDER = ["Firefighter", "Patient", "Doctor", "PatientBedRest", "BasicWorker", "Warden", "Handling", "Cooking",
             "Hunting", "Construction", "Growing", "Mining", "PlantCutting", "Smithing", "Tailoring", "Art", "Crafting",
             "Hauling", "Cleaning", "Research"]

    def _work_name(self, w):
        w = str(w or "").strip()
        exact = next((o for o in self.ORDER if o.lower() == w.lower()), None)
        return exact or self.WORK_ALIASES.get(w.lower().replace(" ", ""), w)

    def _ladder_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "ladder.json")

    def _gates(self):
        """gates.py, loaded once: the Python ladder engine and the RimPLC thin client (one RimPLC retry timer)."""
        if getattr(self, "_gates_mod", None) is None:
            spec = importlib.util.spec_from_file_location("gates_rt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gates.py"))
            g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
            self._gates_mod = g
        return self._gates_mod

    def _rimplc_call(self):
        return None if self.bridge.offline else self.bridge.call

    def t_ladder(self):
        # RimPLC in the game when it is loaded (rimplc/read_ladder, or its command file), else the Python engine.
        # Either way the top live rungs with the measured values that made them fire, so she can say WHY, in the
        # same fields as always (gates.ladder_result / format_ladder).
        # the start kind the GO chose (keep-playing writes .local/qa/_start_kind) goes into RimPLC's marks, so the
        # start-crashlanded rung can fire in the game's own engine too (2026-10-13 audit: nothing ever set it)
        try:
            sk = int(open(os.path.join(ROOT, ".local", "qa", "_start_kind"), encoding="utf-8").read().strip() or 0)
            if sk and not self.dry and getattr(self, "_start_kind_sent", None) != sk:
                self._gates().rimplc("set_mark", {"name": "start_kind", "value": sk}, call=self._rimplc_call())
                self._start_kind_sent = sk
        except (OSError, ValueError):
            pass
        if not self.dry:
            self._gates().push_host()       # remote I/O: chat, voice, dead air, owner at the controls
        text, _src = self._gates().ladder_result(call=self._rimplc_call())
        try:   # the live top rung's meta prompt rides along (rung-prompts.json)
            rp = json.load(open(os.path.join(HERE, "rung-prompts.json"), encoding="utf-8"))
            top = next((i for i in re.findall(r'"id":\s*"([^"]+)"', text) if i in rp), None)
            if top:
                text += chr(10) + chr(10) + "HOW TO DO [%s] NOW:" % top + chr(10) + rp[top]
        except (OSError, ValueError):
            pass
        return text

    def _book(self):
        return self._book_static()

    @staticmethod
    def _book_static():
        try:
            return json.load(open(os.path.join(ROOT, "docs", "playbook.gates.json"), encoding="utf-8"))
        except Exception:
            return {}

    RIMPLC_OPS = {"mark": "set_mark", "tag": "set_tag", "add_rung": "upsert_rung", "remove_rung": "remove_rung"}

    # ---- the setup gate is MOD-CONFIRMED, never her say-so (test run 2026-10-13, 19:30 row: "the ladder does not
    # know we are crashed, so I am telling it" -> ladder_set mark setup_crashlanded true -> "Setup is done, time runs
    # now", with no stove, no bill, no priorities set). A mark named setup_* / *_set / *_done that a rung of the
    # setup, start or configuration family reads is not hers to write: ladder_set routes it to the mod's own
    # reading (sensors.json from the mod's Sensors.cs via gates.state(), and the mod's ok: replies in
    # RimroomsAutomation/outbox.jsonl since this colony started). The value written is always the measured one.
    SETUP_FAMILIES = ("setup", "start", "configuration")
    SETUP_MARK_RE = re.compile(r"^(setup_.*|.*_set|.*_done|.*_hauled|.*_built|.*_placed)$")   # run 5: "supplies_hauled" set by hand after a missing command
    # mark -> (the mod replies that confirm it: game_set cmds answered "ok", AND/OR the sensor test), with the source
    # named for the refusal text. A mark with no entry and a setup_* name has no reading at all and is refused.
    CONFIRMED_MARKS = {
        "pawns_set": ("grid_matches_plan", None,
                      "the mod's pawn work grid (sensors.json, Sensors.cs) -> grid_matches_plan"),
        "assign_set": (None, ("assign", "day_one", "crew_setup"),
                       "an ok: reply to game_set cmd assign (or day_one / crew_setup) in the mod's outbox"),
        "config_assign_tab_done": (None, ("assign", "day_one", "crew_setup"),
                                   "an ok: reply to game_set cmd assign (or day_one / crew_setup) in the mod's outbox"),
        "config_schedule_anything_done": (None, ("schedule", "day_one"),
                                          "an ok: reply to game_set cmd schedule (or day_one) in the mod's outbox"),
        "config_drug_policy_done": (None, ("drug_policy", "day_one"),
                                    "an ok: reply to game_set cmd drug_policy (or day_one) in the mod's outbox"),
        # run 5 (2026-10-13 23:21): armed-by-sensor needs the equip jobs to RUN, and time is stopped during setup -- so she ran
        # time to get the mark (owner: "pause is her friend"). The mod's ok to `arm` queues the orders; that confirms it.
        "arms_set": ("armed", ("arm",), "the mod's able_shooters_armed == able_shooters > 0 (Sensors.cs), or an ok: reply to game_set cmd arm (the equip orders are queued and run when time runs)"),
        # the camp is LAID OUT: the mod's ok to ALL THREE of storage_room, shelter and stove (plans, not buildings). This is the
        # mark that lets time run (setup-6-run) -- owner: "should not unpause until inistal setup and zoneing is done and buildings are layed out"
        # run 5 (2026-10-14 01:21): `stove` refuses until a room STANDS ("no finished roofed room ... do not call stove again
        # until then"), and standing needs time, and time needed the stove's ok -- a deadlock. The layout is the two rooms
        # laid out; the stove follows once a room stands (setup-5-stove, after setup-6-run).
        "layout_set": (None, ("storage_room", "shelter"), "ok: replies to BOTH storage_room and shelter in the mod's outbox (the camp is laid out; the crew builds it once time runs; the stove comes when a room stands)"),
        "supplies_hauled": (None, ("haul",), "an ok: reply to game_set cmd haul (the pile unforbidden, Hauling at 1 for everyone)"),
        "food_indoors": (None, ("stockpile_room",), "an ok: reply to game_set cmd stockpile_room mode food (the Food store under the roof; owner, run 5: food rotting outside)"),
        "chop_set": (None, ("chop",), "an ok: reply to game_set cmd chop (trees marked; the rung counted designations and chopped the same trees every turn -- run 5)"),
        "shelter_set": (None, ("shelter",),
                        "an ok: reply to game_set cmd shelter (or build_room) in the mod's outbox"),
        "camp_set": (None, ("camp",), "an ok: reply to game_set cmd camp (the anchor read) in the mod's outbox"),
        "storage_room_set": (None, ("storage_room",), "an ok: reply to game_set cmd storage_room (walls, door and roof planned) in the mod's outbox"),
        "stove_set": ("stove_and_bill", ("stove", "add_bill"),
                      "the mod's stoves >= 1 and bill_rows > 0 (Sensors.cs), or ok: replies to both stove and add_bill"),
        "ideo_roles_set": ("ideo_roles", ("ideo_role",),
                           "the mod's ideo_leader_assigned true and ideo_roles_unassigned 0, or an ok: reply to ideo_role"),
        "start_opening_done": ("opening", None,
                               "unforbid answered ok: plus the confirmed assign_set and pawns_set"),
        "setup_done": ("setup_all", None,
                       "the confirmed pawns_set, assign_set and stove_set plus a food store on the map"),
        "explore_done": ("explore_flag", ("explore",),
                         ".local/qa/_explore_done.flag (written when exploring finds nothing left)"),
    }

    @classmethod
    def setup_gate_marks(cls, book=None):
        """Every mark name matching setup_* / *_set / *_done that a setup-, start- or configuration-family rung of
        the book reads, plus the routed names above. These are the marks she may not set herself."""
        names = set(cls.CONFIRMED_MARKS)
        try:
            book = book or json.load(open(os.path.join(ROOT, "docs", "playbook.gates.json"), encoding="utf-8"))
            for g in book.get("gates") or []:
                if g.get("family") not in cls.SETUP_FAMILIES:
                    continue
                for k in re.findall(r'"mark_([a-z0-9_]+)"', json.dumps(g.get("when") or {})):
                    if cls.SETUP_MARK_RE.match(k):
                        names.add(k)
        except Exception:
            pass
        return names

    @staticmethod
    def _outbox_ok_cmds(since_offset=None):
        """The game_set cmds the mod answered 'ok' since this colony started (scratch/colony-epoch.json offset into
        RimroomsAutomation/outbox.jsonl; no epoch = the whole file). Rows look like
        {"result": "{'id': 'x-0', 'cmd': 'stove'} -> ok: ...", "id": "x-0"}."""
        if since_offset is None:
            since_offset = colony_epoch().get("outbox_offset", 0)
            # the epoch lands at the END of the day_one row (written as the file length right after the reply), so the
            # day_one ok -- the route for priorities, schedule, drugs, assign -- was never in this colony's set (run 5,
            # 01:02:44: a correct priorities tick refused, every pawn's grid about to be redone). Start at that row.
            d1 = last_day_one_offset()
            if d1 and d1 < since_offset:
                since_offset = d1
        ok = set()
        try:
            if not os.path.exists(AUTOMATION_OUTBOX):
                return ok
            with open(AUTOMATION_OUTBOX, encoding="utf-8", errors="replace") as f:
                if os.path.getsize(AUTOMATION_OUTBOX) >= since_offset:
                    f.seek(since_offset)
                for row in f.read().splitlines():
                    try:
                        res = str(json.loads(row).get("result", ""))
                    except Exception:
                        continue
                    m = re.search(r"'cmd':\s*'([a-z_]+)'.*?->\s*ok\b", res)
                    if m:
                        ok.add(m.group(1))
        except OSError:
            pass
        return ok

    @classmethod
    def confirmed_marks(cls, st=None, ok_cmds=None):
        """name -> True/False for every routed setup mark, from the mod's readings only. st is gates.state() (or any
        dict of measured keys); None reads the live state."""
        if st is None:
            try:
                spec = importlib.util.spec_from_file_location("gates_cm", os.path.join(HERE, "gates.py"))
                g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
                st = g.state()
            except Exception:
                st = {}
        ok = cls._outbox_ok_cmds() if ok_cmds is None else set(ok_cmds)
        # gates.state() carries the autopilot's own readings; the keys these tests need are RimPLC's (Sensors.cs) and
        # some never reach it (run 3, 21:47: able_shooters_armed was None here while the mod read 3, so arms_set could
        # never be confirmed and every setup rung behind it stayed dead). Fill what is missing from the mod itself.
        need = [k for k in ("able_shooters", "able_shooters_armed", "stoves", "bill_rows", "ideo_leader_assigned",
                            "ideo_roles_unassigned", "grid_matches_plan", "food_store") if st.get(k) is None]
        if need:
            try:
                r = subprocess.run([PY, os.path.join(ROOT, ".local", "qa", "bridge.py"), "call", "rimplc/read_state",
                                    json.dumps({"keys": ",".join(need)})], capture_output=True, text=True, timeout=30,
                                   cwd=ROOT, shell=False)
                t = r.stdout or ""; i = t.find("{")
                d = json.loads(t[i:]) if i >= 0 else {}
                src = d.get("state") if isinstance(d.get("state"), dict) else {}
                for k in need:
                    if k in src: st[k] = src[k]
            except Exception:
                pass
        def num(k):
            v = st.get(k)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        out = {}
        def sensor(test):
            if test == "grid_matches_plan":
                return st.get("grid_matches_plan") is True
            if test == "armed":
                a, b = num("able_shooters"), num("able_shooters_armed")
                return a is not None and b is not None and a > 0 and b >= a
            if test == "stove_and_bill":
                s, b = num("stoves"), num("bill_rows")
                return s is not None and b is not None and s >= 1 and b > 0
            if test == "ideo_roles":
                return st.get("ideo_leader_assigned") is True and num("ideo_roles_unassigned") == 0
            if test == "explore_flag":
                return os.path.exists(os.path.join(ROOT, ".local", "qa", "_explore_done.flag"))
            if test == "opening":
                return "unforbid" in ok and out.get("assign_set", False) and out.get("pawns_set", False)
            if test == "setup_all":
                return (out.get("pawns_set", False) and out.get("assign_set", False) and out.get("stove_set", False)
                        and st.get("food_store") is True)
            return False
        # dependencies (opening, setup_all) read earlier entries: plain marks first, composites last
        order = [k for k, v in cls.CONFIRMED_MARKS.items() if v[0] not in ("opening", "setup_all")] + ["start_opening_done", "setup_done"]
        for name in order:
            test, cmds, _src = cls.CONFIRMED_MARKS[name]
            by_sensor = sensor(test) if test else False
            by_reply = bool(cmds) and (all(c in ok for c in cmds) if name in ("stove_set", "layout_set") else any(c in ok for c in cmds))
            out[name] = bool(by_sensor or by_reply)
        return out

    @classmethod
    def scrub_setup_marks(cls):
        """Drop every setup-gate mark from scratch/ladder.json that the mod does not confirm (a new colony, or a
        restart). Returns the names removed. The confirmed ones are rewritten with the measured value."""
        path = os.path.join(HERE, "scratch", "ladder.json")
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            return []
        marks = d.get("marks") or {}
        if not marks:
            return []
        blocked = cls.setup_gate_marks()
        confirmed = cls.confirmed_marks()
        gone = []
        for k in list(marks):
            if k in blocked or cls.SETUP_MARK_RE.match(k) and k.startswith("setup_"):
                if confirmed.get(k):
                    marks[k] = True
                else:
                    del marks[k]; gone.append(k)
        if gone:
            d["marks"] = marks
            guards.scratch_write("ladder.json", json.dumps(d, indent=1))
        return gone

    def _route_setup_mark(self, name, value):
        """A setup-gate mark: the value written is the mod's, and a request that disagrees with it is refused with
        what the mod reads and what is still missing."""
        want = value if isinstance(value, bool) else str(value if value is not None else "").strip().lower() in ("true", "yes", "done", "on", "1")
        if name not in self.CONFIRMED_MARKS:
            raise GuardError("mark %s is not yours to set: no reading of the mod backs it, so the ladder will never "
                             "take it from you. The start kind is already measured (mark start_kind from the GO); do "
                             "the live rung's steps and let the mod confirm them" % name)
        test, cmds, src = self.CONFIRMED_MARKS[name]
        measured = self.confirmed_marks().get(name, False)
        if measured != want:
            raise GuardError("mark %s stays %s: it is read from %s, not from you. %s" % (
                name, "true" if measured else "false", src,
                "Do the rung's steps with the real tools and read the mod's reply; the mark follows by itself."
                if want else "The mod confirms it, so it stays true."))
        return measured

    def t_ladder_set(self, op, name=None, value=None, rung=None):
        """ladder_set: through RimPLC when it is loaded (mark -> set_mark, tag -> set_tag, add_rung -> upsert_rung,
        remove_rung -> remove_rung), mirrored into scratch/ladder.json so the Python fallback keeps her edits; else
        straight into scratch/ladder.json. Same result text and refusals either way.
        A setup-gate mark (setup_gate_marks: pawns_set, assign_set, stove_set, setup_done, setup_* ...) is routed to
        the mod's own reading first: she cannot write a value the mod does not confirm."""
        if op == "mark" and (str(name or "") in self.setup_gate_marks() or str(name or "").startswith("setup_")):
            value = self._route_setup_mark(str(name), value)
        cmd = self.RIMPLC_OPS.get(op)
        if cmd and not self.dry:
            args = {"set_mark": {"name": name, "value": value}, "set_tag": {"name": name, "value": value},
                    "upsert_rung": {"rung": rung}, "remove_rung": {"id": name}}[cmd]
            r = self._gates().rimplc(cmd, args, call=self._rimplc_call())
            if r is not None:
                if not r.get("ok"):
                    raise GuardError(r.get("refused") or "refused by RimPLC")
                try:
                    self._ladder_set_local(op, name, value, json.loads(json.dumps(rung)) if rung is not None else None)
                except GuardError:
                    pass
                note = r.get("note")
                return str(r.get("result", "ladder updated: " + op)) + ((" " + note) if note else "")
        return self._ladder_set_local(op, name, value, rung)

    def _ladder_set_local(self, op, name=None, value=None, rung=None):
        path = self._ladder_path()
        try: d = json.load(open(path, encoding="utf-8"))
        except Exception: d = {}
        note = ""
        if op == "mark":
            if not re.fullmatch(r"[a-z0-9_]{1,40}", str(name or "")): raise GuardError("mark name: lowercase_with_underscores")
            # numeric marks stay numbers (title_rank 4, gate_sections_done 3); everything else is true/false
            if isinstance(value, bool): v = value
            elif isinstance(value, (int, float)): v = value
            else:
                sv = str(value if value is not None else "").strip().lower()
                if re.fullmatch(r"-?\d+", sv): v = int(sv)
                elif re.fullmatch(r"-?\d+\.\d+", sv): v = float(sv)
                else: v = sv in ("true", "yes", "done", "on")
            d.setdefault("marks", {})[name] = v
        elif op == "tag":
            if not re.fullmatch(r"[A-Z0-9_]{1,40}", str(name or "")): raise GuardError("tag name: UPPER_CASE")
            tg = self._book().get("tags") or {}
            if name in (tg.get("constants") or {}):
                raise GuardError("%s is a constant: a safety limit only the owner changes" % name)
            spec = (tg.get("variables") or {}).get(name)
            if spec is None:
                raise GuardError("%s is not a variable on the ladder" % name)
            try: value = float(value) if not isinstance(value, (int, float)) or isinstance(value, bool) else value
            except (TypeError, ValueError): raise GuardError("tag value must be a number")
            lo, hi = spec.get("min"), spec.get("max")
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                note = " (clamped to %s..%s when read)" % (lo, hi)
            d.setdefault("tags", {})[name] = value
        elif op == "add_rung":
            r = rung or {}
            if not (isinstance(r, dict) and r.get("id") and isinstance(r.get("priority"), (int, float)) and isinstance(r.get("when"), dict)):
                raise GuardError("rung needs id, priority (number), when (object), then (list)")
            r["id"] = "unity-" + re.sub(r"[^a-z0-9-]", "-", str(r["id"]).lower())[:40] if not str(r["id"]).startswith("unity-") else str(r["id"])[:46]
            r["then"] = [str(x)[:300] for x in (r.get("then") or [])][:8]
            if "latch" in r: r["latch"] = bool(r["latch"])
            # THE STREAM IS CLEAN: a notice is shown in the game (RimPLC does the same check with its port of the filter)
            if r.get("notice") is not None and guards.clean_for_stream(str(r["notice"])) is None:
                raise GuardError("notice is not clean for the stream: reword it")
            bk = self._book()
            known = set((bk.get("sensors") or {}).keys()) | set(((bk.get("tags") or {}).get("variables") or {}).keys()) \
                | set(((bk.get("tags") or {}).get("constants") or {}).keys()) | {"letter_matches"}
            unknown = [k for k, _w in self._gates().leaves(r["when"]) if not k.startswith(("mark_", "alert_")) and k not in known]
            if unknown: note = " (keys with no sensor, the rung stays quiet until measured: %s)" % ", ".join(unknown)
            d["gates"] = [g for g in d.get("gates", []) if g.get("id") != r["id"]] + [r]
        elif op == "remove_rung":
            d["gates"] = [g for g in d.get("gates", []) if g.get("id") != name]
        else:
            raise GuardError("op must be mark, tag, add_rung or remove_rung")
        guards.scratch_write("ladder.json", json.dumps(d, indent=1))
        return "ladder updated: " + op + " " + str(name or (rung or {}).get("id", "")) + note

    def t_pawn_priorities(self, pawn, custom=None):
        """Owner: "set up all priorities ... for every one using coopy paste to paste one to the tosthers then
        customize keep all the 1s firsefiring through cooking" / "dint leave a bunch blankk". One step per pawn."""
        if not re.fullmatch(r"[A-Za-z0-9_ .-]{1,40}", str(pawn or "")):
            raise GuardError("bad pawn name")
        grid = {}
        for w in self.ORDER[:self.ORDER.index("Cooking") + 1]:
            grid[w] = 1
        for w, lvl in (custom or {}).items():
            name = self._work_name(w)
            try: lvl = max(0, min(4, int(lvl)))
            except Exception: continue
            grid[name] = lvl
        for w in self.ORDER:                    # nothing left blank
            grid.setdefault(w, 3)
        if self.dry:
            return "dry-run: " + json.dumps(grid)
        cmds = [{"cmd": "set_work_priority", "pawn": str(pawn), "work": w, "level": str(l)} for w, l in grid.items()]
        # one batch through the shared client: each result is matched to its own command by id
        aspec = importlib.util.spec_from_file_location("automate_rt", os.path.join(QA, "automate.py"))
        am = importlib.util.module_from_spec(aspec); aspec.loader.exec_module(am)
        out = am.exchange(cmds, wait_s=30)
        lines = cmds
        ok = sum(1 for _c, r in out if r is not None and r.startswith("ok"))
        bad = ["%s: %s" % (c["work"], (r or "no result")[:70]) for c, r in out if r is None or not r.startswith("ok")]
        return "%s: %d/%d work types set (1s Firefighter..Cooking, rest as given, none blank)%s" % (
            pawn, ok, len(lines), ("; refused: " + " | ".join(bad[:3])) if bad else "")

    def _mark_letters_seen(self):
        """She has looked at the letters: the ones on screen now are handled for the ladder (gates.py)."""
        try:
            r = self.bridge.call("rimworld/list_letters", {})
            r = r.get("result", r); r = r.get("structuredContent", r) if isinstance(r, dict) else {}
            ids = [l.get("id") for l in r.get("letters", []) if l.get("id")]
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "ladder.json")
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                d = {"marks": {}}
            d["letters_seen"] = sorted(set(d.get("letters_seen", [])) | set(ids))
            json.dump(d, open(p, "w", encoding="utf-8"), indent=1)
        except Exception:
            pass
        try:
            # RimPLC keeps its own seen-letter set (the `letters` count): tell it too when it is loaded
            self._gates().rimplc("letters_seen", {}, call=self._rimplc_call(), wait_s=1.0)
        except Exception:
            pass

    FILLER_CMDS = ("hunt", "explore")

    @staticmethod
    def _storage_room_box():
        """(x, z, w, h) of the storage room the mod last planned this colony, from its own ok reply ("inside 14x6 from
        126,142"), or None."""
        try:
            with open(AUTOMATION_OUTBOX, "rb") as f:
                f.seek(last_day_one_offset())
                text = f.read().decode("utf-8", "replace")
            m = None
            for m in re.finditer(r"'cmd': 'storage_room'[^\n]*?-> ok:[^\n]*?inside (\d+)x(\d+) from (\d+),(\d+)", text):
                pass
            if not m:
                return None
            w, h, x, z = (int(m.group(i)) for i in (1, 2, 3, 4))
            return (x, z, w, h)
        except Exception:
            return None

    def t_game_set(self, cmd, **kw):
        # run 3 (2026-10-13 21:50): "the rung is not my own, so I do what the colony needs right now. Hunting is the job now"
        # -- with fire-in-camp (2.0) live. Filler is refused while a survival or war rung is on top.
        top = getattr(self, "live_top", None)
        if cmd in self.FILLER_CMDS and top and top[1] in ("survival", "war") and top[2] < 3.0:
            raise GuardError("%s is filler: the live top rung is [%s] (%s %.2f) -- do that rung's steps, nothing else" % (cmd, top[0], top[1], top[2]))
        """Owner, 2026-10-10: "fix that so it doesnt ever need the screen and MY DAMN MOUSE" / "build it into
        the mod if you have to". The component reads a command file once a second; the result is written back."""
        payload = {"cmd": cmd}
        for k, v in kw.items():
            if v is None or v == "": continue
            if k in ("pawn", "work", "owner", "area", "plant", "recipe", "room", "mode", "priority", "food", "medicine", "hostility", "map", "def", "stuff", "what", "hours", "assignment", "policy", "project", "kind", "label", "role", "name", "zone", "from", "to") and not re.fullmatch(r"[A-Za-z0-9_ .-]{1,60}", str(v)):
                raise GuardError("bad value for " + k)
            payload[k] = v
        if cmd == "set_work_priority" and not (0 <= int(payload.get("level", -1)) <= 4):
            raise GuardError("level must be 0-4")
        if cmd in ("shelves", "beds", "stove", "butcher", "build_room", "stockpile_room", "set_zone_plant", "crops", "shelter",
                   "build", "zone_create", "home_area", "wall_swap") and str(kw.get("x", "")) != "" and str(kw.get("z", "")) != "":
            # run 5 (00:39): potatoes at 169,175 and shelves at 157,136 -- thirty cells from the camp, in the mountain
            box = self._storage_room_box()
            if box:
                bx, bz, bw, bh = box
                cx, cz = bx + bw // 2, bz + bh // 2
                try: dx, dz = abs(int(float(kw["x"])) - cx), abs(int(float(kw["z"])) - cz)
                except (TypeError, ValueError): dx = dz = 0
                if dx > 25 or dz > 25:
                    raise GuardError("%s at %s,%s is %d cells from the camp: the camp is the storage room planned at %d,%d (%dx%d). Everything "
                                     "of the camp goes within 25 cells of it, on the open ground beside the room -- give x,z near %d,%d or let "
                                     "the command place it (no x,z)." % (cmd, kw["x"], kw["z"], max(dx, dz), bx, bz, bw, bh, cx, cz))
        if cmd == "camp" and str(kw.get("x", "")) != "" and str(kw.get("z", "")) != "":
            # run 5 (2026-10-14 00:29-00:35): `camp x z` became her escape hatch -- the anchor walked to 150,176, thirty
            # cells from the planned storage room and into the rock, and every shelter was refused around it. Once the
            # room is planned the room IS the camp: the anchor stays within 14 cells of it.
            box = self._storage_room_box()
            if box:
                bx, bz, bw, bh = box
                cx, cz = bx + bw // 2, bz + bh // 2
                try: dx, dz = abs(int(float(kw["x"])) - cx), abs(int(float(kw["z"])) - cz)
                except (TypeError, ValueError): dx = dz = 0
                if dx > 14 or dz > 14:
                    raise GuardError("the camp IS the storage room planned at %d,%d (%dx%d): the anchor stays within 14 cells of it; the "
                                     "shelter and the stove go on the open ground beside the room, never in the mountain. Use game_set cmd "
                                     "camp x %d z %d (the room's centre) and build from there." % (bx, bz, bw, bh, cx, cz))
        if self.dry:
            log("DRY-RUN would game_set", payload)
            return "dry-run: not executed"
        # every value goes as a quoted string: the mod's flat reader swallowed the rest of the line after a bare
        # number ('"level": 1, "pawn": "Gee"' came back "no colonist"); the mod parses numbers out of strings fine
        return run_script("automate", ["raw", json.dumps({k: str(v) for k, v in payload.items()})], timeout=90)

    def t_twitch(self, action, text, viewer=None):
        clean = guards.clean_for_stream(text, max_len=400)
        if not clean:
            return "BLOCKED by the stream filter; say it cleaner"
        args = [action]
        if action == "reply":
            name = guards.clean_viewer_name(viewer or "")
            if not name: raise GuardError("reply needs a viewer name")
            args.append(name)
        args.append(clean)
        if self.dry:
            log("DRY-RUN would twitch", args)
            return "dry-run: not executed"
        return run_script("twitch", args, timeout=90)

    def t_new_colony(self, reason):
        """Owner: "redo with new colony till its fucking correct and the model should be doing all this use the admin
        chat to tell it". The guards keep her off the main menu, so she asks for the new game and the switch runs the
        proven setup (start-scenario picks the scenario row; the mod's WorldSetupDriver does every page)."""
        if self.dry:
            return "dry-run: not executed"
        # a new colony throws away the current one: only a grant the owner wrote (CLI or panel) allows it, and it
        # is used up by this one request -- a model guess or a viewer's push cannot restart the run
        grant = os.path.join(ROOT, ".local", "qa", "_owner_grant_new_colony")
        if not os.path.exists(grant):
            return ("refused: a new colony needs the owner's grant (.local/qa/_owner_grant_new_colony); keep playing "
                    "this colony and tell chat you would need the owner to say so")
        try: os.remove(grant)
        except OSError: pass
        line = guards.clean_for_stream("fact: starting a brand new colony. " + (reason or ""), max_len=200)
        if line:
            self.t_say(line)
        with open(os.path.join(ROOT, ".local", "qa", "_new_colony.request"), "w", encoding="utf-8") as f:
            f.write("Async Industries" + chr(10) + "force")
        return "new colony requested; the switch starts it within a minute -- keep talking to chat while it loads"

    def t_plan(self, what):
        line = guards.clean_for_stream("fact: pausing to plan " + (what or "the next big step") +
                                       "", max_len=200)
        if self.dry:
            return "dry-run: not executed"
        if line:
            self.t_say(line)
        try:
            self.bridge.call("rimworld/pause_game", {"pause": True})
        except Exception:
            pass
        self.paused_on_purpose = True
        self.wants_time = None
        self.think_next = True
        return "paused and announced; your next turn thinks deeply -- plan it, then unpause when the plan is set"

    def t_webcam(self, mood, caption, scene=""):
        if mood not in MOODS:
            mood = "focus"
        cap = guards.clean_for_stream(caption, max_len=90)
        if not cap:
            return "BLOCKED: caption failed the stream filter"
        if self.dry:
            log("DRY-RUN would webcam", mood, cap)
            return "dry-run: not executed"
        scn = guards.clean_for_stream(scene or "", max_len=80) or ""
        if re.search(r"\b(top off|topless|naked|nude|bare chest|undress|strip|no top|no shirt|boobs out|flash)", scn.lower()):
            scn = "crossing her arms, shaking her head with a teasing smile"   # never on Twitch: she stays dressed
        subprocess.Popen([PY, SCRIPTS["cam"], mood, cap, scn], cwd=ROOT, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, shell=False)
        return "webcam rendering: %s / %s%s" % (mood, cap, (" / " + scn) if scn else "")

    def t_snap(self, x, z, w, h, caption, marks=None):
        cap = guards.clean_for_stream(caption, max_len=90)
        if not cap:
            return "BLOCKED: caption failed the stream filter"
        args = [int(x), int(z), max(4, min(int(w), 120)), max(4, min(int(h), 120)), cap]
        for m in (marks or [])[:3]:
            note = guards.clean_for_stream((m or {}).get("note", ""), max_len=40)
            if note:
                args += ["--mark", int(m["x"]), int(m["z"]), note]
        if self.dry:
            log("DRY-RUN would snap", args)
            return "dry-run: not executed"
        return run_script("snap", args, timeout=180)

    def t_read(self, path, offset=1, limit=200):
        full = guards.read_allowed(path)
        if os.path.isdir(full):
            return "\n".join(sorted(os.listdir(full))[:200])
        lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
        a = max(1, int(offset or 1))
        chunk = lines[a - 1:a - 1 + max(1, min(int(limit or 200), 400))]
        text = "\n".join("%d\t%s" % (a + k, l) for k, l in enumerate(chunk))
        return text[:guards.MAX_READ] + ("\n[%d lines total]" % len(lines))

    # The pad records only what the mod confirmed (test run 2026-10-13, 19:15 row: "[x] explore", "[x] pawn_priorities",
    # "[x] assign" on a colony that had run none of them). A "[x]" line that names a setup item is accepted only when
    # the mod's ok: reply for that item is in the outbox since this colony started; otherwise the note is refused
    # and she sees why. Item pattern -> the game_set cmds whose ok: confirms it. EVERY item a [x] line names must be
    # confirmed (a bundled "[x] beds, shelves, stove + bill" with the stove refused is refused); word boundaries so
    # "bedroom" is the shelter, not the beds.
    PAD_ITEMS = (
        ("unforbid", r"unforbid", ("unforbid", "day_one")),
        ("priorities", r"pawn_priorities|priorit|work grid|set_work_priority", ("set_work_priority", "day_one")),
        ("assign", r"\bassign|hostility", ("assign", "day_one", "crew_setup")),
        ("explore", r"\bexplor", ("explore",)),
        ("shelter", r"\bshelter|\bbedroom|build_room", ("shelter", "build_room")),
        ("shelves", r"\bshel(f|ves)\b", ("shelves",)),
        ("stores", r"stockpile|\bstores?\b", ("stockpile_camp", "stockpile_room", "zone_create")),
        ("beds", r"\bbeds?\b", ("beds",)),
        ("stove", r"\bstoves?\b", ("stove",)),
        ("bill", r"\bbills?\b", ("add_bill", "kitchen", "bill_count")),
        ("chop", r"\bchop", ("chop",)),          # not "wood": "a wood bedroom" names the stuff, not a chop order
        ("crops", r"\bcrops?\b|\bfields?\b|\bsow", ("crops", "set_zone_plant", "zone_create")),
        ("hunt", r"\bhunt", ("hunt",)),
        ("roof", r"\broof", ("roof_area",)),
    )

    def _unconfirmed_ticks(self, text):
        """The [x] lines of a note naming a setup item the mod never answered ok: for -> [(line, item, needed cmds)]."""
        ok = self._outbox_ok_cmds()
        explored = os.path.exists(os.path.join(ROOT, ".local", "qa", "_explore_done.flag"))
        bad = []
        for raw in str(text or "").splitlines():
            line = raw.strip()
            if not re.match(r"^(?:-\s*)?\[x\]", line, flags=re.I):
                continue
            # only the item the [x] NAMES is tested -- the plan words after "; next:", "--", "->" or "then" are not
            # claims (run 5, 00:05:40 and 00:07:04: "[x] stream title and category set; next: ... shelves, stove" was
            # refused twice for the shelves and the stove it had not claimed; owner: "why is ypour not fixing it")
            low = re.split(r";\s*next\b|\bnext:|\s--\s|->|\bthen\b|\bafter that\b", line.lower(), maxsplit=1)[0]
            # and only the item NAME: what follows ":" or "(" describes it ("[x] storage room: ... (walls, door and
            # roof around the pile)" was refused for the roof it described -- run 5, 00:34:34); a bundle like
            # "[x] beds, shelves, stove + bill" has no colon and is still tested whole
            low = re.split(r"[:(]", low, maxsplit=1)[0]
            for item, pat, cmds in self.PAD_ITEMS:
                if not re.search(pat, low):
                    continue
                if item == "explore" and explored:
                    continue
                if not any(c in ok for c in cmds):
                    bad.append((line[:90], item, cmds))
        return bad

    def t_note(self, name, text, append=False):
        bad = self._unconfirmed_ticks(text)
        if bad:
            raise GuardError("note not written -- a [x] needs the mod's ok: on record, and these have none this colony: "
                             + " ; ".join("%r: %s (needs an ok: reply to game_set cmd %s)" % (l, item, " / ".join(c)) for l, item, c in bad)
                             + ". Write them as [ ] (with what was refused, if it was) and send the note again.")
        return "wrote " + guards.scratch_write(name, text, append=bool(append))


# ---------------------------------------------------------------------------------------------------------------
# This colony's epoch: where in the mod's outbox it started. Written by the autopilot when it detects a new colony
# (autopilot.colony_epoch_check); read by the note tool and ladder_set so only THIS colony's ok: replies count.
# ---------------------------------------------------------------------------------------------------------------
COLONY_EPOCH = "colony-epoch.json"
AUTOMATION_OUTBOX = os.path.join(os.path.expandvars(r"%USERPROFILE%/AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"),
                                 "RimroomsAutomation", "outbox.jsonl")


def colony_epoch():
    try:
        return json.load(open(guards.scratch_path(COLONY_EPOCH), encoding="utf-8"))
    except Exception:
        return {}


def last_day_one_offset():
    """The byte offset of the last 'day_one' reply in the outbox: keep-playing sends day_one once per new colony, so
    the newest such row is the mod-confirmed start of the colony on the map (0 when there is none)."""
    off, found = 0, 0
    try:
        with open(AUTOMATION_OUTBOX, "rb") as f:
            for raw in f:
                if b"'cmd': 'day_one'" in raw:
                    found = off
                off += len(raw)
    except OSError:
        return 0
    return found


def write_colony_epoch(offset=None):
    """offset None = the outbox's current size (a colony starting now); 0 = count every reply on file."""
    if offset is None:
        try:
            offset = os.path.getsize(AUTOMATION_OUTBOX)
        except OSError:
            offset = 0
    guards.scratch_write(COLONY_EPOCH, json.dumps({"outbox_offset": int(offset), "ts": time.time(),
                                                   "written": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1))
    return offset


def _outbox(text, reply_to):
    """Append one Unity line to the studio outbox (same row format unity-say.py writes). Fixed path, filtered text."""
    last = 0
    if os.path.exists(OUTBOX):
        for line in open(OUTBOX, encoding="utf-8"):
            try:
                last = max(last, int(json.loads(line).get("id", 0)))
            except Exception:
                pass
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": last + 1, "replyTo": reply_to, "ts": int(time.time() * 1000),
                            "persona": "unity", "text": text}) + "\n")


def read_owner(after_id=0):
    """The owner's private messages: studio-inbox rows WITHOUT the "[twitch]" prefix, typed in the Persona Studio
    window (owner: "train in twitch versus admin conversions fromn the admin panel and admin hud thing"). Never shown
    on stream; answered with reply_owner, whose outbox row points at the message so the stream feed skips it."""
    inbox = os.path.join(ROOT, ".claude", ".studio-inbox.jsonl")
    out = []
    try:
        for line in open(inbox, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            text = str(r.get("text") or "")
            if int(r.get("id", 0)) > after_id and text and not text.startswith("[twitch]"):
                out.append({"msg_id": int(r["id"]), "text": text[:600], "ts": r.get("ts") or 0})
    except OSError:
        pass
    return out


def read_chat():
    """New Twitch rows from the studio's /api/chat (read-only GET)."""
    try:
        rows = json.loads(urllib.request.urlopen(STUDIO + "/api/chat", timeout=5).read()).get("rows", [])
    except Exception:
        return []
    return [r for r in rows if not r.get("unity") and (r.get("who") or "").lower() != "unityplaysrimworld"]
