"""RimPLC: evaluate the ladder (docs/playbook.gates.json) against measured game state and hand back ONE action chain.

Owner, 2026-10-10, verbatim: *"all my things ive been tossing at you as instructions on how to play all need to
be put into the models undertstanding but not a text wall shit a actual logical guided logaica gates system of
porcess chains and actions for every thing uve ran into in the game"*.

Owner, 2026-10-12, verbatim: *"i think this is the whoole PLC like logic chain if this then this if heath level
reaches then this type of thing for the whole game properly layed out into a PLC that we will call RimPLC"*.

The ladder is laid out as a PLC:

  * INPUTS (sensors): `state()` reads the bridge once per scan; `derive()` turns those raw reads into measured
    keys. A key that cannot be read is left OUT of the state, never filled with a fake 0, so a rung that needs it
    stays quiet. The sensor table in the playbook (`sensors`) documents every key and its source.
  * TAGS: constants (safety limits, owner only) and variables (setpoints recomputed from the colony's size each
    scan, clamped to min/max, overridable by her with `ladder_set tag`).
  * MARKS: what the bridge cannot measure, set by her with `ladder_set mark` -- booleans or numbers. Numeric
    marks stay numbers. A boolean mark that was never set reads false; a numeric mark reads its `mark_defaults`
    value from the playbook, or stays unmeasured.
  * RUNGS: `when` (an AND of conditions) -> `then` (an ordered action chain), scanned by priority. A growth rung
    with `"latch": true` gets a done-latch: `mark_<id>_done: false` is added to its `when` and
    `ladder_set mark <id>_done true` is appended to its `then`, so a finished long-term rung stops hiding every
    rung ranked after it.

    python .local/autopilot/gates.py            # what fires right now, and why
    python .local/autopilot/gates.py --all      # every rung that matches, in order
"""
import importlib.util, json, math, os, re, socket, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QA = os.path.join(ROOT, ".local", "qa")
# the tracked copy under docs/ is the source of record; .local keeps a working copy for when docs is absent
PLAYBOOK = next((p for p in (os.path.join(ROOT, "docs", "playbook.gates.json"),
                             os.path.join(HERE, "playbook.json")) if os.path.exists(p)), None)
bspec = importlib.util.spec_from_file_location("b", os.path.join(QA, "bridge.py"))
bridge = importlib.util.module_from_spec(bspec); bspec.loader.exec_module(bridge)
cspec = importlib.util.spec_from_file_location("camp", os.path.join(QA, "camp.py"))
camp = importlib.util.module_from_spec(cspec); cspec.loader.exec_module(camp)

QA_DIR = QA
LADDER = os.path.join(HERE, "scratch", "ladder.json")          # her edits: marks, tag overrides, her own rungs
SETPOINTS = os.path.join(HERE, "scratch", "setpoints.json")    # measured, local
ALERT_LOG = os.path.join(HERE, "scratch", "alert_labels.json")  # every alert label ever seen, to fix ALERT_MATCH

# ---------------------------------------------------------------------------------------------------------------
# Sensor tables. Every name here is either seen in a captured bridge reply (.local/qa/*.json) or marked UNVERIFIED.
# ---------------------------------------------------------------------------------------------------------------
TICKS_PER_DAY = 60000
TICKS_PER_QUADRUM = 900000
# vanilla LetterDefOf.ThreatBig / ThreatSmall (seen in the decompiled Verse.FogGrid.cs under .local/inspection-*);
# the captured list_letters reply carries the `letterDef` field (only "PositiveEvent" captured so far)
THREAT_LETTER_DEFS = ("ThreatBig", "ThreatSmall")
THREAT_LETTER_MAX_AGE = 2 * TICKS_PER_DAY     # a threat letter older than this no longer vouches for the crowd
# substring of an alert label (lower case) -> alert_<key>. UNVERIFIED: no list_alerts reply has been captured;
# the first live scans log every label to scratch/alert_labels.json and this table is fixed from that log.
ALERT_MATCH = {
    "low_food": "low food", "starv": "starv", "hypotherm": "hypotherm", "heatstroke": "heatstroke",
    "low_medicine": "medicine", "warm_clothes": "warm", "sickness": "sick", "need_research": "research",
    "idle": "idle", "colonist_needs_rescue": "rescue", "food_rot": "rot",
    # the control chains' health inputs (UNVERIFIED labels, same as the rest of this table)
    "needs_tend": "treatment", "life_threat": "life-threatening", "bleeding": "bleed",
}
# weapons lying loose on the map: Gun_* is captured (Gun_ChargeRifle); the other prefixes are UNVERIFIED
WEAPON_PREFIXES = ("Gun_", "MeleeWeapon_", "Bow_")
# quality words that make a loose weapon junk (sell or smelt); the label carries "(<color>normal</color>)" (captured),
# the words awful / poor are UNVERIFIED in captures
JUNK_QUALITY = ("awful", "poor")
# defName -> resource key (sweep, summed by stackCount; stackCount is UNVERIFIED in captures, 1 per stack otherwise)
RESOURCES = {"Steel": "steel", "ComponentIndustrial": "components", "ComponentSpacer": "adv_components",
             "Plasteel": "plasteel", "Uranium": "uranium", "Gold": "gold", "Silver": "silver",
             "Chemfuel": "chemfuel", "Cloth": "cloth"}
NEVER_HUNT_DEFS = ("Boomalope", "Thrumbo", "Elephant", "Rhinoceros", "Megasloth")   # plus Bear_*
INSECT_DEFS = ("Megascarab", "Spelopede", "Megaspider")                                   # infestation hive insects
MOUNT_DEFS_DEFAULT = ("Elephant", "Horse", "Dromedary", "Muffalo", "Thrumbo")
# designation defName -> key. The field shape {defName, targetCell, targetThingDefName} is captured; these vanilla
# DesignationDef names are UNVERIFIED (only Deconstruct and SkilledBuilder3 have been seen).
DESIGNATIONS = {"Hunt": "designations_hunt", "Tame": "designations_tame", "HarvestPlant": "designations_harvest",
                "Mine": "designations_mine", "CutPlant": "designations_cut"}
# buildings counted as distinct objects: a multi-cell building is listed on every cell it covers and the cell reply
# has no thing id, so adjacent cells of the same def are merged into one object (two touching beds read as one)
BUILDING_KEYS = {
    "stoves": lambda d, c: d in ("FueledStove", "ElectricStove"),
    "research_benches": lambda d, c: c == "RimWorld.Building_ResearchBench" or d in ("SimpleResearchBench", "HiTechResearchBench"),
    "comms_console": lambda d, c: d == "CommsConsole" or c == "RimWorld.Building_CommsConsole",
    "turrets": lambda d, c: "Turret" in d and not d.startswith(("Blueprint_", "Frame_")),
    "beds": lambda d, c: c in ("RimWorld.Building_Bed", "Hospitality.Building_GuestBed"),
    "throne": lambda d, c: "Throne" in d and not d.startswith(("Blueprint_", "Frame_")),
    "pod_launchers": lambda d, c: d == "PodLauncher",
    "transport_pods": lambda d, c: d == "TransportPod",
    "grav_parts": lambda d, c: "Grav" in d and not d.startswith(("Blueprint_", "Frame_")),
    "ship_parts": lambda d, c: d.startswith("Ship_"),
    "power_generators": lambda d, c: "Generator" in d and not d.startswith(("Blueprint_", "Frame_"))
                                     or d in ("WindTurbine", "GeothermalGenerator"),
}
BOOL_BUILDINGS = ("comms_console", "throne")


