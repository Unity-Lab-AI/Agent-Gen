"""One switch for the whole stream: start everything, stop everything, or see what is up.

Owner, 2026-10-10, verbatim: *"still dont have the streamer script working with a easy start stop for it so i
can stop everything and start it with one press only here in the game files"*. Double-click
`Stream Start.cmd` or `Stream Stop.cmd` in the repo root, or run this directly:

    python stream/services.py start     # start every service that is not already running
    python stream/services.py stop      # stop every one of them
    python stream/services.py status    # one line each: UP with its pid, or DOWN
    python stream/services.py restart

Each service is matched by its own command line, so a service already running by any other route is
recognised and never started twice. Nothing here touches RimWorld itself -- the game is the owner's to launch
and to close.
"""
import importlib.util, json, os, re, subprocess, sys, time

# Owner, 2026-10-10: "im getting alot of system cmd openings while im doing stuff". Every helper this script
# spawns -- powershell for the process table, python for a spoken line -- was flashing its own console over
# whatever the owner was doing. One shim, applied to this process, makes every child windowless.
import subprocess as _sp, os as _os
if _os.name == "nt":
    _CF = 0x08000000                       # CREATE_NO_WINDOW
    _run = _sp.run
    def _run_nowin(*a, **k):
        k["creationflags"] = k.get("creationflags", 0) | _CF
        return _run(*a, **k)
    _sp.run = _run_nowin
    _Popen = _sp.Popen
    class _PopenNoWin(_Popen):
        def __init__(self, *a, **k):
            k["creationflags"] = k.get("creationflags", 0) | _CF
            super().__init__(*a, **k)
    _sp.Popen = _PopenNoWin


# detaching differs per platform: Windows wants creationflags, posix wants its own session
DETACH = ({'creationflags': 0x00000200 | 0x08000000} if os.name == 'nt' else {'start_new_session': True})

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QA = os.path.join(ROOT, ".local", "qa")
PY = sys.executable
# pythonw.exe runs without a console window at all -- same interpreter, no black box
PYW = (os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
       if os.name == 'nt' and os.path.exists(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))
       else sys.executable)
NODE = "node"

# name, the fragment that identifies it in a command line, how to start it
SERVICES = [
    ("studio",      ".claude/tools/persona-studio.cjs", [NODE, os.path.join(ROOT, ".claude/tools/persona-studio.cjs")]),
    ("face",        ".claude/tools/unity-face-sd.py",   [PYW, os.path.join(ROOT, ".claude/tools/unity-face-sd.py")]),
    ("twitch",      ".claude/tools/twitch-bridge.cjs",  [NODE, os.path.join(ROOT, ".claude/tools/twitch-bridge.cjs")]),
    ("host",        ".local/qa/stream-host.py",         [PYW, "-u", os.path.join(QA, "stream-host.py")]),
    ("popups",      ".local/qa/popup-guard.py",         [PYW, os.path.join(QA, "popup-guard.py")]),
    ("clock",       ".local/qa/clock-guard.py",         [PYW, "-u", os.path.join(QA if "QA" in globals() else HERE, "clock-guard.py")]),
    ("heat",        ".local/qa/heat-guard.py",          [PYW, os.path.join(QA, "heat-guard.py")]),
    ("camdir",      ".local/qa/cam-director.py",        [PYW, os.path.join(QA if "QA" in globals() else HERE, "cam-director.py")]),
    ("followcrew",  ".local/qa/follow-crew.py",         [PYW, os.path.join(QA if "QA" in globals() else HERE, "follow-crew.py")]),
    # ("cursorjobs",  ".local/qa/cursor-jobs.py",         [PYW, os.path.join(QA, "cursor-jobs.py")]),
    ("keepgoing",   ".local/qa/keep-playing.py",        [PYW, "-u", os.path.join(QA if "QA" in globals() else HERE, "keep-playing.py")]),
    # her own voice, version 2 (models/unity-voice-v2, the emotional-range retrain the owner approved 2026-10-13 after
    # the A/B) served once on :5123; unity-speak.py posts every line to it, no fallback. v1 stays in models/unity-voice.
    ("voice",       "models/unity-voice-v2/serve.py",   [PYW, "-u", os.path.join(ROOT, "models/unity-voice-v2/serve.py")]),
    ("autopilot",   ".local/autopilot/autopilot.py",    [PYW, "-u", os.path.join(ROOT, ".local/autopilot/autopilot.py"), "--num-gpu", os.environ.get("AUTOPILOT_NUM_GPU", "0")]),
    ("admin",       "stream/admin.py",                  [PYW, "-u", os.path.join(HERE, "admin.py")]),
]
# Runs once, pins the overlay window topmost and exits -- fired on start, never reported as a service.
ONE_SHOTS = [[PYW, os.path.join(ROOT, ".claude/tools/unity-overlay.py")]]

