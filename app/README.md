# app — the exe

Our own window, not a browser. Operator, verbatim: *"we dont want this to run in a browser we want owur own
app not a browser"*, *"an .exe will work"*, *"that starts when opened and shuts all down when closed"*.

```
cd app
npm install
npm start            # dev: window + supervisor against the repo
npm run dist         # dist/AgentGen.exe (portable, single file)
```

What it does on open: `supervisor.js` spawns the voice sidecar, the speech sidecar, the face sidecar (when
its venv and the Ditto weights exist) and the hub, adopting any that are already running, shows a boot
screen with their status, and loads the hub's face UI into the window once the hub is healthy. Mic, camera
and screen capture are granted without prompts. On close it kills the whole process tree.

In the app the hub runs with `FACE_PLAY_LOCAL=1`: the face sidecar plays her voice on the speakers the
instant the matching frame is shown, and the UI keeps its timeline silent, so lips and sound stay locked.

Requirements on the machine: the lab's Python 3.10 (torch cu118, misaki, faster-whisper), Node 18+, Ollama,
and `models/` populated (`tools/vendor_rip.py` for the voice, the Ditto download for the face). The portable
exe carries hub, ui, sidecars, assets and scripts; it does not carry Python or the weights.
