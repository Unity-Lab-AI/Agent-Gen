"""Local mission control: one page, no cloud. Processes on the left, a chat to the local model on the right.

Owner, 2026-10-10, verbatim: *"we arent do tests we are saving the colony from collap[pse and getting
everything abouteverything to work locally so yeah all those scrpt shells and shit i need my own precoss
organizer and adnmmin chat locally to talk to the local model you are handing the whole show over to"*.

    python stream/admin.py               # http://127.0.0.1:4318/

What the page gives:
  * every service, live: UP with its pid or DOWN, with start / stop / restart per service and for all of them
  * the colony in one line, straight off the bridge: time speed, the three colonists, letters, alerts
  * ORDERS -- what you type is appended to .local/autopilot/owner-orders.txt, which the autopilot reads at the
    top of every turn as binding orders. That is the handover channel: you type, it obeys, it keeps playing.
  * CHAT -- goes into the private owner channel (the same one as the Persona Studio window), so the brain that
    is playing reads it as an OWNER block and answers with reply_owner, never on stream. If no brain answers within
    ADMIN_BRAIN_WAIT seconds (autopilot not running) the local model answers directly instead, and says so.

Nothing here reaches the internet. It binds to 127.0.0.1 only, it never touches RimWorld itself, and the
orders file and the private owner inbox are the only things it writes.
"""
import http.server, importlib.util, json, os, re, secrets, socket, subprocess, sys, threading, urllib.request, uuid

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


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QA = os.path.join(ROOT, ".local", "qa")
ORDERS = os.path.join(ROOT, ".local", "autopilot", "owner-orders.txt")
SERVICES = os.path.join(HERE, "services.py")
PORT = int(os.environ.get("ADMIN_PORT", "4318"))
MODEL = os.environ.get("ADMIN_MODEL", os.environ.get("UNITY_VOICE_LLM", "unity-local"))

bspec = importlib.util.spec_from_file_location("b", os.path.join(QA, "bridge.py"))
bridge = importlib.util.module_from_spec(bspec); bspec.loader.exec_module(bridge)
cspec = importlib.util.spec_from_file_location("camp", os.path.join(QA, "camp.py"))
camp = importlib.util.module_from_spec(cspec); cspec.loader.exec_module(camp)
_lock = threading.Lock()
# Every change (GO, colony, services, orders, chat) needs this run's token; it lives only in the page this server
# hands out, so another local program or a web page in a browser cannot fire them. Reads stay open.
TOKEN = secrets.token_urlsafe(24)
HOSTS = {"127.0.0.1:%d" % PORT, "localhost:%d" % PORT}