# Owner, 2026-10-10: "wtf actually it should of already started did you start everything up correctly with
# the start .bat and .sh? form a dead state?" -- a dead state means the GAME too. It is started if missing,
# and it is never stopped by the switch: a run in progress is the owner's, not ours.
# RimWorld 1.7 (Waylith, Steam's unstable branch) ships RimWorld.exe; 1.6 shipped RimWorldWin64.exe.
# the folder's real casing: 1.7 (Waylith) launched from "...\common\Rimworld" failed to find hundreds of Core textures
# (red X pawns and items, 2026-10-13); launched from "...\common\RimWorld" it loaded clean
RW_DIR = r"C:/Program Files (x86)/Steam/steamapps/common/RimWorld"
RW_IMAGE = "RimWorld" if os.path.exists(os.path.join(RW_DIR, "RimWorld.exe")) else "RimWorldWin64"
START_ONLY = [
    # borderless window at the screen's size, never exclusive fullscreen: owner, 2026-10-13, "the game is not properly
    # running in the background, i cant see my desktop when tabbing out of it" -- Prefs.xml said fullscreen True, so
    # alt-tab swapped the display instead of showing the desktop. Unity's own flags win over the prefs every launch.
    ("rimworld", RW_IMAGE + ".exe", [os.path.join(RW_DIR, RW_IMAGE + ".exe"), "-screen-fullscreen", "0", "-popupwindow"], RW_DIR),
]

# Not python or node, so they are matched and started by their own executables.
EXTRAS = [
    ("obs", "obs64.exe", [os.path.expandvars(r"%USERPROFILE%/OBS-Portable/bin/64bit/obs64.exe"),
                          "--portable", "--disable-updater", "--minimize-to-tray",
                          # owner, 2026-10-10: "the steream is offline u need to get to work" --
                          # launching OBS is not streaming; it has to be told to go live.
                          *(["--startstreaming"] if os.environ.get("GO_LIVE") == "1" else []),
                          # owner, 2026-10-10: "i keep getting the obs studio did not shut down properly
                          # error on screen i press run in safe mode" -- that prompt appears because OBS was
                          # force-killed. Suppress the prompt, and stop OBS gracefully below.
                          "--disable-shutdown-check"],
     os.path.expandvars(r"%USERPROFILE%/OBS-Portable/bin/64bit")),
    ("twitchui", "twitch-profile", [os.path.expandvars(r"%LOCALAPPDATA%/ms-playwright/chromium-1223/chrome-win64/chrome.exe"),
                                    "--user-data-dir=" + os.path.join(ROOT, ".local/twitch-profile"),
                                    "--remote-debugging-port=9333", "--no-first-run",
                                    # the stream's own Twitch page plays the broadcast back; muted so the owner hears
                                    # her once (owner 2026-10-13: "im hearing two feeds")
                                    "--mute-audio",
                                    # Owner, 2026-10-10: a Twitch picture-in-picture prompt interrupted them and they
                                    # denied it blind. Nothing here should ever ask the owner for a permission.
                                    "--disable-features=AutoPictureInPicture,AutoPictureInPictureVideoHeuristics",
                                    "--deny-permission-prompts", "--disable-notifications",
                                    "--new-window", "https://www.twitch.tv/"], None),
]

# Killed by name on stop. The model runner and the game are here because neither is a child in the
# command-line table: Ollama spawns llama-server itself, and the game is its own process. Owner, 2026-10-10:
# "stop.bat properly kills everything becasue you didnt have that working".
KILL_BY_NAME = ["llama-server", "ollama", "ollama app", "obs64", RW_IMAGE]

# NEVER killed, no matter what matches: the owner's own browsers. Owner, 2026-10-10: "you dont fuck with my
# browsers you shit put them back". Only the Twitch window this switch itself started may be closed, and it
# is identified by the profile directory this repo owns.
PROTECT_NAMES = ["chrome", "msedge", "firefox", "brave", "opera", "vivaldi"]
OUR_BROWSER_MARK = "twitch-profile"

OLLAMA = os.path.expandvars(r"%LOCALAPPDATA%/Programs/Ollama/ollama.exe")
if not os.path.exists(OLLAMA): OLLAMA = "ollama"
MODELS = ["dolphin3:8b", "qwen3:8b", "qwen3.6:35b"]         # pulled from the registry: the voice base and the player
BRAIN_DIR = os.path.join(ROOT, "models", "unity-brain")   # her one brain + its README (git-ignored weights)
BRAIN_STATE = os.path.join(ROOT, "training", "models", "unity-brain")   # apply stamps + the owner's line-writer choice
if not os.path.exists(os.path.join(BRAIN_DIR, "unity-brain.gguf")):
    BRAIN_DIR = BRAIN_STATE = os.path.join(ROOT, "training", "models")