def _session():
    try:
        port, tok = bridge.endpoint()
    except SystemExit as e:                      # "no live standalone bridge": a condition, not a reason to exit
        raise RuntimeError(str(e))
    s = socket.create_connection(("127.0.0.1", port), timeout=120); buf = bytearray()
    bridge.exchange(s, buf, "session/hello", {"token": tok, "bridgeVersion": "gates/2",
                                              "platform": "windows", "launchId": str(uuid.uuid4())})
    return s, buf


def state():
    """Everything the rungs ask about, measured -- never assumed. Reads only; never moves the player's selection."""
    s, buf = _session()
    def call(n, a=None):
        r = bridge.exchange(s, buf, "tools/call", {"name": n, "arguments": a or {}}); r = r.get("result", r)
        return r.get("structuredContent", r) if isinstance(r, dict) else r
    def opt(n, a=None):
        try:
            return call(n, a)
        except (Exception, SystemExit):
            return None
    raw = {}
    raw["game_info"] = call("rimworld/get_game_info"); time.sleep(1.2)
    gi2 = call("rimworld/get_game_info")
    raw["ticks_moving"] = raw["game_info"].get("ticksGame") != gi2.get("ticksGame")
    raw["bridge"] = opt("rimbridge/get_bridge_status")
    raw["ui"] = call("rimworld/get_ui_state")
    raw["letters"] = call("rimworld/list_letters")
    raw["alerts"] = opt("rimworld/list_alerts")
    raw["colonists"] = call("rimworld/list_colonists")
    raw["here"] = opt("rimworld/list_colonists", {"currentMapOnly": True})
    raw["zones"] = opt("rimworld/list_zones")
    raw["areas"] = opt("rimworld/list_areas")
    raw["rimplc"] = opt("rimplc/read_state")          # RimPLC's live sensors (computed on request, never a stale file)
    crew = [c for c in (raw["colonists"] or {}).get("colonists", []) if c.get("factionIsPlayer")]
    home = camp.home_map(crew)
    here = (raw["here"] or {}).get("colonists", []) if isinstance(raw["here"], dict) else []
    if any(c.get("mapId") == home for c in here):
        # the cell sweep can only read the map on screen; when that is not home nothing is switched (a poll must
        # never move the player's selection) and every sweep key stays unmeasured this scan
        cells = []
        minx, minz, maxx, maxz = camp.camp_rect(crew, home)
        for x in range(minx, maxx + 1, 26):
            for z in range(minz, maxz + 1, 26):
                r = opt("rimworld/get_cells_info", {"x": x, "z": z, "width": 26, "height": 26})
                cells.extend((r or {}).get("cells", []) if isinstance(r, dict) else [])   # past the edge reads empty
        raw["cells"] = cells
    raw["foreground"] = _foreground()
    raw["explore_done"] = os.path.exists(os.path.join(QA_DIR, "_explore_done.flag"))
    st = derive(raw, _ladder_file())
    _log_alert_labels(st.get("alerts") or [])
    return st


def _payload(r, key):
    return (r or {}).get(key, []) if isinstance(r, dict) else []


def derive(raw, lf=None):
    """Raw bridge replies -> measured keys. Pure: feed it captured replies to check the ladder offline.

    raw keys (all optional): game_info, ticks_moving, bridge, ui, letters, alerts, colonists, here, zones, areas,
    cells (list of get_cells_info cells), foreground, explore_done. A missing raw read leaves its keys out.
    """
    lf = lf or {}
    st = {}
    # --- clock and session ---
    gi = raw.get("game_info") or {}
    if "ticks_moving" in raw: st["ticks_moving"] = bool(raw["ticks_moving"])
    tk = gi.get("ticksGame")
    if isinstance(tk, (int, float)) and not isinstance(tk, bool):
        st["day"] = round(tk / TICKS_PER_DAY, 2)
        st["quadrum_index"] = int(tk // TICKS_PER_QUADRUM) % 4     # a counter, NOT a season (latitude-dependent)
    if isinstance(gi.get("mapCount"), int): st["map_count"] = gi["mapCount"]
    # paused rides on the `state` block every bridge reply carries (captured: list_zones, designator replies)
    for src in (raw.get("bridge"), raw.get("zones"), raw.get("ui")):
        if isinstance(src, dict):
            blk = src.get("state") if isinstance(src.get("state"), dict) else src
            if isinstance(blk.get("paused"), bool):
                st["paused"] = blk["paused"]; break
    ui = raw.get("ui")
    if isinstance(ui, dict):
        st["dialog_open"] = bool(ui.get("nonImmediateDialogWindowOpen") or ui.get("NonImmediateDialogWindowOpen"))
    # --- letters: counted once (seen ids live in ladder.json); threats by letterDef, never by the word "raid" ---
    if raw.get("letters") is not None:
        letters = _payload(raw["letters"], "letters")
        seen = set(lf.get("letters_seen", []))
        unseen = [l for l in letters if l.get("id") not in seen]
        st["letters"] = len(unseen)
        st["letter_labels"] = [l.get("label") for l in letters]
        st["letter_defs"] = [l.get("letterDef") for l in letters]
        # a threat letter vouches for the crowd while it is recent, whether or not she has read it: reading a raid
        # letter must not make the raiders vanish from the ladder
        # an UNREAD threat letter vouches whatever its age: test run 2026-10-13 19:27, "Badger revenge" passed the
        # 2-day cap in five real minutes at superfast and left the ladder before she opened it, then got read as a
        # joke while Unity lay wounded. A read one vouches for the 2 days as before.
        threat_unread = [l for l in letters if l.get("letterDef") in THREAT_LETTER_DEFS and l.get("id") not in seen]
        st["threat_letter"] = bool(threat_unread) or any(l.get("letterDef") in THREAT_LETTER_DEFS and
                                  (l.get("ageTicks") is None or l.get("ageTicks") <= THREAT_LETTER_MAX_AGE)
                                  for l in letters)
        st["threat_letter_unread"] = bool(threat_unread)
        st["quest_letter"] = any("quest" in (l.get("label") or "").lower() or "Quest" in (l.get("letterDef") or "")
                                 for l in unseen)
        st["empire_letter"] = any("empire" in (l.get("relatedFaction") or "").lower() for l in unseen)
    # --- alerts (labels logged; the match table is UNVERIFIED until the log is read) ---
    if raw.get("alerts") is not None:
        labels = [a.get("label") or "" for a in _payload(raw["alerts"], "alerts")]
        st["alerts"] = labels
        low = [l.lower() for l in labels]
        for key, sub in ALERT_MATCH.items():
            st["alert_" + key] = any(sub in l for l in low)
    # --- crew ---
    every = _payload(raw.get("colonists"), "colonists")
    crew = [c for c in every if c.get("factionIsPlayer") and c.get("humanlike", True) is not False]
    st["crew"] = [(c.get("name"), c.get("job"), bool(c.get("drafted")), bool(c.get("downed"))) for c in crew]
    if raw.get("colonists") is not None:
        st["colonists"] = len(crew)
        st["downed_count"] = sum(1 for c in crew if c.get("downed"))
        st["drafted_count"] = sum(1 for c in crew if c.get("drafted"))
        st["mental_break"] = any(c.get("mentalState") for c in crew)
        maps = {c.get("mapId") for c in crew if c.get("mapId")}
        st["away_maps"] = max(0, len(maps) - 1)
        # UNVERIFIED whether list_colonists ever lists animals, mechs or hostile pawns: only written when seen, so an
        # empty list never reads as a measured zero
        n_an = sum(1 for c in every if c.get("animal") and c.get("factionIsPlayer"))
        n_me = sum(1 for c in every if c.get("mechanoid") and c.get("factionIsPlayer"))
        n_ho = sum(1 for c in every if c.get("factionHostileToPlayer") and not c.get("dead") and not c.get("downed"))
        if n_an: st["colony_animals"] = n_an
        if n_me: st["colony_mechs"] = n_me
        if n_ho: st["hostile_pawns_listed"] = n_ho
    ours = camp.crew_names(crew)
    home = camp.home_map(crew)
    st["home_map"] = home
    here = _payload(raw.get("here"), "colonists")
    on_home = any(c.get("mapId") == home for c in here)
    st["home_on_screen"] = on_home
    # --- zones and areas ---
    if raw.get("zones") is not None:
        zones = _payload(raw["zones"], "zones")
        zl = [z.get("label") or "" for z in zones]
        st["growing_cells"] = sum(z.get("cellCount", 0) for z in zones if str(z.get("className", "")).endswith("Zone_Growing"))
        st["stockpile_cells"] = sum(z.get("cellCount", 0) for z in zones if str(z.get("className", "")).endswith("Zone_Stockpile"))
    else:
        zl = []
    st["food_store"] = any("food" in z.lower() for z in zl)
    st["main_store"] = any("main" in z.lower() for z in zl)
    areas = _payload(raw.get("areas"), "areas")
    hc = [a.get("cellCount") for a in areas if str(a.get("className", "")).endswith("Area_Home")]
    cells = raw.get("cells") if on_home else None
    if not hc and cells:     # every cell reply carries its areas with their cellCount (captured)
        hc = [a.get("cellCount") for c in cells[:50] for a in (c.get("areas") or [])
              if isinstance(a, dict) and str(a.get("className", "")).endswith("Area_Home")][:1]
    if hc and isinstance(hc[0], int): st["home_cells"] = hc[0]
    # --- the sweep: only when home is the map on screen ---
    if cells is not None:
        _sweep(st, cells, ours, crew)
    if "foreground" in raw: st["game_foreground"] = bool(raw["foreground"])
    st["colony_exists"] = len(st["crew"]) > 0
    if "explore_done" in raw: st["explore_done"] = bool(raw["explore_done"])
    # --- her own marks: numbers stay numbers, everything else is a boolean ---
    for k, v in (lf.get("marks") or {}).items():
        st["mark_" + k] = v if isinstance(v, (int, float)) and not isinstance(v, bool) else bool(v)
    for k in ("pawns_set", "assign_set", "beds_set", "stove_set", "bill_set"):
        st.setdefault("mark_" + k, False)
    _sensor_file(st)
    try:
        for k, v in host_inputs().items(): st.setdefault(k, v)
    except Exception:
        pass
    if not st.get("mark_start_kind"):          # nothing ever set it (2026-10-13 audit): the GO writes the scenario it chose
        try: st["mark_start_kind"] = int(open(os.path.join(QA, "_start_kind"), encoding="utf-8").read().strip() or 0)
        except (OSError, ValueError): pass
    # LIVE overlay from RimPLC: the mod's sensors.json is written on game ticks, so while the game is held (the setup
    # lock, run 5) it ages past _sensor_file's five minutes and every sweep key here went None -- the driver read
    # "food days 0.0" and the lock read no hostiles from a 24-minute-old snapshot. RimPLC computes on request.
    try:
        _r = raw.get("rimplc")
        _live = _r.get("state") if isinstance(_r, dict) and isinstance(_r.get("state"), dict) else {}
        for _k, _v in _live.items():
            if _k.startswith("mark_") or _k in ("crew",):
                continue
            if st.get(_k) is None and isinstance(_v, (int, float, bool)):
                st[_k] = _v
        if _live:
            st["rimplc_live"] = True
            # run 5, 00:25:20: one empty `list_colonists` read (the game busy planning 35 walls) read as "no colony" and
            # froze her 104 s with a conversation reset; RimPLC's own count is the second witness
            if not crew and (_live.get("colonists") or 0) > 0:
                st["colony_exists"] = True
                st["crew_list_missing"] = True
    except Exception:
        pass
    _chain_inputs(st, crew, raw.get("colonists") is not None)
    return st


SENSOR_FILE = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow", "Ludeon Studios",
                           "RimWorld by Ludeon Studios", "Config", "RimroomsAutomation", "sensors.json")
