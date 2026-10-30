# Stream switch

One press each, nothing to remember. The presses live in the **Backrooms root**:

| Platform | Start | Stop | Panel |
|---|---|---|---|
| Windows | `windows\start.bat` | `windows\stop.bat` | `windows\admin.bat` |
| Linux / macOS | not supported -- the rig is Windows-only; `linux/*.sh` only print that and exit | | |

All of them call `stream/services.py`, the engine (tracked here). `.local/qa/services.py` and
`.local/qa/admin.py` are thin wrappers that run the `stream/` files, not copies; the old root
`Stream Start.cmd` / `Stream Stop.cmd` and `Unity Plays RimWorld.cmd` just call the `windows\*.bat` pair, so
there is exactly one way the rig comes up and goes down. Start/stop/restart take a lock
(`.local/qa/_svc_control.lock`), so two presses never race each other into double launches.

**Panel token.** Every button in the panel that changes something (GO, new colony, services, orders, chat)
carries a token made fresh each time the panel server starts, and requests must come addressed to
`127.0.0.1`/`localhost` on the panel port. Reading status stays open. After the panel restarts, reload the
page once -- an old tab gets "refused: reload the panel page".

**Models.** `dolphin3:8b`, `qwen3:8b` (the voice base) and `qwen3.6:35b` are pulled if missing; `unity-local`
is built on this machine and is only reported, never pulled. A failed `training/apply.py` is printed as
NOT applied, and the previous models stay. A GO left on disk for more than three hours is dropped at startup.

**Start** brings up Ollama and both models (the voice pre-warmed), OBS, the Twitch window, the studio, the
webcam, chat, the host voice, the guards, the click queue, Unity the player, and the admin panel at
`http://127.0.0.1:4318/` (its chat is the private owner channel: the playing brain answers it with `reply_owner`, never on stream; the local model answers directly only when the autopilot is not running). Then she **asks** -- out loud and in the panel's Ready? card -- what you want
tonight. **GO** in the panel makes that binding, launches RimWorld, takes OBS live, and arms the company
colony. Nothing goes live before GO.

**Stop** closes what it owns gracefully first -- OBS ends the broadcast over its websocket and is asked to close, the
game is saved as `Unity-autosave` over the bridge and asked to close -- and only what is still up after
`STOP_GRACE_S` (45 s) is killed by name (`llama-server`, `ollama`, `obs64`, `RimWorldWin64`); then it sweeps the services,
then prints the GPU so you can see the memory came back. It never touches your browsers.

Each service logs to `.local/qa/_svc_<name>.log`. Status any time: `python stream/services.py status`.

## What the autopilot is allowed to touch

Enforced in code, under the model, in `.local/autopilot/guards.py` -- the model cannot talk its way past it:

- **The game, through the bridge and the mod's own automation channel only.** An explicit allowlist of
  bridge calls. A second filter rejects anything matching lua, script, debug, mod, reorder, load_game,
  main_menu, god_mode, spawn or compile even if someone widens the allowlist later. UI clicks and menu
  options carrying *mods*, *dev mode*, *quit*, *load*, *delete*, *abandon*, *banish* or *execute prisoner*
  are refused. She cannot start a game herself; the switch does that at GO.
- **The stream.** Spoken lines, the real Twitch chat, title and category, captions -- every one through the
  clean-stream filter, with emoji, URLs, paths and anything secret-shaped stripped.
- **Nothing else on the machine.** There is no shell and no process control. Writes are limited to small
  text files inside `.local/autopilot/scratch`; reads are allowlisted, and `.env`, `user.json`, tokens,
  passwords, credentials, keys and the Twitch profile are unreadable -- so it cannot see the stream key or
  any account secret. Saves are forced to the `rimbridge_save_` prefix.
- **It never edits the mod or writes code.** That is the reason it exists in this shape.

## Restart without dropping the stream

`windows
estart.bat` / `linux/restart.sh` restart everything **except the broadcast**: OBS switches to the BRB
scene and keeps streaming, so viewers never see Twitch's network error. She asks Ready? again, and GO switches the
stream back to Live (GO never relaunches an OBS that is already up). Only **stop** ends the broadcast.