# Unity's one brain (training/BRAIN_PLAN.md): its base is pulled only once a trained brain has been downloaded
if os.path.exists(os.path.join(BRAIN_DIR, "unity-brain.gguf")):
    MODELS.append("qwen3.5:9b")
# Ollama on a 16 GB card shared with RimWorld, OBS and the Twitch window: flash attention and an 8-bit KV cache
# roughly halve the context's VRAM with no audible change in her lines. Takes effect when Ollama next starts.
# one slot: Ollama reports "model architecture does not currently support parallel requests" for qwen35, so
# OLLAMA_NUM_PARALLEL=2 did nothing (2026-10-13). Her turns stay fast only while the game leaves the GPU room.
OLLAMA_ENV = {"OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0"}


def brain_env():
    """Env for every service once the brain is applied: it plays on the GPU with a 32K context (her longest turns
    plus the tool list fit in ~24K), and -- only when its eval beat or matched today's voice (brain-voice.ok,
    written by training/apply.py) -- every voice caller asks it too, so one model sits on the GPU, not two."""
    if not os.path.exists(os.path.join(BRAIN_STATE, "unity-brain.gguf.applied")):
        return {}
    env = {"AUTOPILOT_MODEL": "unity-brain", "AUTOPILOT_NUM_CTX": "32768"}
    if os.path.exists(os.path.join(BRAIN_STATE, "brain-voice.ok")):
        env.update(OLLAMA_URL="http://127.0.0.1:11434", UNITY_VOICE_URL="http://127.0.0.1:11434", UNITY_VOICE_LLM="unity-brain",
                   UNITY_VOICE_NUM_CTX="32768")   # same context as the player, so Ollama never reloads between them
    return env
CUSTOM = ["unity-local"]                                    # built on this machine (training/apply.py), never pulled
VOICE = "unity-local"

def deps():
    """Bring up what the models need before any service starts.

    Owner, 2026-10-10, verbatim: "it needs to start up the api and shit needed too for the model to run it all
    and all needed models". So: the Ollama server, every model the stack uses (pulled in the background if one
    is missing), and the voice model preloaded so the first line out is not a cold start. The RimBridge API
    lives inside RimWorld, which the owner launches -- nothing here starts the game.
    """
    import urllib.request
    def api(path, data=None, timeout=8):
        req = urllib.request.Request("http://127.0.0.1:11434" + path,
                                     data=(json.dumps(data).encode() if data else None),
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout).read()
    try:
        api("/api/version"); print("ollama      already up")
    except Exception:
        log = open(os.path.join(QA, "_svc_ollama.log"), "ab", buffering=0)
        subprocess.Popen([OLLAMA, "serve"], stdout=log, stderr=log, env=dict(os.environ, **OLLAMA_ENV),
                         **DETACH)
        for _ in range(40):
            time.sleep(1)
            try: api("/api/version"); break
            except Exception: pass
        print("ollama      started")
    have = subprocess.run([OLLAMA, "list"], capture_output=True, text=True).stdout
    names = {ln.split()[0] for ln in have.splitlines()[1:] if ln.split()}
    def present(m):
        return m in names or (":" not in m and m + ":latest" in names)
    for m in CUSTOM:
        print("model       %s %s" % (m, "present" if present(m) else
                                    "MISSING -- built locally from a Modelfile or training/apply.py, it cannot be pulled"))
    pulls = []
    for m in MODELS:
        if present(m):
            print("model       %s present" % m)
        else:
            log = open(os.path.join(QA, "_svc_pull_%s.log" % m.replace(":", "_")), "ab", buffering=0)
            pulls.append((m, subprocess.Popen([OLLAMA, "pull", m], stdout=log, stderr=log,
                                              **DETACH)))
            print("model       %s pulling" % m)
    # the shells below are built on these bases, so apply waits for every pull -- bounded, never forever
    deadline = time.time() + int(os.environ.get("PULL_WAIT_S", "3600"))
    for m, pr in pulls:
        try:
            rc = pr.wait(timeout=max(1, deadline - time.time()))
            print("model       %s %s" % (m, "pulled" if rc == 0 else "pull FAILED (exit %d)" % rc))
        except subprocess.TimeoutExpired:
            print("model       %s still pulling after the wait -- apply runs without it, it retries next start" % m)
    # the voice gets its OWN Ollama on 11435 (owner, live: "she is cycling through the smae fucking responses"):
    # on the shared server every voice line queued behind the 35B player and timed out, so she fell back to a
    # small fixed pool. Two servers, two queues; the voice never waits on the player.
    def vapi(path, data=None, timeout=8):
        req = urllib.request.Request("http://127.0.0.1:11435" + path,
                                     data=(json.dumps(data).encode() if data else None),
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout).read()
    try:
        vapi("/api/version"); print("ollama-voice already up")
    except Exception:
        log = open(os.path.join(QA, "_svc_ollama_voice.log"), "ab", buffering=0)
        subprocess.Popen([OLLAMA, "serve"], stdout=log, stderr=log, env=dict(os.environ, OLLAMA_HOST="127.0.0.1:11435", **OLLAMA_ENV),
                         **DETACH)
        for _ in range(40):
            time.sleep(1)
            try: vapi("/api/version"); break
            except Exception: pass
        print("ollama-voice started on 11435")
    # Unity's trained shells (training/models/*.gguf) go into Ollama before anything warms or starts; a no-op
    # once applied (owner: "when its done it all auto applies and can run with start.bat")
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "training", "apply.py")], capture_output=True,
                           text=True, timeout=3600)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            print("shells      NOT fully applied (exit %d) -- the previous models stay; it retries next start" % r.returncode)
    except Exception as e:
        print("shells      apply skipped (%s)" % str(e)[:60])
    be = brain_env()
    if be.get("UNITY_VOICE_LLM"):
        try:
            api("/api/generate", {"model": "unity-brain", "prompt": "hi", "stream": False, "think": False, "keep_alive": -1,
                                  "options": {"num_ctx": 32768, "num_predict": 1}}, timeout=300)
            print("model       unity-brain warm (plays and speaks; the voice server stays empty)")
        except Exception as e:
            print("model       unity-brain warm-up skipped (%s)" % str(e)[:40])
        return
    try:
        vapi("/api/generate", {"model": VOICE, "prompt": "hi", "stream": False, "think": False, "keep_alive": -1,
                               "options": {"num_ctx": 8192, "num_predict": 1}}, timeout=180)
        print("model       %s warm on the voice server" % VOICE)
    except Exception as e:
        print("model       %s voice warm-up skipped (%s)" % (VOICE, str(e)[:40]))
    return
    try:
        api("/api/generate", {"model": VOICE, "prompt": "hi", "stream": False, "think": False, "keep_alive": -1,
                              "options": {"num_ctx": 8192, "num_predict": 1}}, timeout=180)
        print("model       %s warm" % VOICE)
    except Exception as e:
        print("model       %s warm-up skipped (%s)" % (VOICE, str(e)[:40]))