COOK_TO = ("Firefighter", "Patient", "Doctor", "PatientBedRest", "BasicWorker", "Warden", "Handling", "Cooking")


def _sensor_file(st):
    """The mod's input scan (Sensors.cs, every 600 ticks): readings the bridge sweep never had. A file older than
    five minutes is stale and fills nothing, so an old game's scan cannot drive a new one."""
    try:
        if time.time() - os.path.getmtime(SENSOR_FILE) > 300:
            return
        sx = json.load(open(SENSOR_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return
    st["sensors_raw"] = True
    for k in ("bill_rows", "research_queue_empty", "ship_research_done", "items_forbidden", "blueprints", "prisoners"):
        if k in sx: st[k] = sx[k]
    pawns = sx.get("pawns") or []
    if pawns:
        # the plan: Firefighter..Cooking at 1, nothing the pawn can do left at 0
        st["grid_matches_plan"] = all(all((p.get("work") or {}).get(w, 1) == 1 for w in COOK_TO) and
                                      all(v != 0 for v in (p.get("work") or {}).values()) for p in pawns)
    grow = [z for z in sx.get("zones") or [] if z.get("kind") == "Zone_Growing"]
    if grow:
        st["fields_all_default_crop"] = len({z.get("plant") for z in grow}) == 1 and len(grow) > 1
    texts = [(l.get("label") or "") + " " + (l.get("text") or "") for l in sx.get("letters") or []]
    if texts:
        st["letter_labels"] = list(st.get("letter_labels") or []) + texts
    st["game_conditions"] = sx.get("conditions") or []
    for cond in st["game_conditions"]:
        st["condition_" + re.sub(r"[^a-z0-9]+", "_", str(cond).lower()).strip("_")] = True


def _chain_inputs(st, crew, crew_read):
    """The control chains' inputs (owner decision 3 in docs/RIMPLC_DESIGN.md): who can fight, the odds, who is hurt.

    The bridge has no pawn health read (list_colonists carries drafted/downed/mentalState only; a pawn's cell
    hitPoints is -1, captured), so hurt and bleeding come from alerts (UNVERIFIED labels) or her own marks after a
    pawn_check Health look. Nothing is written when nothing behind it was read.
    """
    if crew_read:
        st["able_shooters"] = sum(1 for c in crew if not c.get("downed") and not c.get("dead") and not c.get("mentalState"))
    h = st.get("hostiles_on_map")
    if isinstance(h, (int, float)) and h > 0 and "able_shooters" in st:
        st["fight_ratio"] = round(st["able_shooters"] / float(h), 2)
    alerts_read = "alerts" in st
    bleed_src = [st.get("alert_bleeding"), st.get("alert_life_threat"), st.get("mark_pawn_bleeding")]
    if alerts_read or "mark_pawn_bleeding" in st:
        st["pawn_bleeding"] = any(bool(v) for v in bleed_src)
    if crew_read or alerts_read or "mark_colonist_hurt" in st:
        st["colonist_hurt"] = bool(st.get("downed_count") or st.get("alert_needs_tend") or st.get("pawn_bleeding")
                                   or st.get("mark_colonist_hurt"))


def _sweep(st, cells, ours, crew):
    meals = raw_food = wood = med = bp = foes = beasts = roofed = total = defence = 0
    res = {k: 0 for k in set(RESOURCES.values())}
    berry = healroot = wild = danger = mounts = fire = corpses = embr = weapons = junk = 0; battery = False
    bhp = {}          # (defName, stuff) -> [hitPoints per cell], for the damaged-building float switch
    desig = {k: 0 for k in DESIGNATIONS.values()}
    bcells = {k: set() for k in BUILDING_KEYS}
    mount_defs = MOUNT_DEFS_DEFAULT
    for c in cells:
        bp += len(c.get("blueprintBuildDefs") or [])
        for dg in c.get("designations") or []:
            k = DESIGNATIONS.get((dg or {}).get("defName") if isinstance(dg, dict) else None)
            if k: desig[k] += 1
        xy = (c.get("x"), c.get("z"))
        for t in c.get("things", []):
            d = t.get("defName") or ""; cl = t.get("className") or ""; n = t.get("stackCount", 1)
            for k, test in BUILDING_KEYS.items():
                if test(d, cl): bcells[k].add((d, xy))
            if d.startswith("Meal"): meals += n
            elif d.startswith(("Raw", "Meat_")): raw_food += n       # meat is food too (2026-10-13 audit: a hunting start read as starving)
            elif d == "WoodLog": wood += n
            elif "Medicine" in d: med += n
            elif d in RESOURCES: res[RESOURCES[d]] += n
            elif "Leather" in d: res["cloth"] += n
            elif d in ("Plant_Berry", "Plant_Strawberry_Wild"): berry += 1     # Plant_Berry UNVERIFIED; the other captured
            elif d in ("Plant_Healroot", "Plant_HealrootWild"): healroot += 1
            elif d == "Fire": fire += 1
            elif "Corpse" in cl: corpses += 1
            elif cl == "Verse.Pawn":
                lab = t.get("label") or ""
                nm = lab.split("<")[0].strip()
                if "," in lab:            # humanlikes carry ", <title>" in their label (captured)
                    if nm and nm not in ours: foes += 1
                elif d.startswith("Mech_") or d in INSECT_DEFS or "manhunter" in lab.lower():
                    beasts += 1       # mechs, insects and manhunters are hostile with or without a letter
                elif d != "Human":
                    if d in NEVER_HUNT_DEFS or d.startswith("Bear_"): danger += 1
                    else: wild += 1
                    if d in mount_defs: mounts += 1
            if d.startswith(WEAPON_PREFIXES):
                weapons += 1
                if any(q in (t.get("label") or "").lower() for q in JUNK_QUALITY): junk += 1
            hp = t.get("hitPoints")
            if ("Building" in cl and isinstance(hp, (int, float)) and hp > 0
                    and not t.get("isBlueprint") and not t.get("isFrame") and not d.startswith(("Blueprint_", "Frame_"))):
                bhp.setdefault((d, t.get("stuffDefName")), []).append(hp)
            if d == "Battery": battery = True
            if "Embrasure" in d and not d.startswith(("Blueprint_", "Frame_")): embr += 1
            if (("Turret" in d or d in ("Sandbags", "Barricade") or "Embrasure" in d)
                    and not d.startswith(("Blueprint_", "Frame_"))): defence += 1
        # the stores are the cells inside a food/main stockpile zone, read off the cell itself
        zone = json.dumps(c.get("zone") or "").lower()
        if "food" in zone or "main" in zone:
            total += 1; roofed += 1 if c.get("roofDefName") else 0
    st["days_of_food"] = round((meals * 0.9 + raw_food * 0.05) / (1.6 * max(1, len(crew))), 2)
    st.update({"meals": meals, "raw_food": raw_food, "wood": wood, "medicine": med, "blueprints": bp,
               "humanlikes_not_ours": foes, "defences_built": defence > 0})
    st.update(res)
    st.update(desig)
    for k, cs in bcells.items():
        n = _objects(cs)
        st[k] = n > 0 if k in BOOL_BUILDINGS else n
    st["has_power"] = st["power_generators"] > 0 or battery
    st.update({"berry_bushes": berry, "healroot_plants": healroot, "danger_animals_near": danger,
               "mount_candidates": mounts, "fire_cells": fire, "corpses": corpses, "embrasures": embr,
               "wild_game": max(0, wild - st.get("colony_animals", 0)),
               "loose_weapons": weapons, "junk_weapons": junk})
    # damaged buildings: the cell reply has hitPoints but no maxHitPoints (captured), so the healthiest cell of the same
    # def and stuff in this sweep stands in for full health. A group of fewer than 3 cells cannot tell, and a group that
    # is damaged evenly reads as healthy (UNVERIFIED: no captured sweep shows a damaged building)
    st["buildings_damaged"] = sum(sum(1 for h in hs if h < max(hs)) for hs in bhp.values() if len(hs) >= 3)
    if total:
        st["store_roofed_fraction"] = roofed / total
        st["unroofed_store_cells"] = total - roofed
    # hostiles: the crowd counts as hostile only while a recent threat letter vouches for it, or the colonist list
    # itself names hostile pawns
    st["hostiles_on_map"] = max(foes if st.get("threat_letter") else 0, st.get("hostile_pawns_listed", 0)) + beasts
    # wall_gaps is not measured: the perimeter rung stays disabled rather than fed a fixed 0


def _objects(cs):
    """Count connected groups of same-def cells (a multi-cell building is listed on each of its cells)."""
    left = set(cs); n = 0
    while left:
        d, (x, z) = left.pop(); n += 1; stack = [(x, z)]
        while stack:
            px, pz = stack.pop()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                k = (d, (px + dx, pz + dz))
                if k in left: left.discard(k); stack.append(k[1])
    return n


def _log_alert_labels(labels):
    try:
        old = set(json.load(open(ALERT_LOG, encoding="utf-8")))
    except Exception:
        old = set()
    new = old | {l for l in labels if l}
    if new != old:
        try:
            os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
            json.dump(sorted(new), open(ALERT_LOG, "w", encoding="utf-8"), indent=1)
        except Exception:
            pass


def _ladder_file():
    try:
        return json.load(open(LADDER, encoding="utf-8"))
    except Exception:
        return {}


def _foreground():
    try:
        import ctypes
        u = ctypes.WinDLL("user32"); g = u.FindWindowW(None, "RimWorld by Ludeon Studios")
        return bool(g) and u.GetForegroundWindow() == g and not u.IsIconic(g)
    except Exception:
        return False


def _foreground_process():
    """The exe name (lower case, no path) of the process that owns the foreground window; "" when it cannot be read.
    GetForegroundWindow -> GetWindowThreadProcessId -> QueryFullProcessImageNameW (RimWorld runs as RimWorldWin64.exe)."""
    try:
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        u.GetForegroundWindow.restype = ctypes.c_void_p
        u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        k.OpenProcess.restype = ctypes.c_void_p
        k.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        h = u.GetForegroundWindow()
        if not h:
            return ""
        pid = wintypes.DWORD(0); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if not pid.value:
            return ""
        p = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not p:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024); n = wintypes.DWORD(len(buf))
            if not k.QueryFullProcessImageNameW(p, 0, buf, ctypes.byref(n)):
                return ""
            return os.path.basename(buf.value).lower()
        finally:
            k.CloseHandle(p)
    except Exception:
        return ""


def tags(book, st, lf=None):
    """The PLC tag table: constants stay put, variables are recomputed from the empire's current size.

    Owner, 2026-10-10, verbatim: "with changaeable variables and constants as needed and maintained for a
    growing empire". So a colony of three and an empire of thirty read the same ladder and get different
    numbers, and the numbers are maintained here rather than scattered through the rungs.
    """
    lf = _ladder_file() if lf is None else lf
    tg = book.get("tags") or {}
    const = dict(tg.get("constants") or {})
    var = tg.get("variables") or {}
    n = max(1, len(st.get("crew") or []))
    home = st.get("home_cells")
    computed = {
        "FOOD_MIN_DAYS": 2 + 0.4 * n,
        "FOOD_COMFORT_DAYS": 2 * (2 + 0.4 * n),
        "MEAL_BILL_TARGET": 10 * n,
        "WOOD_RESERVE": 60 * n,
        "MEDICINE_RESERVE": 2 * n,
        "BEDS_NEEDED": n + 1,
        "COOLERS_PER_ROOM": 1,
        "TURRET_TARGET": 2 + n // 3,
        "STOCK_CELLS": 30 + 15 * n,
        "COMPONENT_RESERVE": 5 + n,
        "STEEL_RESERVE": 150 * n,
        "AID_CALL_FOES": 2 * n,
        "MOUNT_TARGET": n,
        "WEAPON_KEEP": n + 2,
    }
    if isinstance(home, (int, float)):
        computed["EMBRASURE_TARGET"] = int(4 * math.sqrt(home))
    out = dict(const)
    overrides = lf.get("tags") or {}
    pod_squad = None
    for name, spec in var.items():
        v = overrides[name] if name in overrides else computed.get(name, spec.get("value"))
        if name == "POD_FUEL" and name not in overrides and pod_squad is not None:
            v = 150 * pod_squad
        try:
            v = float(v) if not isinstance(v, (int, float)) or isinstance(v, bool) else v
        except (TypeError, ValueError):
            v = spec.get("value")
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None: v = max(lo, v)
        if hi is not None: v = min(hi, v)
        v = round(v, 2) if isinstance(v, float) else v
        spec["value"] = v           # in memory only; the live setpoints are written to scratch/setpoints.json
        out[name] = v
        if name == "POD_SQUAD": pod_squad = v
    return out


def latch_name(rid):
    """The done-mark of a latched rung: lowercase, underscores, at most 40 characters (ladder_set's mark rule)."""
    return re.sub(r"[^a-z0-9]+", "_", str(rid).lower()).strip("_")[:35] + "_done"


def _latched(g):
    """Apply a rung's done-latch: when gets mark_<id>_done false, then ends with setting it true."""
    if not g.get("latch"):
        return g
    g = dict(g); name = latch_name(g["id"])
    g["when"] = dict(g.get("when") or {}); g["when"].setdefault("mark_" + name, False)
    step = "ladder_set mark %s true" % name
    g["then"] = list(g.get("then") or [])
    if not any(step in s for s in g["then"]): g["then"].append(step)
    return g


def _bound(expr, st, tagvals):
    """A numeric bound: a number, a {TAG}, or a measured state/tag name. None when it cannot be resolved."""
    e = expr.strip()
    if e.startswith("{") and e.endswith("}"):
        e = e[1:-1].strip()
    try:
        return float(e)
    except ValueError:
        pass
    for src in (tagvals, st):
        v = src.get(e)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


OPS = (">=", "<=", "!=", ">", "<")

# ---------------------------------------------------------------------------------------------------------------
# Nested instructions (RimPLC P2, the same rules as RimPLC/Source/RimPLC/Engine.cs). A `when` entry whose value is an
# object is an instruction; its key is only a label (it names the instruction, and its timer/counter memory):
#   {"any": [when, when, ...]}             OR of AND-branches
#   {"not": when}                          NOT (an unmeasured input stays unmeasured: a missing key never fires)
#   {"ton": when, "ticks": N | "hours": H} on-delay: true once `when` has held N game ticks
#   {"tof": when, "ticks": N | "hours": H} off-delay: stays true N ticks after `when` stops holding
#   {"ctu": when, "preset": N, "reset": when}  counts rising edges of `when`; true at N or more; `reset` zeroes it
#   {"ons": when}                          one-shot: true on the one scan `when` turns true
# Timers count game ticks (the `ticks` key when present, else day * 60000; a game hour is 2500 ticks). Timer and
# counter memory moves forward once per committed scan (decide(write=True) here, a tick scan in game); a read-only
# scan sees what the next scan would see without moving it.
# ---------------------------------------------------------------------------------------------------------------
TICKS_PER_HOUR = 2500
STATEFUL = ("ton", "tof", "ctu", "ons")
NESTED = ("any", "not") + STATEFUL
MEMORY = os.path.join(HERE, "scratch", "plc_memory.json")   # timer / counter memory between decide() calls


def expr_op(e):
    """The instruction an object condition holds, or None when it is not exactly one known instruction."""
    ops = [k for k in NESTED if isinstance(e, dict) and k in e]
    return ops[0] if len(ops) == 1 else None


def leaves(when):
    """Every plain (key, want) condition inside a when, nested instructions opened up, in order."""
    for k, w in (when or {}).items():
        if isinstance(w, dict):
            op = expr_op(w)
            subs = (w.get("any") or []) if op == "any" else [w.get(op)] if op else []
            if op == "ctu" and isinstance(w.get("reset"), dict): subs = subs + [w["reset"]]
            for s in subs:
                if isinstance(s, dict):
                    yield from leaves(s)
        else:
            yield k, w


def _now(st):
    t = st.get("ticks")
    if isinstance(t, (int, float)) and not isinstance(t, bool): return int(t)
    d = st.get("day")
    if isinstance(d, (int, float)) and not isinstance(d, bool): return int(round(d * 60000))
    return None


def _duration(e):
    if isinstance(e.get("ticks"), (int, float)) and not isinstance(e.get("ticks"), bool): return int(e["ticks"])
    if isinstance(e.get("hours"), (int, float)) and not isinstance(e.get("hours"), bool): return int(round(e["hours"] * TICKS_PER_HOUR))
    return None


def _leaf(key, want, st, tagvals, rec=None, ctx=None, path=""):
    """One condition -> "T" true, "F" false, "U" unmeasured, "R" unresolved (rec(text) collects unresolved bounds)."""
    if key == "letter_matches":
        return "T" if any(str(want).lower() in (l or "").lower() for l in st.get("letter_labels", [])) else "F"
    if isinstance(want, dict):
        return _expr(key, want, st, tagvals, rec, ctx, path)
    if key in st:
        got = st.get(key)
    elif key in tagvals:           # a tag can gate a rung directly (e.g. CAVALRY_ENABLED: ">0")
        got = tagvals[key]
    else:
        return "U"          # unmeasured is not the same as false: a rung cannot fire on a missing key
    if isinstance(want, bool):
        return "T" if bool(got) == want else "F"
    if isinstance(want, (int, float)):
        return "F" if got is None or isinstance(got, bool) or got != want else "T"
    if isinstance(want, str) and want[:1] in "<>!":
        op = next(o for o in OPS if want.startswith(o)) if any(want.startswith(o) for o in OPS) else None
        ref = _bound(want[len(op):], st, tagvals) if op else None
        if ref is None:
            # an unresolved bound never passes silently: the rung does not fire and the reason is recorded
            if rec: rec("%s %s" % (key, want))
            return "R"
        if got is None or isinstance(got, bool) or not isinstance(got, (int, float)): return "F"
        g = float(got)
        return "T" if {">": g > ref, "<": g < ref, ">=": g >= ref, "<=": g <= ref, "!=": g != ref}[op] else "F"
    if isinstance(want, str):
        return "T" if str(got) == want else "F"
    return "F"


def _branch(cond, st, tagvals, rec=None, ctx=None, path=""):
    """An AND of conditions, tested in order, stopping at the first that does not hold (its state is the result)."""
    if not isinstance(cond, dict):
        return "R"
    for k, w in cond.items():
        c = _leaf(k, w, st, tagvals, rec, ctx, path + "/" + k)
        if c != "T": return c
    return "T"


def _expr(key, e, st, tagvals, rec=None, ctx=None, path=""):
    op = expr_op(e)
    if op is None:
        if rec: rec("%s %s" % (key, "not one instruction of " + "/".join(NESTED)))
        return "R"
    if op == "any":
        got = [_branch(b, st, tagvals, rec, ctx, "%s.%d" % (path, i)) for i, b in enumerate(e.get("any") or [])]
        for c in ("T", "R", "U"):
            if c in got: return c
        return "F"
    if op == "not":
        c = _branch(e.get("not"), st, tagvals, rec, ctx, path + ".0")
        return {"T": "F", "F": "T"}.get(c, c)
    # timers, counter, one-shot: the output the instruction pass computed for this scan
    return ((ctx or {}).get("out") or {}).get(path, "U")


def _instructions(when, st, tagvals, ctx, path):
    """The instruction pass: every timer / counter / one-shot in a rung moves once per scan, children first, whether
    or not an earlier condition of the rung already failed (a timer must see its input every scan)."""
    for k, w in (when or {}).items():
        if not isinstance(w, dict): continue
        p = path + "/" + k
        op = expr_op(w)
        if op is None: continue
        subs = list(enumerate(w.get("any") or [])) if op == "any" else [(0, w.get(op))]
        for i, s in subs:
            if isinstance(s, dict): _instructions(s, st, tagvals, ctx, "%s.%d" % (p, i))
        if op == "ctu" and isinstance(w.get("reset"), dict):
            _instructions(w["reset"], st, tagvals, ctx, p + ".r")
        if op not in STATEFUL: continue
        c = _branch(w.get(op), st, tagvals, None, ctx, p + ".0")
        m = dict(ctx["mem"].get(p) or {})
        m.setdefault("prev", False); m.setdefault("start", None); m.setdefault("last", None); m.setdefault("count", 0)
        now, dur, inp = ctx["now"], _duration(w), c == "T"
        if op == "ons":
            out = ("T" if inp and not m["prev"] else "F") if c in ("T", "F") else c
        elif op == "ton":
            if not inp: m["start"] = None
            elif m["start"] is None: m["start"] = now
            out = "U" if now is None or dur is None else \
                ("T" if inp and now - m["start"] >= dur else "F" if c in ("T", "F") else c)
        elif op == "tof":
            if inp: m["last"] = now
            held = m["last"] is not None and now is not None and dur is not None and now - m["last"] < dur
            out = "U" if now is None or dur is None else ("T" if inp or held else "F" if c in ("T", "F") else c)
        else:   # ctu
            r = _branch(w.get("reset"), st, tagvals, None, ctx, p + ".r") if isinstance(w.get("reset"), dict) else "F"
            if r == "T": m["count"] = 0
            elif inp and not m["prev"]: m["count"] += 1
            pre = w.get("preset")
            out = "R" if not isinstance(pre, (int, float)) or isinstance(pre, bool) else ("T" if m["count"] >= pre else "F")
        m["prev"] = inp
        ctx["mem"][p] = m
        ctx["out"][p] = out


def _holds(cond, st, tagvals=None, ctx=None, path=""):
    tagvals = tagvals or {}
    rec = lambda s: st.setdefault("unresolved_conditions", []).append(s)
    for key, want in cond.items():
        if _leaf(key, want, st, tagvals, rec, ctx, path + "/" + key) != "T": return False
    return True


def _value_of(k, w, st, tagvals):
    return w if k == "letter_matches" else st.get(k, tagvals.get(k, "unmeasured"))


def explain(g, st, tagvals):
    """The measured values behind a rung's conditions, so she can say WHY it fired. A nested instruction shows the
    measured values of the plain conditions inside it."""
    out = {}
    for k, w in (g.get("when") or {}).items():
        if isinstance(w, dict):
            out[k] = {lk: _value_of(lk, lw, st, tagvals) for lk, lw in leaves({k: w})}
        else:
            out[k] = _value_of(k, w, st, tagvals)
    return out


def _load_memory():
    try:
        m = json.load(open(MEMORY, encoding="utf-8"))
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def apply_fallbacks(book, st):
    """A sensor RimPLC measures but the bridge cannot (research_<def>, caravan_out) names the mark it replaced in the
    preset's sensor table (`fallback`). Unmeasured here, it reads that mark: the mark's value, or false when unset,
    which is what the old mark condition read."""
    for k, spec in ((book.get("sensors") or {}).items()):
        fb = spec.get("fallback") if isinstance(spec, dict) else None
        if fb and k not in st:
            st[k] = st.get(fb, False)


def rungs(book, lf):
    """Book rungs plus hers (hers replace a book rung of the same id), latches applied."""
    mine = {g["id"]: g for g in (lf.get("gates") or []) if g.get("id") and "priority" in g}
    allg = [g for g in book["gates"] if g["id"] not in mine] + list(mine.values())
    return [_latched(g) for g in allg]


def decide(st=None, every=False, book=None, lf=None, write=True, memory=None):
    """The Python engine (the fallback when RimPLC is not loaded). memory: timer/counter memory to scan against (a
    dict, updated in place on write); None = the scratch copy, saved when write is true."""
    lf = _ladder_file() if lf is None else lf
    st = st if st is not None else state()
    book = book or json.load(open(PLAYBOOK, encoding="utf-8"))
    tagvals = tags(book, st, lf)
    st["tags"] = tagvals
    if write:
        # the playbook under docs/ is canonical and never rewritten by a read; the live setpoints go machine-local
        try:
            os.makedirs(os.path.dirname(SETPOINTS), exist_ok=True)
            tmp = SETPOINTS + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"tags": tagvals, "ts": time.time()}, f, indent=1)
            os.replace(tmp, SETPOINTS)
        except Exception:
            pass
    allg = rungs(book, lf)
    # marks: numeric defaults from the book; a boolean mark nobody has set yet reads false
    for k, v in ((book.get("marks") or {}).get("defaults") or {}).items():
        st.setdefault("mark_" + k, v)
    for g in allg:
        for k, w in leaves(g.get("when")):
            if k.startswith("mark_") and isinstance(w, bool): st.setdefault(k, False)
    apply_fallbacks(book, st)
    # grace: the empire rungs wait until the opening has had START_GRACE_DAYS (the `always` rung never waits)
    gfrom = tagvals.get("GRACE_FROM_PRIORITY")
    grace = tagvals.get("START_GRACE_DAYS")
    # a rung marked disabled has an input nothing measures yet; it never fires, and the reason is kept on the state
    st["disabled_rungs"] = {g["id"]: g["disabled"] for g in allg if g.get("disabled")}
    allg = [g for g in allg if not g.get("disabled")]
    known = set((book.get("sensors") or {}).keys())
    st["unknown_keys"] = sorted({k for g in allg for k, _w in leaves(g.get("when"))
                                 if k != "letter_matches" and not k.startswith(("mark_", "alert_")) and k not in known
                                 and k not in tagvals and k not in st})
    # the instruction pass: timers, counters and one-shots move once, before any rung is tested
    mem = _load_memory() if memory is None else memory
    ctx = {"mem": {k: dict(v) for k, v in mem.items() if isinstance(v, dict)}, "out": {}, "now": _now(st)}
    for g in allg:
        _instructions(g.get("when"), st, tagvals, ctx, g["id"])
    if write:
        mem.clear(); mem.update({k: v for k, v in ctx["mem"].items() if k in ctx["out"]})
        if memory is None and (mem or os.path.exists(MEMORY)):
            try:
                os.makedirs(os.path.dirname(MEMORY), exist_ok=True)
                json.dump(mem, open(MEMORY, "w", encoding="utf-8"), indent=1)
            except Exception:
                pass
    def ok(g):
        w = g.get("when", {})
        if (isinstance(gfrom, (int, float)) and isinstance(grace, (int, float)) and g["id"] != "always"
                and gfrom <= g["priority"] < 99):
            w = dict(w); w.setdefault("day", ">%s" % grace)
        return _holds(w, st, tagvals, ctx, g["id"])
    hits = [g for g in sorted(allg, key=lambda g: g["priority"]) if ok(g)]
    for g in hits:
        g["matched"] = explain(g, st, tagvals)
    return (hits if every else hits[:1] + [g for g in hits if g["id"] == "always"][:1]), st