def svc(action, name=None):
    cmd = [sys.executable, SERVICES, action] + ([name] if name else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return (r.stdout + r.stderr).strip()

def colony():
    try:
        port, tok = bridge.endpoint()
        s = socket.create_connection(("127.0.0.1", port), timeout=10); buf = bytearray()
        bridge.exchange(s, buf, "session/hello", {"token": tok, "bridgeVersion": "admin/1",
                                                  "platform": "windows", "launchId": str(uuid.uuid4())})
        def call(n, a=None):
            r = bridge.exchange(s, buf, "tools/call", {"name": n, "arguments": a or {}}); r = r.get("result", r)
            return r.get("structuredContent", r) if isinstance(r, dict) else r
        players = [c for c in call("rimworld/list_colonists").get("colonists", []) if c.get("factionIsPlayer")]
        crew = [(c["name"], c["position"]["x"], c["position"]["z"], c.get("job"), bool(c.get("drafted")))
                for c in players]
        # days of food, measured -- the famine that nearly went unnoticed on 2026-10-09 was invisible on
        # this page while the alert list said nothing. Meals are 0.9 nutrition, raw is 0.05, 1.6 per pawn/day.
        # read by cell, never by selecting a pawn: polling this page must not steal the player's selection
        # the sweep reads the map on screen, so it only counts when that is the home map; otherwise unknown
        nut = None
        home = camp.home_map(players)
        try:
            on_home = any(c.get("mapId") == home for c in
                          call("rimworld/list_colonists", {"currentMapOnly": True}).get("colonists", []))
        except Exception:
            on_home = False
        if crew and on_home:
          nut = 0.0
          minx, minz, maxx, maxz = camp.camp_rect(players, home)
          try:
            for x in range(minx, maxx + 1, 22):
                for z in range(minz, maxz + 1, 22):
                    try:
                        cells = call("rimworld/get_cells_info", {"x": x, "z": z, "width": 22, "height": 22}).get("cells", [])
                    except (Exception, SystemExit):
                        cells = []               # a block past the map edge reads as empty
                    for c in cells:
                        for th in c.get("things", []):
                            d = th.get("defName") or ""
                            if d.startswith("Meal"): nut += th.get("stackCount", 1) * 0.9
                            elif d.startswith(("Raw", "Meat", "Pemmican", "Kibble")): nut += th.get("stackCount", 1) * 0.05
          except Exception:
            nut = None
        return {"crew": crew,
                "days_of_food": (round(nut / (1.6 * max(1, len(crew))), 2) if nut is not None
                                 else "unknown (home map not on screen)"),
                "letters": [l.get("label") for l in call("rimworld/list_letters").get("letters", [])],
                "alerts": [a.get("label") for a in call("rimworld/list_alerts").get("alerts", [])][:8],
                "ticks": call("rimworld/get_game_info").get("ticksGame")}
    except Exception as e:
        return {"error": str(e)[:120]}

INBOX = os.path.join(ROOT, ".claude", ".studio-inbox.jsonl")
OUTBOX = os.path.join(ROOT, ".claude", ".studio-outbox.jsonl")


def _last_id(path):
    last = 0
    try:
        for line in open(path, encoding="utf-8"):
            try:
                last = max(last, int(json.loads(line).get("id", 0)))
            except (ValueError, AttributeError):
                pass
    except OSError:
        pass
    return last


def ask_brain(text, wait=float(os.environ.get("ADMIN_BRAIN_WAIT", "90"))):
    """Owner, 2026-10-12: "train in twitch versus admin conversions fromn the admin panel". The panel chat goes into
    the same private owner channel as the Persona Studio window: a row without the "[twitch]" prefix, which the
    playing brain reads as an OWNER block and answers with reply_owner (never on stream). Returns her reply, or
    None when no brain answered in time (autopilot not running), so the caller can fall back."""
    import time
    with _lock:
        msg_id = _last_id(INBOX) + 1
        with open(INBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": msg_id, "ts": int(time.time() * 1000), "persona": "unity",
                                "text": text.strip()[:600]}) + "\n")
    end = time.time() + wait
    while time.time() < end:
        try:
            for line in open(OUTBOX, encoding="utf-8"):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("replyTo") == msg_id and r.get("text"):
                    return r["text"]
        except OSError:
            pass
        time.sleep(1.5)
    return None


def ask(text):
    reply = ask_brain(text)
    if reply is not None:
        return reply
    return "(the playing brain did not answer -- autopilot not running; the local model answered instead)\n" + ask_direct(text)