WINDOWS = os.name == "nt"

def _ps_lines(pattern):
    """(pid, command line) for every process whose command line matches, on Windows or Linux/macOS."""
    if WINDOWS:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '%s' } | "
                              "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }" % pattern],
                             capture_output=True, text=True).stdout
    else:
        out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout
        keep = []
        for line in out.splitlines():
            line = line.strip()
            if not line: continue
            pid, _, args = line.partition(" ")
            if re.search(pattern, args): keep.append("%s	%s" % (pid, args))
        out = chr(10).join(keep)
    return out

def running():
    """{fragment: [pid, ...]} for every python/node process whose command line carries a fragment."""
    out = _ps_lines("python|node")

    found = {}
    for line in out.splitlines():
        if "\t" not in line: continue
        pid, cmd = line.split("\t", 1)
        cmd = cmd.replace("\\", "/")
        for _, frag, _start in SERVICES:
            if frag in cmd:
                found.setdefault(frag, []).append(int(pid))
    # the extras are not python or node: ask for them by image name
    out2 = _ps_lines("obs64|chrome|chromium|^" + RW_IMAGE + r"\.exe$")
    for line in out2.splitlines():
        if "	" not in line: continue
        pid, cmd = line.split("	", 1); cmd = cmd.replace("\\", "/")
        low = cmd.lower()
        if any(n in low for n in PROTECT_NAMES) and OUR_BROWSER_MARK not in low:
            continue                     # the owner's own browser: never ours to touch
        for _, frag, _c, _cwd in EXTRAS + START_ONLY:
            if frag in cmd: found.setdefault(frag, []).append(int(pid))
    return found

def status():
    found = running()
    for name, frag, _c, _cwd in START_ONLY + EXTRAS:
        pids = found.get(frag, [])
        print("%-11s %s" % (name, ("UP   " + " ".join(map(str, pids))) if pids else "DOWN"))
    for name, frag, _ in SERVICES:
        pids = found.get(frag, [])
        print("%-11s %s" % (name, ("UP   " + " ".join(map(str, pids))) if pids else "DOWN"))
    return found

def announce(line):
    """One short line to chat -- owner, 2026-10-10: "tell chat whats up too / not the details tho"."""
    say = os.path.join(ROOT, ".claude", "tools", "unity-say.py")
    try:
        subprocess.Popen([PY, say, line], cwd=ROOT,
                         **DETACH,
                         env=dict(os.environ, UNITY_NO_GLANCE="1"))
    except Exception:
        pass