# ---------------------------------------------------------------------------------------------------------------
# Thin client: when the RimPLC mod is loaded, the ladder lives in the game and this file only asks it.
#
#   brain tool (unchanged)        RimPLC (rimplc/<cmd> on the bridge, or cmd in <config>/RimPLC/inbox.jsonl)
#   ladder                     -> read_ladder {top: 4}
#   ladder_set mark name value -> set_mark {name, value}
#   ladder_set tag name value  -> set_tag {name, value}             (never the owner flag: chat never reaches it)
#   ladder_set add_rung rung   -> upsert_rung {rung}
#   ladder_set remove_rung name-> remove_rung {id: name}
#   (letters looked at)        -> letters_seen {}
#
# The result text the brain sees is the same: ladder_result() returns exactly t_ladder's JSON (live_rungs with id,
# priority, matched, then; tags; my_marks; my_rungs; unknown_keys; cut at 5000 characters), and ladder_set returns
# "ladder updated: <op> <name><note>" or raises the refusal. RimPLC's numbers arrive as doubles; they are given back
# their Python form (an integral count is an int, a float key stays a float, tags take the type gates.tags() gives,
# a book rung's priority its book value). When RimPLC does not answer, everything falls back to the Python engine
# above, and after a miss RimPLC is not asked again for RIMPLC_RETRY_S seconds.
# ---------------------------------------------------------------------------------------------------------------
RIMPLC_DIR = os.environ.get("RIMPLC_DIR") or os.path.expandvars(
    r"%USERPROFILE%/AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config/RimPLC")
