# 🛠 SETUP-README — DUNGEON MASTER: THE HUNT

> Technical setup, deployment, troubleshooting, and architecture diagrams.

> **Cross-references:** [`README.md`](./README.md) (gameplay wiki — every game system) · [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) (system design) · [`docs/ROADMAP.md`](./docs/ROADMAP.md) (phase plan) · [`docs/SKILL_TREE.md`](./docs/SKILL_TREE.md) (capability matrix) · [`docs/TODO.md`](./docs/TODO.md) (active backlog) · [`docs/FINALIZED.md`](./docs/FINALIZED.md) (completion archive)

---

## What is this

`SETUP-README.md` covers everything **operational** — how to get the game running, how it's wired internally, how to deploy, and how to debug when something breaks. The other half (gameplay loop, archetypes, tools, mechanics, image gallery) lives in [README.md](./README.md).

---

## Prerequisites

| Component | Minimum | Notes |
|---|---|---|
| **Modern browser** | Chrome 110+ / Firefox 110+ / Safari 16+ | WebGL2 + IndexedDB + ES2020 required |
| **Ollama** | 0.1.30+ | Runs the dialogue brain at `localhost:11434` |
| **Uncensored model** | Dolphin Mistral 7B (recommended) | Or any abliterated variant that won't refuse persona content |
| **8GB RAM minimum** | 16GB recommended | Model weights live in RAM while Ollama serves |
| **2GB free disk** | 8GB+ for model | Model weights + Kokoro voice weights + IDB save |
| **Internet (first run only)** | — | For Ollama model pull + Kokoro CDN weights download |

**Optional:**

| Component | Notes |
|---|---|
| **Local Stable Diffusion server** (optional) | Ships in `local-services/image-server/`. Run `scripts/install_image_gen` once (pulls torch + diffusers + a ~2GB uncensored checkpoint), then `scripts/start_image_gen` per session. Unlocks per-girl portrait images + on-demand selfies. Runs on your GPU. No API key. |
| **Local voice server** (optional) | Ships in `local-services/voice-server/`. Run `scripts/install_voice` once (pulls faster-whisper + a ~480MB Whisper-small model), then `scripts/start_voice` per session. Unlocks mic-in. GPU-first, CPU fallback available. No API key. |
| **Embedding model** (`nomic-embed-text`) | Enables memory retrieval — not required, last-N chronological memory works without it. |

---

## Install Ollama

### Windows

```powershell
# Download installer from https://ollama.com/download
# After install, open PowerShell as Administrator:
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "User")
# Restart Ollama
```

### macOS

```bash
brew install ollama
launchctl setenv OLLAMA_ORIGINS "*"
ollama serve
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
export OLLAMA_ORIGINS="*"   # add to ~/.bashrc / ~/.zshrc for persistence
ollama serve
```

**Why `OLLAMA_ORIGINS=*`?** The browser-side game makes CORS-protected `fetch` calls to `http://localhost:11434`. Without the wildcard origin Ollama rejects them with a CORS error.

---

## Pull the model

```bash
ollama pull dolphin-mistral
# Or any other uncensored model:
ollama pull dolphin-mixtral
ollama pull dolphin-llama3
```

The setup wizard (`index.html#setup`) detects available models and lets you pull one with a live progress bar inside the browser. No CLI required for normal use.

---

## Install Kokoro voice (in-browser)

Kokoro TTS runs in your browser via ONNX runtime. Model weights (~80MB) download once from a public CDN and cache forever in IndexedDB.

**Nothing to install manually.** Open `index.html#setup`, the Kokoro card auto-loads on first visit. After that it's instant.

If the CDN load fails:
1. Check browser console for the failed URL
2. Confirm your network can reach `https://huggingface.co/onnx-community/Kokoro-82M-ONNX`
3. Open in-game Settings → "Kokoro" → Force reload weights

---

## Start the local image + voice servers (optional)