def start(only=None):
    if only in (None, "autopilot"):
        try: os.remove(AUTOPILOT_HOLD)
        except OSError: pass
    found = running()
    env = dict(os.environ, PYTHONUNBUFFERED="1", STUDIO_PERSIST="1", UNITY_OWN_VOICE="1",
               # her pod-trained voice speaks at natural pace; the old 1.2 stretch was for the too-fast local test voice
               # (owner 2026-10-13: "what just playewd was 1/5th too slow")
               UNITY_VOICE_LENGTH_SCALE=os.environ.get("UNITY_VOICE_LENGTH_SCALE", "1.0"))
    be = brain_env()
    env.update(be)
    if os.environ.get("TWITCH_CHANNEL") is None: env["TWITCH_CHANNEL"] = "unityplaysrimworld"
    for name, frag, cmd in SERVICES:
        if only and name != only: continue
        if found.get(frag):
            print("%-11s already up (%s)" % (name, found[frag][0])); continue
        if name == "autopilot" and be:               # the brain runs on the GPU, not the CPU like the 35B did
            # no --num-gpu at all: num_gpu is a load-time option, and the warm-up and her voice lines never send it --
            # a play turn that asks for a different value can make Ollama reload the brain (the 2026-10-13 hang)
            cmd = cmd[:-2] + ([ "--num-gpu", os.environ["AUTOPILOT_NUM_GPU"]] if os.environ.get("AUTOPILOT_NUM_GPU") else [])
        log = open(os.path.join(QA, "_svc_%s.log" % name), "ab", buffering=0)
        subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=log,
                         **DETACH, env=env)
        print("%-11s started" % name); time.sleep(0.6)
    for name, frag, cmd, cwd in EXTRAS:
        if only and name != only: continue
        if name == "obs" and os.environ.get("GO_LIVE") != "1":
            # OBS opens ONCE, at GO, already streaming -- never opened early and relaunched (that made two)
            print("%-11s waiting for GO" % name); continue
        if found.get(frag): print("%-11s already up (%s)" % (name, found[frag][0])); continue
        if not os.path.exists(cmd[0]): print("%-11s SKIPPED (not installed: %s)" % (name, cmd[0])); continue
        log = open(os.path.join(QA, "_svc_%s.log" % name), "ab", buffering=0)
        subprocess.Popen(cmd, cwd=cwd or ROOT, stdout=log, stderr=log,
                         **DETACH, env=env)
        print("%-11s started" % name); time.sleep(1.0)
    if only: return                       # one service: no overlay, no game, no panel, no bridge report
    for cmd in ONE_SHOTS:
        if os.path.exists(cmd[-1]):
            log = open(os.path.join(QA if "QA" in dir() else HERE, "_svc_oneshot.log"), "ab", buffering=0)
            subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=log, **DETACH)
            print("%-11s fired" % "overlay")
    for name, frag, cmd, cwd in START_ONLY:
        if os.environ.get("GO_LIVE") != "1":
            print("%-11s waiting for GO (owner, 2026-10-10: \"it should ask me if im ready to start the stream and game\")" % name); continue
        if found.get(frag): print("%-11s already up (%s)" % (name, found[frag][0])); continue
        if not os.path.exists(cmd[0]): print("%-11s SKIPPED (not installed: %s)" % (name, cmd[0])); continue
        subprocess.Popen(cmd, cwd=cwd or ROOT, **DETACH)
        print("%-11s launched (never stopped by this switch)" % name); time.sleep(8)
    # the panel opens once, on the full start (start.bat) -- not on every single-service start or restart, which
    # opened a new "mission control" tab each time a helper was revived (owner: "why does mission control tab keep
    # constantly opening?")
    OPEN_ADMIN = os.environ.get("NO_ADMIN_PAGE") != "1" and only is None
    if OPEN_ADMIN:
        url = "http://127.0.0.1:%s/" % os.environ.get("ADMIN_PORT", "4318")
        try:
            if WINDOWS:
                subprocess.Popen(["cmd", "/c", "start", "", url], **DETACH)
            else:
                subprocess.Popen(["xdg-open", url], **DETACH)
            print("%-11s opened %s" % ("adminpage", url))
        except Exception as e:
            print("%-11s could not open the panel (%s)" % ("adminpage", str(e)[:50]))
    # the game's own API lives inside RimWorld, which stays the owner's to launch
    try:
        bspec = importlib.util.spec_from_file_location("b", os.path.join(QA, "bridge.py"))
        bb = importlib.util.module_from_spec(bspec); bspec.loader.exec_module(bb); bb.endpoint()
        print("rimbridge   UP   (RimWorld is running and the API answers)")
    except Exception:
        print("rimbridge   DOWN (launch RimWorld yourself -- this switch never touches the game)")