RIMPLC_RETRY_S = 60
_rimplc_quiet_until = [0.0]
FLOAT_KEYS = {"day", "days_of_food", "fight_ratio", "store_roofed_fraction", "lowest_health_pct", "lowest_mood",
              "outdoor_temp"}


def _unwrap(r):
    """A bridge reply -> RimPLC's result dict (structuredContent, or a JSON text content block), else None."""
    if not isinstance(r, dict):
        return None
    if isinstance(r.get("ok"), bool):
        return r
    for blk in r.get("content") or []:
        try:
            d = json.loads(blk.get("text", ""))
            if isinstance(d, dict) and isinstance(d.get("ok"), bool):
                return d
        except Exception:
            pass
    return None


def _bridge_args(cmd, a):
    """The bridge companion takes strings where the command file takes JSON values (RimPLC.BridgeTools)."""
    a = dict(a)
    if cmd in ("set_mark", "set_tag") and "value" in a:
        v = a["value"]
        a["value"] = "" if v is None else ("true" if v is True else "false" if v is False else str(v))
    if cmd in ("upsert_rung",) and not isinstance(a.get("rung"), str):
        a["rung"] = json.dumps(a.get("rung"))
    if cmd == "import" and not isinstance(a.get("json"), str):
        a["json"] = json.dumps(a.get("json"))
    if cmd == "read_state" and isinstance(a.get("keys"), list):
        a["keys"] = ",".join(a["keys"])
    return a