def ask_direct(text):
    """The panel chat IS Unity talking to the owner -- not a bare model. Owner, 2026-10-10, after it answered
    'update your representation images more often' with invented translation and recipe jobs: "this dont seem
    right". So: her persona, the live colony, and the tail of her orders go in as the system prompt; anything
    the owner asks her to DO is also appended to owner-orders.txt so the player acts on it next turn."""
    try:
        col = colony()
        facts = ("no game loaded" if col.get("error") else
                 "colonists: " + ", ".join("%s (%s)" % (c[0], c[3]) for c in col.get("crew", [])) +
                 "; days of food: %s; letters: %s" % (col.get("days_of_food"), ", ".join(col.get("letters", [])) or "none"))
    except BaseException:                         # the bridge helper raises SystemExit when the game is not up
        facts = "colony unknown right now"
    try:
        orders = open(ORDERS, encoding="utf-8").read()[-2500:]
    except Exception:
        orders = ""
    system = ("You are Unity: 25, emo goth, sharp, funny, real. You are streaming RimWorld on Twitch and you play the "
              "colony yourself through the game; this private panel is the owner talking to you directly. You are "
              "NOT a general assistant: never invent past tasks, users, translations, recipes or anything you did not "
              "do. Talk only about the stream, the colony and yourself. If the owner gives you an instruction, say "
              "plainly that you will do it and how, in a few short lines. Live colony: " + facts +
              ". Your standing orders (latest): " + orders)
    if any(w in text.lower() for w in ("update", "make", "do ", "set ", "build", "explore", "go ", "stop", "start",
                                        "always", "never", "more", "less", "send", "post", "use ")):
        with open(ORDERS, "a", encoding="utf-8") as f:
            f.write("\n- OWNER, typed in the panel chat (binding next turn): " + text.strip()[:400] + "\n")
    body = {"model": MODEL, "system": system, "prompt": text, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"num_ctx": int(os.environ.get("UNITY_VOICE_NUM_CTX", "8192")), "num_predict": 220, "temperature": 0.7}}
    req = urllib.request.Request(os.environ.get("UNITY_VOICE_URL", "http://127.0.0.1:11435") + "/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read()).get("response", "").strip()

PAGE = """<!doctype html><meta charset=utf-8><title>Unity mission control</title>
<style>
 body{background:#0d0d10;color:#e6e6ea;font:14px/1.5 Consolas,monospace;margin:0;padding:14px}
 h1{font-size:15px;letter-spacing:.14em;color:#ff5fa2;margin:0 0 12px;text-transform:uppercase}
 .wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 .card{background:#15151b;border:1px solid #2a2a35;border-radius:8px;padding:12px}
 table{width:100%;border-collapse:collapse}td{padding:3px 4px;border-bottom:1px solid #22222c}
 .up{color:#6ee7a0}.down{color:#ff6b6b}
 button{background:#23232e;color:#e6e6ea;border:1px solid #39394a;border-radius:5px;padding:3px 9px;cursor:pointer;font:12px Consolas,monospace}
 button:hover{border-color:#ff5fa2}
 textarea{width:100%;background:#0f0f14;color:#e6e6ea;border:1px solid #2a2a35;border-radius:6px;padding:8px;font:13px Consolas,monospace}
 pre{white-space:pre-wrap;background:#0f0f14;border:1px solid #22222c;border-radius:6px;padding:8px;max-height:260px;overflow:auto;margin:8px 0 0}
 .row{display:flex;gap:6px;margin-top:6px}.row button{flex:0 0 auto}
 small{color:#8a8a9a}
</style>
<h1>Unity mission control &mdash; local only</h1>
<div class=wrap>
 <div>
  <div class=card><b>Processes</b> <small>&nbsp;start / stop / restart</small>
   <div id=svc>loading...</div>
   <div class=row>
    <button onclick=all('start')>start all</button>
    <button onclick=all('stop')>stop all</button>
    <button onclick=all('restart')>restart all</button>
    <button onclick=refresh()>refresh</button>
   </div>
   <pre id=svcout></pre>
  </div>
  <div class=card style=margin-top:14px><b>Colony</b><pre id=colony>loading...</pre></div>
  <div class=card style=margin-top:14px id=popcard><b>Pop-up waiting for you</b>
   <pre id=popup>none</pre></div>
  <div class=card style=margin-top:14px><b>Needs the game window</b>
   <small>&nbsp;these only work when RimWorld is the front window</small>
   <pre id=queue>loading...</pre></div>
 </div>
 <div>
  <div class=card style=border-color:#ff5fa2><b>Ready?</b>
   <small>&nbsp;Unity waits here. Tell her what you want tonight, then GO -- the game launches, the stream goes live, the colony starts.</small>
   <textarea id=want rows=2 placeholder="e.g. company start, equator tile, food first, no raids on stream tonight"></textarea>
   <div class=row><button onclick=go()>GO</button>
    <button onclick=newColony() title="Abandon this colony and start a fresh company colony, set up the owner's way">NEW COLONY</button></div>
   <pre id=goout></pre>
  </div>
  <div class=card style=margin-top:14px><b>Orders to the autopilot</b>
   <small>&nbsp;appended to owner-orders.txt, binding on its next turn</small>
   <textarea id=ord rows=4 placeholder="e.g. get everything inside and close the east wall before anything else"></textarea>
   <div class=row><button onclick=sendOrder()>send order</button></div>
   <pre id=ordout></pre>
  </div>
  <div class=card style=margin-top:14px><b>Chat with the local model</b>
   <textarea id=msg rows=4 placeholder="ask it anything"></textarea>
   <div class=row><button onclick=sendChat()>send</button></div>
   <pre id=chat></pre>
  </div>
 </div>
</div>
<script>
const TOKEN='__ADMIN_TOKEN__';
async function j(u,b){const r=await fetch(u,b?{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':TOKEN},body:JSON.stringify(b)}:{});return r.json()}
async function refresh(){
 const d=await j('/api/status');let h='<table>';
 for(const s of d.services){h+=`<tr><td>${s.name}</td><td class=${s.up?'up':'down'}>${s.up?'UP '+s.pids.join(' '):'DOWN'}</td>`
  +`<td style=text-align:right><button onclick="one('start','${s.name}')">start</button> `
  +`<button onclick="one('stop','${s.name}')">stop</button></td></tr>`}
 document.getElementById('svc').innerHTML=h+'</table>';
 const c=d.colony;document.getElementById('colony').textContent=c.error?('bridge: '+c.error):
  ('tick '+c.ticks+'   food: '+c.days_of_food+' days'+(c.days_of_food<1?'  << LOW':'')+'\\n'+c.crew.map(p=>p[0]+' ('+p[1]+','+p[2]+') '+p[3]+(p[4]?' DRAFTED':'')).join('\\n')
   +'\\n\\nletters: '+(c.letters.join(', ')||'none')+'\\nalerts: '+(c.alerts.join(', ')||'none'));
}
async function all(a){document.getElementById('svcout').textContent='working...';
 const d=await j('/api/svc',{action:a});document.getElementById('svcout').textContent=d.out;refresh()}
async function one(a,n){document.getElementById('svcout').textContent='working...';
 const d=await j('/api/svc',{action:a,name:n});document.getElementById('svcout').textContent=d.out;refresh()}
async function go(){const t=document.getElementById('want').value.trim();
 const d=await j('/api/go',{text:t});document.getElementById('goout').textContent=d.out}
async function newColony(){if(!confirm('Start a brand-new colony? The current one is abandoned.'))return;
 const d=await j('/api/newcolony',{});document.getElementById('goout').textContent=d.out}
async function sendOrder(){const t=document.getElementById('ord').value.trim();if(!t)return;
 const d=await j('/api/order',{text:t});document.getElementById('ordout').textContent=d.out;document.getElementById('ord').value=''}
async function sendChat(){const t=document.getElementById('msg').value.trim();if(!t)return;
 const box=document.getElementById('chat');box.textContent+=(box.textContent?'\\n\\n':'')+'you: '+t+'\\n...';
 document.getElementById('msg').value='';
 const d=await j('/api/chat',{text:t});
 box.textContent=box.textContent.replace(/\\n\\.\\.\\.$/,'\\n')+ (d.reply||d.error||'');box.scrollTop=box.scrollHeight}
async function queue(){const d=await j('/api/queue');
 document.getElementById('queue').textContent=(d.jobs||[]).map(x=>'* '+x).join('\\n')+'\\n\\nlast run:\\n'+(d.log||'')}
async function popup(){const d=await j('/api/popup');const box=document.getElementById('popup');
 const card=document.getElementById('popcard');
 if(!d||!d.type){box.textContent='none';card.style.borderColor='#2a2a35';return}
 box.textContent=(d.type||'')+'\\n\\n'+((d.text||[]).join('\\n'))+'\\n\\noptions: '+((d.options||[]).join(' | '));
 card.style.borderColor='#ff5fa2'}
refresh();queue();popup();setInterval(refresh,6000);setInterval(queue,15000);setInterval(popup,5000);
</script>
"""

def _go_note():
    """GO is only acted on by the keep-going loop; say so plainly when that loop is not running."""
    try:
        up = any(l.split()[:2] == ["keepgoing", "UP"] for l in svc("status").splitlines())
    except Exception:
        up = False
    return "" if up else " -- but keepgoing is DOWN, so nothing happens until it starts (start keepgoing above)"

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a): pass

    def _host_ok(self):
        # a page on another site that rebinds its name to 127.0.0.1 still sends its own Host
        return (self.headers.get("Host") or "") in HOSTS

    def _allowed(self):
        if not self._host_ok(): return False
        origin = self.headers.get("Origin")
        if origin and origin.split("://", 1)[-1] not in HOSTS: return False
        return secrets.compare_digest(self.headers.get("X-Admin-Token") or "", TOKEN)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "wrong host"})
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.replace("__ADMIN_TOKEN__", TOKEN).encode("utf-8"), "text/html; charset=utf-8")
        if self.path == "/api/popup":
            # Owner, 2026-10-10: "and i got a p t u didnt mention it so i denyed" -- a pop-up the guard cannot
            # decide was only written to a flag file and spoken on stream, so the owner had to answer it blind.
            # It belongs where they are actually looking.
            f = os.path.join(ROOT, ".claude", ".popup.json")
            try:
                return self._send(200, json.load(open(f, encoding="utf-8")))
            except Exception:
                return self._send(200, {})
        if self.path == "/api/queue":
            # what still needs the game window, and what the queue said last time it ran
            jobs, log = [], ""
            try:
                src = open(os.path.join(QA, "cursor-jobs.py"), encoding="utf-8").read()
                m = re.search(r"JOBS = \[(.+?)\]", src, re.S)
                if m: jobs = re.findall(r'\("([^"]+)"', m.group(1))
            except Exception as e: jobs = ["(cannot read cursor-jobs.py: %s)" % str(e)[:60]]
            try:
                log = "".join(open(os.path.join(QA, "_svc_cursorjobs.log"), encoding="utf-8", errors="replace").readlines()[-8:])
            except Exception: log = "(the queue has not run yet -- it waits for RimWorld to be the front window)"
            return self._send(200, {"jobs": jobs, "log": log})
        if self.path == "/api/status":
            out = svc("status")
            services = []
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] in ("UP", "DOWN"):
                    services.append({"name": parts[0], "up": parts[1] == "UP", "pids": parts[2:]})
            return self._send(200, {"services": services, "colony": colony()})
        return self._send(404, {"error": "no"})

    def do_POST(self):
        if not self._allowed():
            return self._send(403, {"out": "refused: reload the panel page (it was opened before this panel restarted)",
                                    "error": "refused"})
        n = min(int(self.headers.get("Content-Length") or 0), 65536)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: body = {}
        if self.path == "/api/go":
            # Owner, 2026-10-10: "when it starts up it should ask me if im ready to start the stream and game
            # and what i want not just random do everything". This is the answer: GO plus tonight's directive.
            want = (body.get("text") or "").strip()
            with open(os.path.join(QA, "_go.request"), "w", encoding="utf-8") as f: f.write(want or "go")
            if want:
                with open(ORDERS, "a", encoding="utf-8") as f:
                    f.write(chr(10) + "- TONIGHT, from the owner at GO: " + want + chr(10))
            return self._send(200, {"out": "GO received" + (" -- tonight: " + want if want else "") + _go_note()})
        if self.path == "/api/newcolony":
            # owner: "i dont know how to call it u have to do it and tell me how for next time" -- one button
            with open(os.path.join(QA, "_new_colony.request"), "w", encoding="utf-8") as f:
                f.write("Async Industries" + chr(10) + "force")
            return self._send(200, {"out": "new colony requested -- she announces it and the setup runs within a minute"})
        if self.path == "/api/svc":
            if body.get("action") == "start" and not body.get("name"):
                # the owner's "start all" means GO: game, stream, colony -- not just "services already up"
                if not os.path.exists(os.path.join(QA, "_go.request")):
                    with open(os.path.join(QA, "_go.request"), "w", encoding="utf-8") as f: f.write("go")
                    return self._send(200, {"out": "GO received -- launching the stream, then the game, then the colony" + _go_note()})
            with _lock:
                return self._send(200, {"out": svc(body.get("action", "status"), body.get("name"))})
        if self.path == "/api/order":
            text = (body.get("text") or "").strip()
            if not text: return self._send(400, {"out": "empty"})
            with open(ORDERS, "a", encoding="utf-8") as f:
                f.write("\n- OWNER, typed in mission control: " + text + "\n")
            return self._send(200, {"out": "order added; the autopilot reads it at the top of its next turn"})
        if self.path == "/api/chat":
            try: return self._send(200, {"reply": ask(body.get("text", ""))})
            except Exception as e: return self._send(200, {"error": str(e)[:200]})
        return self._send(404, {"error": "no"})

print("mission control on http://127.0.0.1:%d/  (local only, model=%s)" % (PORT, MODEL))
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