AUTOPILOT_HOLD = os.path.join(QA, "_autopilot.hold")   # while it exists keep-going does not restart the player

def stop_one(name):
    """Stop ONE named service and nothing else (OBS asked to close, never killed)."""
    if name == "autopilot":
        # run 3 (2026-10-13 22:08): the player stopped by hand came back within a minute -- keep-going restarts a DOWN
        # player. A hand-stop leaves a hold file that keep-going honours; `start autopilot` lifts it.
        try: open(AUTOPILOT_HOLD, "w").write(str(int(time.time())))
        except OSError: pass
    frag = next((f for n, f, *_ in SERVICES + EXTRAS + START_ONLY if n == name), None)
    if frag is None: print("no service called", name); return
    pids = running().get(frag, [])
    if not pids: print("%-11s already down" % name); return
    # the two bridge clients stop GRACEFULLY: a flag they read between turns, then up to 90 s for the process to leave on
    # its own with its socket closed. A hard kill mid-request crashed the game (run 5, 2026-10-14 02:00:28: RimBridge's
    # GabpServer threw "Connection is not active" answering the killed client; the 1.7 engine treats that as fatal).
    flag = {"autopilot": os.path.join(ROOT, ".local", "autopilot", "scratch", "_stop.flag"),
            "keepgoing": os.path.join(QA, "_keepgoing.stop")}.get(name)
    if flag:
        try: open(flag, "w").write(str(int(time.time())))
        except OSError: pass
        for _ in range(90):
            time.sleep(1)
            if not running().get(frag): break
        if not running().get(frag):
            try: os.remove(flag)
            except OSError: pass
            print("%-11s stopped (graceful)" % name); return
        print("%-11s did not stop on request in 90 s -- killing it" % name)
        pids = running().get(frag, [])
    if WINDOWS:
        verb = "$null = $pr.CloseMainWindow()" if name == "obs" else "Stop-Process -Id $p -Force"
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "foreach ($p in %s) { try { $pr = Get-Process -Id $p -ErrorAction Stop; %s } catch {} }"
                        % (",".join(map(str, pids)), verb)], capture_output=True, text=True)
    else:
        for p in pids:
            try: os.kill(p, 15)
            except Exception: pass
    print("%-11s stopped (%s)" % (name, " ".join(map(str, pids))))

GRACE_S = int(os.environ.get("STOP_GRACE_S", "45"))   # how long owned apps get to close before the name sweep

def _alive(image):
    if not WINDOWS:
        return subprocess.run(["pgrep", "-f", image], capture_output=True).returncode == 0
    return image.lower() in subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s.exe" % image],
                                           capture_output=True, text=True).stdout.lower()

def graceful_close():
    """Close what we own the polite way first: OBS ends the broadcast over its websocket and is asked to close,
    the game is saved over the bridge and asked to close. The name sweep in stop() is only the fallback for
    whatever is still up after GRACE_S seconds."""
    c = obs_ws()
    if c is not None:
        try:
            if c.get_stream_status().output_active:
                c.stop_stream(); print("obs         stream stopped over the websocket")
        except Exception as e:
            print("obs         websocket stop failed (%s)" % str(e)[:40])
    try:
        r = subprocess.run([PY, os.path.join(QA, "bridge.py"), "call", "rimworld/save_game",
                            json.dumps({"saveName": "Unity-autosave"})], cwd=ROOT, capture_output=True, text=True,
                           timeout=120)
        ok = r.returncode == 0 and '"success": false' not in (r.stdout or "").lower()
        print("rimworld    %s" % ("saved as Unity-autosave" if ok else "not saved (bridge down or refused)"))
    except Exception as e:
        print("rimworld    save skipped (%s)" % str(e)[:40])
    if WINDOWS:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process obs64,%s -ErrorAction SilentlyContinue | ForEach-Object { " % RW_IMAGE +
                        "$null = $_.CloseMainWindow() }"], capture_output=True, text=True)
    t0 = time.time()
    while time.time() - t0 < GRACE_S and (_alive("obs64") or _alive(RW_IMAGE)):
        time.sleep(1)
    left = [n for n in ("obs64", RW_IMAGE) if _alive(n)]
    print("closed gracefully" if not left else "still up after %ds, falling back to the name sweep: %s"
          % (GRACE_S, " ".join(left)))