def _rimplc_file(cmd, args, wait_s):
    """The command-file fallback. Only used when RimPLC has made its folder (it is loaded, or was)."""
    if not os.path.isdir(RIMPLC_DIR):
        return None
    inbox, outbox = os.path.join(RIMPLC_DIR, "inbox.jsonl"), os.path.join(RIMPLC_DIR, "outbox.jsonl")
    rid = "gates-" + uuid.uuid4().hex[:10]
    before = os.path.getsize(outbox) if os.path.exists(outbox) else 0
    try:
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict({"id": rid, "cmd": cmd}, **args)) + "\n")
    except OSError:
        return None
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(0.25)
        if not os.path.exists(outbox): continue
        if os.path.getsize(outbox) < before: before = 0
        with open(outbox, encoding="utf-8", errors="replace") as f:
            f.seek(before); rows = f.read().splitlines()
        for row in rows:
            try: d = json.loads(row)
            except Exception: continue
            if d.get("id") == rid and isinstance(d.get("result"), dict):
                return d["result"]
    return None


# ---------------------------------------------------------------------------------------------------------------
# Host inputs (2026-10-13): readings only this PC has. Pushed into RimPLC with set_host each turn (remote I/O), so the
# stream rungs (dead-air, chat-first, viewer-joined, webcam-stale, idle-watchdog) can fire in the game's own engine.
# ---------------------------------------------------------------------------------------------------------------
_HOST_PROMPT_HASH = [None]