Both are Python servers that ship with the game under `local-services/` and run entirely on your machine. No API key. Nothing leaves your box. The game is fully playable as text+emoji without either — turn them on when you want images and mic-in.

**Windows:**

```
scripts\install_image_gen.bat    (one-time — ~2GB SD checkpoint)
scripts\start_image_gen.bat      (per session — serves on 127.0.0.1:7860)

scripts\install_voice.bat        (one-time — ~480MB Whisper model)
scripts\start_voice.bat          (per session — serves on 127.0.0.1:7861)
```

**Linux / macOS:**

```
bash scripts/install_image_gen.sh
bash scripts/start_image_gen.sh

bash scripts/install_voice.sh
bash scripts/start_voice.sh
```

The landing-page setup wizard shows a live status pill for each server and copy-to-clipboard buttons for both commands. Once the servers are running, images + mic-in enable automatically inside the game — no restart, no reload.

**Swap the SD checkpoint:** drop any `.safetensors` into `weird/models/` and restart `start_image_gen`. Files with `xl` in the name are auto-detected as SDXL and loaded via `StableDiffusionXLPipeline` (with model-cpu-offload so they fit alongside Ollama on a 16GB card); anything else loads as SD1.5. If both an SDXL and an SD1.5 file are present, SDXL wins. The default download is RealVisXL V5.0 (~6.5GB SDXL, uncensored, ungated) — with Realistic Vision V5.1 SD1.5 (~2GB) as the fallback if the SDXL fetch fails.

If no key is provided, image features gracefully degrade — text+emoji gameplay continues to work.

---

## Run the game

### One-click launcher (Windows)

Double-click **`start.bat`** in the repo root. It:

1. Checks for Ollama on PATH, launches it in a new window with `OLLAMA_ORIGINS=*`
2. Finds a local web server (Python / Node / PHP — whichever is installed)
3. Starts serving on `http://localhost:9535`
4. Opens your default browser to the landing page

Close the server window to stop.

### One-click launcher (macOS / Linux)

```bash
./start.sh
```

Same behavior as `start.bat`.

### Manual

```bash
npx http-server . -p 8000
# or: python3 -m http.server 8000
# or any static file server
```

Then open `http://localhost:8000` in your browser.

---

## Deploy to a static host

The game is a pure static site — no build step, no bundler, plain HTML + JS + CSS. Drop the repository's files behind any static web host (or a static-pages feature of your git host) and serve them as-is; the entry point is `index.html`.

```bash
git init
git add .
git commit -m "DUNGEON MASTER: THE HUNT initial"
git branch -M main
git remote add origin <your-static-host-or-git-remote>
git push -u origin main
```

Point the host's pages/static-serve feature at the served branch and the site goes live at whatever URL your host assigns. Nothing runs on a server — Ollama is the visitor's local machine, Kokoro runs in their browser, and the local image + voice servers are Python processes the visitor runs on their own machine. No cloud AI, no API keys, no proxy.

### What's NOT deployed

- `.env` — local dev only, gitignored (rarely needed now that no cloud keys are used)
- `cache/` — user-specific local-SD image cache
- `save.json` / `server/save*.json` — save data
- `node_modules/` — Playwright (only used for screenshot tooling)

See `.gitignore`.

---

## Save / load / export / import

Everything lives in your browser's IndexedDB:

| Slot | Purpose |
|---|---|
| `main` | Active save — autosaved on every state mutation |
| `slot1` .. `slot5` | Manual save slots, named from in-game Settings |

### Export your save

Settings → Save Slots → **Export current save**. Downloads a `.json` blob.

### Import a save

Settings → Save Slots → **Import** → pick the `.json` blob → confirm overwrite.

### Factory reset

Settings → **Factory reset** → confirm. Wipes:

- All IDB save slots
- Cached Kokoro weights (you'll re-download on next visit)
- Cached local-SD images
- All localStorage UI preferences (voice toggle, last-used model, etc.)

---

## Module dependency graph

```
                          ┌──────────────────┐
                          │  storage.js      │   ← IDB primitives
                          └──────────────────┘
                                  ▲
                                  │
                          ┌──────────────────┐
                          │  state.js        │   ← reactive store + onChange
                          └──────────────────┘
                                  ▲
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌────────────────┐    ┌────────────────┐         ┌────────────────────┐
│  girl-gen.js   │    │  templates/    │         │  shop.js / hunt.js │
│  (procedural)  │    │  ollama-       │         │  capture.js        │
└────────────────┘    │  templates +   │         │  market.js etc.    │
                      │  john-arche-   │         └────────────────────┘
                      │  types.js      │                  │
                      └────────────────┘                  │
                                  │                       │
                                  ▼                       ▼
                          ┌────────────────────────────────────┐
                          │  ollama.js (streaming)             │
                          │     │                              │
                          │     └─→  delta.js (parser + apply) │
                          │              │                     │
                          │              └─→ pregnancy hook    │
                          └────────────────────────────────────┘
                                          │
                                          ▼
                          ┌──────────────────────────────────┐
                          │  imaging.js (local SD via POST)  │
                          │  pregnancy.js (gestation)        │
                          │  action-effects.js (stat spec)   │
                          │  whore-out.js (johns)            │
                          │  drug-scheduler.js (curves)      │
                          │  lifespan.js (aging)             │
                          └──────────────────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │  tick.js (1/30s)     │
                              └──────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │  router.js + ui/*    │   ← 20+ views
                              └──────────────────────┘
```

### Modules added since the diagram (2026-06-18 mega-build)

These register on `window.DMTHGame.*` (or `window.DMTHRoomPanels` / `window.DMTHDeathDossier`) and load in `game.html` in dependency order. Full per-module responsibilities are in `docs/ARCHITECTURE.md` → *New Systems & Modules*, and player-facing detail in `wiki.html`.

| New module | Loads after | Purpose |
|---|---|---|
| `js/game/progression.js` | `state.js` | DEPRAVITY level + tier gating + pay-to-unlock + ground gates |
| `js/game/sexdrive.js` | `progression.js` | player sex-drive NEED |
| `js/game/wanted.js` | `state.js` | WANTED heat axis |
| `js/game/arrest.js` | `tick.js` deps | raids / fines / jail + escape valves |
| `js/game/death.js` | `lifespan.js` | death dossier chokepoint |
| `js/game/condoms.js` | `pregnancy.js` | typed + timed condoms |
| `js/game/supply.js` | before `loot.js` | two-tier hold/dungeon supply pool |
| `js/game/loot.js` | `capture.js` | loot + passive archetype gifts |
| `js/game/toys.js` | `loot.js` | toys/implements + hold-mount |
| `js/game/transport.js` | `toys.js` | inter-dungeon + corpse transport |
| `js/game/milk.js` | `market.js` | milk economy |
| `js/game/trophies.js` | `disposal.js` | keepsake trophies + perks |
| `js/ui/charsheet.js` | `dashboard.js` | player Character Sheet (route `#charsheet`) |
| `js/ui/death-dossier-overlay.js` | `notify.js` | death dossier modal |
| `js/ui/room/panels.js` | before `room.js` | extracted captive panels |

**Added in the 2026-06-19/20 financial-underworld mega-session:**

| New module | Loads after | Purpose |
|---|---|---|
| `js/game/loanshark.js` | `tick.js` deps | loan sharks — fast cash vs deadline, compounding vig, overdue heat |
| `js/game/gigs.js` | `loanshark.js` | queueable shady gigs (rob/break-in/heist/kidnap), crew scaling |
| `js/ui/gigs-view.js` | `gigs.js` | The Hustle UI (route `#gigs`) |
| `js/ui/stores-hub-view.js` | UI layer | one-door Stores hub (route `#stores`) |
| `js/ui/property-view.js` | UI layer | Bloodland Holdings property store (dungeons + turf buyout) |
| `js/ui/clothing-store-view.js` · `player-clothing-store-view.js` | UI layer | Carcass Closet (captive outfits) · Fitting Room (player clothes) |
| `js/ui/dairy-view.js` · `gristle-view.js` | UI layer | The Dairy (milk) · The Gristle Pimp (body-part fence) |
| `js/game/player-wardrobe.js` | `wardrobe.js` | player's own outfit catalog → renders him into scene images |

Expanded existing modules: `state.js` (new persisted fields + migration backfill; Vault/pocket money model, credit cards, `escapeGovernor` day-counter, `playerCharacter.hairColor`), `tick.js` (new per-tick steps incl. condom expiry, drug self-serve, archetype gifts, supply auto-distribute, loanshark/credit accrual, **escape governor in `runEscapeRoll`** — no-first-days / weekly cooldown / global cap / sandbox-immune / 10× grace), `drug-scheduler.js` (addiction/withdrawal/OD/self-serve), `whore-out.js` (CONDOM-STOCK + JOHN-VARIETY + NPC-action range), `lifespan.js` (snuff + 5-day corpse window), `pregnancy.js` (cum-fill timer + newborn disposal), `action-effects.js` (XTOL + pool fallback + gateOf STATGATE framework), `imaging.js` (toy + corpse + ownership-mark + amputee/nugget tokens; hard face identity-lock), `game-clock.js` (pause), `config.js` (reads `dmth_kokoro_voice` / `dmth_kokoro_speed` / `dmth_ollama_temp` from settings; maxTokens 256), `kokoro.js` (keep-warm heartbeat in a hold + hard `dmth_kokoro_disabled` gate), `ollama.js` (length+completion instruction + trailing-fragment trim), `girl-gen.js` (3 new archetypes: flight-attendant / goth / bartender), `storage.js` (per-key `save.del`).

---

## State-model ER

```
Player
  ├─ wallet { money, notoriety, suspicionByLocation{} }
  ├─ inventory { itemId → qty }
  ├─ dungeons[]
  │    └─ holds[] { holdType, captiveGirlId, upgrades{} }
  ├─ properties[]
  ├─ roster[]
  │    └─ Girl
  │         ├─ visualIdentity { seed, facialDescription, defaultOutfitDescription }
  │         ├─ body { arousal, wetness, cumLoad, bruises, high, stamina, health, activeDrugs[] }
  │         ├─ mood { mood, moodEmoji, history[] }
  │         ├─ stats { intelligence, defiance, curiosity, trust, obedience, stamina,
  │         │         painTolerance, lust }
  │         ├─ bond { bondLevel 0-9, bondXP, bondDebt, milestones[] }
  │         ├─ escape { currentRisk, factors, lastAttempt }
  │         ├─ pregnancy { status, gestationDays, trimester, conceptionSource,
  │         │              johnEncounterId, outcomeHistory[], lastAbortMethod }
  │         ├─ whoreOut { enabled, rate, condomRequired, permittedActs[],
  │         │             blockedJohnTypes[], johnLedger[], sessionTotals,
  │         │             unclaimedEarnings }
  │         ├─ wardrobe[] { id, displayName, description, source, multiplier, nude? }
  │         ├─ consumables { food, water, light }
  │         ├─ captiveAffect ('mute' | 'cusser' | 'fighter' | 'submissive' |
  │         │                'agreeable' | 'bargainer' | 'catatonic')
  │         └─ archetypeTemplate
  ├─ films[]
  ├─ disposals[]
  ├─ propositioners { inbox, active, completed, repeatClients }
  ├─ slaveMarket { listed, available, recentSales }
  ├─ turns { girlId → [{role, text, ts}] }
  └─ settings { mode, activeGirlId, activeDungeonId }
```

---

## Bootstrap flow

```
index.html load
   │
   ├──► env.local.js (optional)
   ├──► config.js / storage.js / templates / catalogs
   ├──► setup/ (detector, models, ollama-repair, kokoro)
   ├──► hero + landing nav rendered
   │
   ├──► (route #home → CTA grid + IDB save detection)
   ├──► (route #setup → Ollama detection → model status → Kokoro load → local SD status → local voice status)
   │
   └──► launch click → location.href = game.html
              │
              ▼
         game.html load
              │
              ├──► state.js .load() → IDB pull → migrate if needed
              │
              ├──► If no save: route #newgame → setup wizard
              │
              ├──► All engine modules + UI views registered
              │
              ├──► router mount + first handle (route from hash)
              ├──► tick.js .start() — 30sec interval
              ├──► Kokoro auto-load (cached after first visit)
              │
              └──► Game live.
```

---

## Tick engine timeline

Every 30 seconds `tick.js#runTick()` fires the following steps in order:

```
runTick():
   1.  bumpTick()
   2.  decayConsumables() — per captive, food/water decay gated by automation tiers
   3.  runEscapeRoll()    — per captive, escape attempt probability
   4.  market.runSaleTick() — films generate passive income per tick
   5.  propositioner.shouldArriveThisTick() → enqueue new offer
   6.  slaveMarket.runBuyerTick() — NPC buyers tick in
   7.  drugs.tickAll()    — pharmacokinetic curves update high + activeDrugs list
   8.  balancing.decayTick() — notoriety slow decay
   9.  achievements.check() — unlock checks
  10.  escapeRecovery.expireTick() — on-the-run timer expiration
  11.  lifespan.tickAll() — aging + neglect evaluation + terminal state transitions
  12.  pregnancy.tickPregnancies() — gestation +7 days per tick, auto-resolve at 280
  13.  actionEffects.tickStaminaHealth() — rest regen or starvation/dehydration drain
  14.  whoreOut.runJohnTick() — per-rate arrival rolls per whored-out captive
```

---

## Imaging pipeline

```
composePrompt(girl, opts)
  │
  ├─► prefix: editorial photograph, 35mm film, full body, age N+, ...
  ├─► [if nude] nudeTokens('full' | 'accessories' | 'stripped')
  ├─► [if pregnant] pregnancyTokens(pregnancy) ← per-trimester markers
  ├─► envTokens(holdIdx) ← per-hold-specific backdrop from dungeon template's holdPrompt
  ├─► [if clothed] faceBlock + outfit description
  ├─► [if nude] faceBlock
  ├─► poseLibrary[situation] ← profile / selfie-* / capture-memorial / etc.
  ├─► drugStateTokens(body) ← per-drug visible markers (coke / weed / mdma / acid /
  │                          whiskey / ketamine / tranquilizer)
  ├─► bodyStateTokens(body) ← arousal / wetness / cumLoad / bruises
  ├─► additionalTokens
  └─► suffix: shallow DOF, cinematic, no watermark
        │
        ▼
   enforceFullBody() / sanitizePrompt()
        │
        ▼
   clampSeed(seed, girl.id) ← deterministic seed fallback via djb2 hash
        │
        ▼
   renderImage() → POST http://127.0.0.1:7860/sdapi/v1/txt2img
        │
        ▼
   queuedFetch() ← single-slot serializer + 429 backoff
        │
        ▼
   IDB cache.put(prompt-hash → blob)
        │
        ▼
   return { url, cached, directUrl }
```

**Why slot 2.5 for pregnancy?** Image models attenuate tokens at the tail; pregnancy bump is a high-priority visual that must NOT be buried. Same logic for nudity (position 2) and per-hold environment (position 3).

---

## Voice pipeline

```
Mic input
  │
  ├─► MediaRecorder API (browser)
  │     │
  │     ▼
  │  POST http://127.0.0.1:7861/stt (local faster-whisper)
  │     │
  │     ▼
  │  user-in textarea autofilled → Send
  │
Ollama streaming response
  │
  ├─► streamed chunks → log
  │     │
  │     ▼
  │  on stream-end:
  │     │
  │     ├─► extractDelta() → applyDelta()
  │     │
  │     └─► clean text → strip asterisk actions
  │              │
  │              ▼
  │       DMTHVoiceQueue.enqueue(text, voiceId, speed)
  │              │
  │              ├─► splitSentences() on `. ! ? …`
  │              │
  │              └─► sequential play with pipelined-generation:
  │                  while sentence N plays, sentence N+1 generates
  │                  Kokoro speaks via in-browser ONNX inference
```

---

## Ollama prompt-assembly stack

`buildSystemPrompt()` composes the system prompt for each Ollama turn as a 4-overlay stack:

```
┌────────────────────────────────────────────────────────────────┐
│ 1.  BASE_SLUT — global slut scaffolding                       │
│     • Speech-first rule (spoken line ≥ 8 words, *action* trails)│
│     • Sexualized body-part references tier-shaped by Stockholm │
│     • Chemical state effects per active drug                  │
│     • DELTA BLOCK schema + TAGS — IMPORTANT SEXUAL-ACT MARKERS │
│       (vaginal-cum tags drive pregnancy conception roll)       │
└────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌────────────────────────────────────────────────────────────────┐
│ 2.  ARCHETYPE overlay — pre-capture identity                  │
│     unity / library / club / street / sorority / gym / barista│
│     / office / waitress / model / nurse                       │
│     • Speech patterns, kinks, drug preferences, outfit prefs  │
└────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌────────────────────────────────────────────────────────────────┐
│ 3.  CAPTIVE_AFFECT overlay — response to captivity            │
│     mute / cusser / fighter / submissive / agreeable /        │
│     bargainer / catatonic                                     │
│     • HOW she resists / submits / negotiates                  │
│     • Orthogonal to archetype — they compose                  │
└────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌────────────────────────────────────────────────────────────────┐
│ 4.  MODE overlay                                              │
│     sexy / hurtme / sexy_with_damage                          │
└────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌────────────────────────────────────────────────────────────────┐
│ 5.  SCENE prompt — per-situation scaffolding                  │
│     room_regular / first_encounter / capture_attempt /        │
│     bond_milestone / disposal / propositioner / etc.          │
└────────────────────────────────────────────────────────────────┘

+ Per-turn CONTEXT block:
  • Body state (arousal / wetness / cum / bruises / high / stamina / health)
  • Stockholm rating L0..L9
  • Active drugs
  • Pregnancy status + gestation day
  • Recent johns (last 5 — she may reference them)
  • Last 5 turns
  • Memory (last-N chronological or embedding-based retrieval)
```

---

## Local development

```bash
# Serve the static files (any local server works)
npx http-server . -p 8000
# or
python3 -m http.server 8000
```

The `.env` → `js/env.local.js` sync pattern that shipped with the old Pollinations-key flow is no longer wired: `js/env.local.js` and `js/env.example.js` were removed when local SD replaced Pollinations, because no cloud keys need syncing. `scripts/sync-env.ps1` remains for any advanced override you might want (e.g. `LOCAL_IMAGE_ENDPOINT=http://192.168.1.42:7860` for a networked SD box), but it's no longer required by the launchers.

Both `.env` and `js/env.local.js` are gitignored. `.env` is the single source of truth — never edit `js/env.local.js` by hand; the launcher will overwrite it.

If you launch the static server manually (without `start.bat` / `start.sh`), run the sync first:

```powershell
# Windows
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync-env.ps1
```

```bash
# Mac/Linux — extract the sync_env function from start.sh, or just call start.sh once
bash start.sh
```

### Regenerating README screenshots

```bash
npm install playwright
npx playwright install chromium
node scripts/screenshots.mjs
```

The script walks the entire game, sends a real Ollama turn, requests a real local-SD selfie, and waits for each to actually complete before screenshotting. Non-headless so you can watch it play. Requires the local SD server to be running.

---

## Troubleshooting

### "Ollama HTTP 400 — model does not support chat"

Your model's blob files got deleted (Windows Storage Sense / Defender / CCleaner are common culprits). The manifest is still on disk so detection reports green, but the actual weights are gone.

**Fix:** In-game → catch the error → click 🔧 Repair → hard-repair path deletes the stale manifest then re-pulls fresh. No CLI needed.

If the in-game repair fails:

```bash
ollama rm dolphin-mistral
ollama pull dolphin-mistral
```

### "Local SD server not reachable"

The image server hasn't started, or it's on a different port. Check:
1. `scripts/start_image_gen` window is still running.
2. `curl http://127.0.0.1:7860/sdapi/v1/options` returns JSON (not a connection error).
3. Nothing else is listening on 7860 (`netstat -ano | findstr :7860` on Windows).

### "no checkpoint in models/"

The install script downloaded RealVisXL V5.0 (or Realistic Vision V5.1 as fallback) but the file isn't where the server expects. Verify `weird/models/*.safetensors` exists. Drop any `.safetensors` into that folder and restart `start_image_gen`.

### "STT cannot use the GPU"

faster-whisper resolves cuBLAS/cuDNN lazily by name. The install script installs `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` wheels and `voice_server.py` puts them on PATH at boot. If GPU init still fails the server falls back to CPU int8 automatically (slower but works everywhere).

If you have no key the game silently falls back to the legacy free endpoint — rate-limited but functional.

### "Kokoro autoplay blocked"

Browsers block audio playback until the page receives at least one user gesture. Click anywhere on the page once, then voice will play normally.

### "Game won't load — empty screen"

1. Open DevTools console
2. Look for the first red error
3. Common: cached `js/env.local.js` from old version — `localStorage.clear()` + hard refresh
4. Common: stale IDB save migration failure — Settings → Factory reset

### "CORS error on Ollama fetch"

`OLLAMA_ORIGINS=*` isn't set. See [Install Ollama](#install-ollama) above.

### "No images appearing"

1. Check that the local SD server is running (`scripts/start_image_gen` window still open).
2. Check the landing-page status pill for the image server — it should read something like "Ready · RealVisXL_V5.0_fp16.safetensors · cuda" (or `realistic-vision-v51.safetensors` if you're on the SD1.5 fallback).
3. Game also writes detailed logs to console — open DevTools.

### "Save got corrupted"

```js
// In DevTools console:
indexedDB.deleteDatabase('dungeon_master_the_hunt')
location.reload()
```

This wipes the save entirely — only do it if there's no other recovery path. Export your save first if possible.

---

## CI / hooks

The repo's `.gitignore` excludes local-dev tooling folders, `.env`, `cache/`, `node_modules/`, `save.json`, screenshots cache, the visitor's `models/` folder (with the multi-GB SD checkpoint + Whisper model files), and the Python virtualenv (`.venv/`, `__pycache__/`). The shipping branch contains only the static-client code + the Python server sources under `local-services/` + the installer / launcher scripts.

No CI configured (this is a static-client browser game with no build step). All verification is manual: open the page, play the loop, watch the dev console.

---

## Where to go next

- **Gameplay wiki + every system** — [README.md](./README.md)
- **Architecture deep-dive** — `docs/ARCHITECTURE.md`
- **Active backlog** — `docs/TODO.md`
- **Phase plan** — `docs/ROADMAP.md`
- **Capability matrix** — `docs/SKILL_TREE.md`

---

*Local-first. Your machine, your rules. No telemetry. No accounts. No cloud.*