def stop():
    graceful_close()
    # the model runner first: it holds the GPU and it is nobody's child in the command-line table
    if WINDOWS:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process %s -ErrorAction SilentlyContinue | Stop-Process -Force"
                        % ",".join("'%s'" % n for n in KILL_BY_NAME)], capture_output=True, text=True)
    else:
        for n in KILL_BY_NAME:
            subprocess.run(["pkill", "-f", n], capture_output=True, text=True)
    print("stopped by name:", " ".join(KILL_BY_NAME))
    found = running()
    pids = sorted({p for frag, lst in found.items() for p in lst})
    if not pids:
        print("nothing to stop"); return
    if WINDOWS:
        # OBS has to be asked to close, not killed: a forced kill is what makes it offer safe mode next launch.
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process obs64 -ErrorAction SilentlyContinue | ForEach-Object { "
                        "$null = $_.CloseMainWindow() }; Start-Sleep 4"],
                       capture_output=True, text=True)
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "foreach ($p in %s) { try { $pr = Get-Process -Id $p -ErrorAction Stop; "
                        "if ($pr.Name -eq 'obs64') { $null = $pr.CloseMainWindow() } else { Stop-Process -Id $p -Force } } catch {} }"
                        % ",".join(map(str, pids))],
                       capture_output=True, text=True)
    else:
        for p in pids:
            try: os.kill(p, 15)
            except Exception: pass
    print("stopped", len(pids), "processes:", " ".join(map(str, pids)))
    # prove the GPU actually came back, rather than assuming it did
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20)
        if r.stdout.strip(): print("gpu after stop:", r.stdout.strip().splitlines()[0])
    except Exception:
        pass

RW_PREFS = os.path.expandvars(r"%USERPROFILE%/AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config/Prefs.xml")

def windowed_prefs():
    """RimWorld re-applies Prefs.xml at startup, so `-screen-fullscreen 0 -popupwindow` alone still came up exclusive
    fullscreen (owner, 2026-10-13: "its still playing in fullscreen i cant see my desktop and have no way to minimizae
    the game"). Write fullscreen False into the prefs right before the launch; the flags keep the window borderless."""
    try:
        if not os.path.exists(RW_PREFS): return
        txt = open(RW_PREFS, encoding="utf-8").read()
        new = re.sub(r"<fullscreen>\s*True\s*</fullscreen>", "<fullscreen>False</fullscreen>", txt)
        if new != txt:
            open(RW_PREFS, "w", encoding="utf-8").write(new); print("rimworld    prefs: fullscreen -> False (borderless window)")
    except OSError as e:
        print("rimworld    prefs not changed (%s)" % str(e)[:60])

def game():
    """Launch the game only. Called by keep-playing once the owner has said GO."""
    windowed_prefs()
    found = running()
    for name, frag, cmd, cwd in START_ONLY:
        if found.get(frag): print("%-11s already up (%s)" % (name, found[frag][0])); return
        if not os.path.exists(cmd[0]): print("%-11s SKIPPED (not installed)" % name); return
        subprocess.Popen(cmd, cwd=cwd or ROOT, **DETACH); print("%-11s launched" % name)

def obs_ws():
    """OBS's own websocket (127.0.0.1:4455) -- scene switches and stream start without restarting OBS."""
    import socket as _so
    try:
        _so.create_connection(("127.0.0.1", 4455), timeout=1).close()   # not up: say nothing, no traceback
    except OSError:
        return None
    try:
        import obsws_python as obs
        return obs.ReqClient(host="127.0.0.1", port=4455, timeout=4)
    except Exception:
        return None

def golive():
    """Go live. Called by keep-playing once the owner has said GO.

    Owner, live: "twich shows network error that should never happen" -- closing OBS ends the broadcast and every
    viewer sees a network error. If OBS is already up (a soft restart keeps it), switch back to Live and make
    sure it is streaming; only a cold start launches it."""
    # the BRB countdown ends at GO: run 3 (2026-10-13 21:25) the file set for the break stayed on disk and the host kept
    # telling the live stream "back in 96 minutes" (owner: "she keeps saying be back in 96 minuites stf?")
    try: os.remove(os.path.join(ROOT, ".local", "obs", "_brb_until"))
    except OSError: pass
    c = obs_ws()
    if c is not None:
        try:
            c.set_current_program_scene("Live")
            if not c.get_stream_status().output_active:
                c.start_stream()
            # the overlay page may have been dead when OBS started (owner, live: "our whole twich hud is mia");
            # a browser source never retries on its own, so reload it every time we go live
            try: c.press_input_properties_button("Unity overlay", "refreshnocache")
            except Exception: pass
            print("obs         already up -- back on Live, streaming, overlay reloaded")
            return
        except Exception as e:
            print("obs         websocket failed (%s) -- relaunching" % str(e)[:40])
    os.environ["GO_LIVE"] = "1"
    if WINDOWS:
        # asked to close (a forced kill makes OBS offer safe mode); wait until it is really gone
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process obs64 -ErrorAction SilentlyContinue | ForEach-Object { $null = $_.CloseMainWindow() }"],
                       capture_output=True, text=True)
        subprocess.run(["taskkill", "/IM", "obs64.exe"], capture_output=True, text=True)
        for _ in range(20):
            time.sleep(1)
            if "obs64" not in subprocess.run(["tasklist"], capture_output=True, text=True).stdout: break
        else:
            # still there (tray ignores close): force it; --disable-shutdown-check stops the safe-mode prompt
            subprocess.run(["taskkill", "/F", "/IM", "obs64.exe"], capture_output=True, text=True); time.sleep(2)
    else:
        subprocess.run(["pkill", "-f", "obs"], capture_output=True, text=True); time.sleep(3)
    found = running()
    for name, frag, cmd, cwd in EXTRAS:
        if name != "obs": continue
        log = open(os.path.join(QA if "QA" in globals() else HERE, "_svc_obs.log"), "ab", buffering=0)
        # the layout lives in OBS's own files and OBS is closed here: write it before every launch
        subprocess.run([PY, os.path.join(ROOT, ".local", "obs", "obs-fit-16x9.py")], capture_output=True, text=True)
        # a stale crash sentinel makes OBS stop on a safe-mode question and never stream; clear it
        import shutil
        shutil.rmtree(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(cmd[0]))),
                                   "config", "obs-studio", ".sentinel"), ignore_errors=True)
        # the command was built at import, before GO_LIVE was set -- add the flag here
        if "--startstreaming" not in cmd: cmd = list(cmd) + ["--startstreaming"]
        subprocess.Popen(cmd, cwd=cwd or ROOT, stdout=log, stderr=log, **DETACH)
        print("obs         relaunched LIVE")