def host_inputs():
    import hashlib, tempfile, ctypes
    claude = os.path.join(ROOT, ".claude")
    out, now = {}, time.time()
    def rows(path):
        try: return [json.loads(l) for l in open(path, encoding="utf-8", errors="replace") if l.strip()][-200:]
        except (OSError, ValueError): return []
    outbox, inbox = rows(os.path.join(claude, ".studio-outbox.jsonl")), rows(os.path.join(claude, ".studio-inbox.jsonl"))
    spoke = max((r.get("ts", 0) for r in outbox if r.get("persona") == "unity"), default=0) / 1000.0
    if spoke: out["seconds_since_spoken"] = round(now - spoke, 1)
    try:
        owners = {l.strip().lower() for l in open(os.path.join(ROOT, ".local", "tw", "owner.txt"), encoding="utf-8") if l.strip()}
    except OSError:
        owners = set()
    unanswered = joins = mod = 0
    for r in inbox:
        if r.get("ts", 0) / 1000.0 <= spoke: continue
        m = re.match(r"\[twitch\] (\w+): (.*)", r.get("text") or "")
        if not m or m.group(1).lower() in owners or m.group(1).lower() == "unityplaysrimworld": continue
        if m.group(2) == "(joined the stream)": joins += 1
        else:
            unanswered += 1
            if re.search(r"(mod|repo|workshop|download|github|link)", m.group(2), re.I): mod += 1
    out.update(chat_unanswered=unanswered, new_joiners=joins, chat_asks_mod=mod > 0)
    # owner_unread: private owner lines (studio inbox rows without the "[twitch]" prefix, tools.read_owner) that no
    # outbox row answers (reply_owner writes replyTo = the owner's msg id), newer than the newest answered one and at
    # most an hour old, so a fresh start does not dig up old private messages (autopilot.gather_owner does the same)
    replied = {r.get("replyTo") for r in outbox if r.get("replyTo") is not None}
    mine = [r for r in inbox if (r.get("text") or "") and not str(r.get("text")).startswith("[twitch]")]
    last = max((r.get("id", 0) for r in mine if r.get("id") in replied), default=0)
    out["owner_unread"] = sum(1 for r in mine if r.get("id", 0) > last and r.get("id") not in replied
                              and now - r.get("ts", 0) / 1000.0 <= 3600)
    # ... plus the owner-orders FILE (the owner's Twitch-chat lines land there, and the admin panel's): unread while it
    # has grown since her last reply_owner (tools.t_reply_owner writes scratch/_orders_ack.json) and within the hour.
    # Run 5 (2026-10-14 00:26-00:40): four owner orders, the owner-message rung never live, the chop rung on top.
    try:
        _op = os.path.join(ROOT, ".local", "autopilot", "owner-orders.txt")
        _ap = os.path.join(ROOT, ".local", "autopilot", "scratch", "_orders_ack.json")
        _cur = os.path.getsize(_op)
        _ack = json.load(open(_ap, encoding="utf-8")) if os.path.exists(_ap) else {"len": 0, "ts": 0}
        # and newer than this colony's start: last colony's orders are not unread on a fresh one (run 5, attempt 5)
        try: _epoch_ts = float(json.load(open(os.path.join(ROOT, ".local", "autopilot", "scratch", "colony-epoch.json"), encoding="utf-8")).get("ts") or 0)
        except Exception: _epoch_ts = 0
        if _cur > int(_ack.get("len", 0)) and now - os.path.getmtime(_op) <= 3600 and os.path.getmtime(_op) >= _epoch_ts:
            out["owner_unread"] += 1
    except (OSError, ValueError):
        pass
    try:
        imgs = [os.path.join(claude, ".studio-images", f) for f in os.listdir(os.path.join(claude, ".studio-images"))]
        out["seconds_since_webcam"] = round(now - max(os.path.getmtime(f) for f in imgs), 1)
    except (OSError, ValueError):
        pass
    try:
        tr = os.path.join(HERE, "traces"); newest = max(os.path.getmtime(os.path.join(tr, f)) for f in os.listdir(tr))
        out["seconds_since_tool"] = round(now - newest, 1)
    except (OSError, ValueError):
        pass
    # her voice holds this lock while a line plays (unity-speak.py)
    lock = os.path.join(tempfile.gettempdir(), "unity-voice-playing.lock")
    try:
        import msvcrt
        with open(lock, "a+b") as f:
            try:
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                out["voice_playing"] = False
            except OSError:
                out["voice_playing"] = True
    except (OSError, ImportError):
        pass
    try:   # the owner is at the controls: keyboard/mouse used in the last 60 s WHILE RimWorld is the foreground window.
           # GetLastInputInfo is PC-wide, so without the foreground test the owner typing to the lead in a terminal
           # read as him playing and held her idle (2026-10-13 ledger 18:54/19:08/19:11/19:12/19:42). The bridge never
           # sends real input, so real input on the game window is his. A measured false is pushed every turn: the
           # owner-at-controls rung is not latched and drops by itself on the first push after his hands leave the game.
        class LII(ctypes.Structure): _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LII(); li.cbSize = ctypes.sizeof(LII)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            age_s = ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0
            out["owner_input_active"] = age_s < 60 and _foreground_process().startswith("rimworld")
    except (AttributeError, OSError):
        pass
    try:
        h = hashlib.sha1()
        for f in (os.path.join(HERE, "prompt.md"), PLAYBOOK):
            h.update(open(f, "rb").read())
        d = h.hexdigest()
        out["prompt_version_changed"] = _HOST_PROMPT_HASH[0] is not None and d != _HOST_PROMPT_HASH[0]
        _HOST_PROMPT_HASH[0] = d
    except (OSError, TypeError):
        pass
    return out


