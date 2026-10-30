# unity-brain

Unity's brain: plays RimWorld through the RimBridge tools, runs RimPLC, answers Twitch chat, writes her spoken
lines and reads screenshots. Text and image input. Everything needed to run it is in this folder.

## What's here

| File | What it is |
|---|---|
| `unity-brain.gguf` | The language model (Qwen3.5-9B fine-tune, IQ4_XS, 5.3 GB) |
| `unity-brain-vision.gguf` | The image reader that lets it see screenshots (0.9 GB) |
| `Modelfile` | Tells Ollama how to load both, with the right chat format and sampling |

## Setup

Install [Ollama](https://ollama.com), then from this folder:

```
ollama create unity-brain -f Modelfile
```

## Use it

```
ollama run unity-brain "Say hi to chat."
```

From a program, Ollama's API on `http://127.0.0.1:11434`:

```
curl localhost:11434/api/chat -d "{\"model\": \"unity-brain\", \"stream\": false, \"options\": {\"num_ctx\": 32768}, \"messages\": [{\"role\": \"user\", \"content\": \"Say hi to chat.\"}]}"
```

- **Always send the same `num_ctx` (32768).** A request without it makes Ollama reload the model with a much
  bigger default context (~14 GB of GPU memory instead of ~6 GB).
- **GPU memory:** about 6 GB at 32K context; it fits a 16 GB card alongside a game and OBS.
- **Images:** add `"images": ["<base64 png>"]` to a message.
## How it calls tools

It uses Ollama's standard tool calling: you send the tool list in the request's `tools` field, it answers with
`message.tool_calls` (name + JSON arguments), you run the tool and send the result back as a `role: "tool"`
message with `tool_name`. It only calls tools you give it, by their exact names.

```json
{"function": {"name": "say", "arguments": {"text": "Scar is a menace with a sword!", "emotion": "excited", "act": "exclamation"}}}
```

It was trained on 8,481 conversations using these names. Use the same names and argument shapes and it knows
them; anything else it has to read from your descriptions.

**Talking (her voice and chat).** Every spoken line carries the voice designators below.

| Tool | Arguments |
|---|---|
| `say` | `text`, `emotion`, `act`: a line out loud on stream |
| `reply_chat` | `chat_id`, `viewer`, `text`, `emotion`, `act`: answer a Twitch viewer by name |
| `reply_owner` | `msg_id`, `text`: private answer to the owner, never spoken |
| `webcam` | `mood`, `caption`: redraw her webcam picture |
| `snap` | `x`, `z`, `w`, `h`, `caption`: show a part of the map |

- `emotion`: `neutral`, `warm`, `happy`, `amused`, `excited`, `sad`, `concerned`, `frustrated`, `surprised`
- `act`: `statement`, `yes_no_question`, `wh_question`, `exclamation`, `instruction`, `reassurance`, `aside`
- She may put `[laughter]` inside `text` for a real laugh.

These are exactly the emotions and speech acts `unity-voice` was trained on, so her choice goes straight to the
voice. Send them to the voice as `emotion` and `speech_act`.

- `mood` (webcam): `chill`, `hype`, `angry`, `focus`, `laugh`, `smug`, `scared`, `sad`

**Playing the game (RimBridge).** RimBridge's tools are given to her with `rimworld/` renamed `game_`
(`rimworld/set_draft` -> `game_set_draft`). The ones she was trained on most:

| Tool | Arguments (example) |
|---|---|
| `game_list_architect_categories` | none |
| `game_list_architect_designators` | `{"categoryId": "architect-category:furniture"}` |
| `game_select_architect_designator` | `{"designatorId": "architect-designator:furniture:build-hospitalbed"}` |
| `game_apply_architect_designator` | `{"designatorId": "architect-designator:furniture:build-hospitalbed", "x": 166, "z": 128}` |
| `game_set_zone_target` | `{"designatorId": "architect-designator:zone:highlight-designator-zoneadd-growing", "zoneId": "Zone_0"}` |
| `game_set_draft` | `{"pawnName": "Kael", "drafted": true}` |
| `game_select_pawn`, `game_list_colonists` | `{"pawnName": "Scar"}`, `{"currentMapOnly": true}` |
| `game_list_selected_gizmos`, `game_execute_gizmo` | `{}`, `{"gizmoId": "selection-gizmo:sel-2e2fb9ea:2"}` |
| `game_get_cell_info`, `game_get_cells_info` | `{"x": 143, "z": 127}`, `{"x": 111, "z": 109, "width": 30, "height": 26}` |
| `game_list_letters`, `game_open_letter`, `game_dismiss_letter` | `{"letterId": "Letter_180"}` |
| `game_pause_game`, `game_set_time_speed` | `{"pause": true}`, `{"speed": "Normal"}` |
| `game_jump_camera_to_cell`, `game_take_screenshot` | `{"x": 142, "z": 147}`, `{"includeTargets": true}` |
| `game_list_alerts`, `game_list_zones`, `game_list_areas`, `game_close_window`, `game_press_accept` | |

Architect designators are the game's build/zone/order buttons. She lists a category, picks a `designatorId`
from what comes back (never invents one), then applies it at a cell.

**Our helper tools** (from the stream's own tool layer, `.local/autopilot/tools.py` in the Backrooms repo):
`game_state`, `look` (screenshot she sees), `pawn_check` (`pawn`, `tab`: Needs / Health / Gear / Character),
`order_pawn` (`pawn_id`, `x`, `z`, `option`), `pawn_priorities`, `play_slices` (`slices`), `game_set` (`cmd`),
`ladder` / `ladder_set` (the colony goal ladder), `run_list`, `empire_pass`, `plan` (`what`), `note`
(`name`, `text`, `append`), `read_doc` (`path`, `offset`, `limit`), `new_colony` (`reason`), `twitch_chat`.

**RimPLC:** she knows the RimPLC mod's settings and tools from its docs (92% right on held-out RimPLC tasks).