LOCK = os.path.join(QA, "_svc_control.lock")

def control_lock(wait_s=900, stale_s=1800, takeover_s=None):
    """One process-control action at a time: two starts racing the same scan each launch their own copy.
    A lock older than stale_s belongs to a dead run and is taken over. A stop never waits in silence (owner,
    2026-10-13: "i ran stop.bat and it didnt work! kill all!" -- it sat on the lock the start window still held):
    it says whose lock it is at once and takes it over after takeover_s seconds."""
    t0 = time.time(); said = False
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            import atexit
            def _release():
                try:
                    if open(LOCK).read().strip() == str(os.getpid()): os.remove(LOCK)
                except OSError: pass
            atexit.register(_release)
            return
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(LOCK)
                holder = open(LOCK).read().strip()
                if age > stale_s: os.remove(LOCK); continue
                if takeover_s is not None and age > takeover_s:
                    print("taking the control lock over from pid %s (%.0f s old)" % (holder, age)); os.remove(LOCK); continue
                if not said:
                    print("waiting for another start/stop (pid %s, lock %.0f s old)%s" % (holder, age,
                          " -- it will be taken over in %d s" % takeover_s if takeover_s is not None else " -- Ctrl-C to abort"), flush=True); said = True
            except OSError:
                continue
            if time.time() - t0 > wait_s:
                print("another start/stop is still running -- gave up waiting"); raise SystemExit(1)
            time.sleep(1)

cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
if cmd != "status": control_lock(takeover_s=10 if cmd == "stop" else None)
if cmd == "game": game(); raise SystemExit
if cmd == "golive": golive(); raise SystemExit
ONE = sys.argv[2].lower() if len(sys.argv) > 2 else None   # a name means THAT service only, never the rig
if cmd == "start" and ONE:
    start(ONE)
elif cmd == "stop" and ONE:
    stop_one(ONE)
elif cmd == "restart" and ONE:
    stop_one(ONE); time.sleep(2); start(ONE)
elif cmd == "start":
    deps(); start(); print("---"); status()
    if os.environ.get("NO_ANNOUNCE") != "1" and os.environ.get("GO_LIVE") == "1":
        announce("fact: the stream is live and the colony is back")
elif cmd == "stop":
    announce("fact: the stream is ending for now"); time.sleep(3); stop()
elif cmd == "restart":
    # owner: the stream must never drop for a restart -- OBS stays live on the BRB scene, the rest restarts
    c = obs_ws()
    if c is not None:
        try: c.set_current_program_scene("BRB"); print("obs         on BRB, still streaming")
        except Exception: pass
    announce("fact: a short reset, the stream stays up")
    keep = ("obs64", "twitch-profile")
    names = [n for n in KILL_BY_NAME if n != "obs64"]
    if WINDOWS:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process %s -ErrorAction SilentlyContinue | Stop-Process -Force" % ",".join("'%s'" % n for n in names)],
                       capture_output=True, text=True)
    found = running()
    pids = sorted({pp for frag, lst in found.items() if not any(k in frag for k in keep) for pp in lst})
    for pp in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pp)], capture_output=True, text=True) if WINDOWS else os.kill(pp, 15)
        except Exception: pass
    print("stopped", len(pids), "processes (OBS and the Twitch window kept)")
    time.sleep(2); deps(); start(); print("---"); status()
else: status()