def push_host():
    """Send the host inputs to RimPLC (command file; the bridge has no set_host tool). Returns RimPLC's reply or None."""
    try:
        return rimplc("set_host", {"values": host_inputs()}, call=None, wait_s=2.0)
    except Exception:
        return None


def rimplc(cmd, args=None, call=None, wait_s=4.0):
    """Ask RimPLC. call = a bridge tools/call function (name, args) -> reply; tried first as rimplc/<cmd>, then the
    command file. Returns RimPLC's result dict (ok true, or ok false with refused), or None when RimPLC does not
    answer -- the caller then uses the Python engine."""
    if time.time() < _rimplc_quiet_until[0]:
        return None
    args = dict(args or {})
    if call is not None:
        try:
            r = _unwrap(call("rimplc/" + cmd, _bridge_args(cmd, args)))
        except (Exception, SystemExit):
            r = None
        if r is not None:
            return r
    r = _rimplc_file(cmd, args, wait_s)
    if r is None:
        _rimplc_quiet_until[0] = time.time() + RIMPLC_RETRY_S
    return r


def _py_num(v, like=None):
    """A number from RimPLC in its Python form: like a float -> float (the command file writes 0 for 0.0), else an
    integral float -> int (the bridge writes 4.0 for a count of 4)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    if isinstance(like, float):
        return float(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def format_ladder(hits, st, mine):
    """t_ladder's result text from a Python-engine scan (unchanged from tools.py)."""
    live = [{"id": h["id"], "priority": h["priority"], "matched": h.get("matched", {}), "then": h.get("then", [])}
            for h in hits[:4]]
    return json.dumps({"live_rungs": live, "tags": st.get("tags"), "my_marks": mine.get("marks", {}),
                       "my_rungs": [r.get("id") for r in mine.get("gates", [])],
                       "unknown_keys": st.get("unknown_keys", [])}, default=str)[:5000]


def format_rimplc_ladder(r, book=None):
    """t_ladder's result text from a RimPLC read_ladder result: the same fields, order and number forms."""
    book = book or json.load(open(PLAYBOOK, encoding="utf-8"))
    pri = {g["id"]: g["priority"] for g in book.get("gates", [])}
    like = tags(book, {"crew": [None] * 3, "home_cells": 400}, {})
    def val(k, v):
        if isinstance(v, dict): return {a: val(a, b) for a, b in v.items()}
        return _py_num(v, 0.0 if k in FLOAT_KEYS else None)
    live = []
    for h in (r.get("live_rungs") or [])[:4]:
        p = h.get("priority")
        p = pri[h.get("id")] if h.get("id") in pri and isinstance(p, (int, float)) and p == pri[h.get("id")] else _py_num(p)
        live.append({"id": h.get("id"), "priority": p,
                     "matched": {k: val(k, v) for k, v in (h.get("matched") or {}).items()},
                     "then": h.get("then", [])})
    tg = {k: _py_num(v, like.get(k)) for k, v in (r.get("tags") or {}).items()}
    marks = {k: _py_num(v) for k, v in (r.get("my_marks") or {}).items()}
    return json.dumps({"live_rungs": live, "tags": tg, "my_marks": marks, "my_rungs": list(r.get("my_rungs") or []),
                       "unknown_keys": list(r.get("unknown_keys") or [])}, default=str)[:5000]


def ladder_result(call=None, lf=None, top=4):
    """The `ladder` tool's text: RimPLC's ladder when it answers, else the Python engine. -> (text, "rimplc"|"python")"""
    r = rimplc("read_ladder", {"top": top}, call=call)
    if r is not None and r.get("ok") and isinstance(r.get("live_rungs"), list):
        return format_rimplc_ladder(r), "rimplc"
    hits, st = decide(every=True, lf=lf)
    mine = _ladder_file() if lf is None else lf
    return format_ladder(hits, st, mine), "python"


if __name__ == "__main__":
    gates, st = decide(every="--all" in sys.argv)
    print("state:", json.dumps({k: v for k, v in st.items() if k != "crew"}, default=str))
    print("crew: ", st.get("crew"))
    for g in gates:
        print("\n== RUNG %s (priority %s)" % (g["id"], g["priority"]))
        print("   why:", g.get("why", "")[:160])
        print("   matched:", json.dumps(g.get("matched", {}), default=str)[:200])
        for i, step in enumerate(g["then"], 1): print("   %d. %s" % (i, step))
        for n in g.get("never", []): print("   NEVER:", n)
