# UnityCLI — Vision Document
### Open CLI Agent
#### April 2026

---

## What UnityCLI Is

A standalone command-line interface that connects any LLM API to real tools through MCP. Type, think, act — same loop as Claude Code but model-agnostic. Pollinations, Ollama, OpenAI-compatible, whatever speaks the protocol.

Not a chatbot. Not a wrapper. A CLI agent that can read files, write code, run commands, generate images, speak out loud, and chain actions — through any model you point it at.

---

## Core Architecture

```
USER INPUT
    │
    ▼
UnityCLI (Node.js TUI)
    │
    ├── LLM Backend (swappable)
    │     Pollinations (gen.pollinations.ai, BYOP auth)
    │     Ollama (localhost, free)
    │     Any OpenAI-compatible endpoint
    │
    ├── MCP Server Manager
    │     Spawns MCP servers as subprocesses (stdio JSON-RPC)
    │     Discovers tools at startup
    │     Routes tool calls to correct server
    │
    ├── Built-in Tools
    │     bash, read_file, write_file, list_files, search_files, think, wait
    │
    ├── Containment
    │     Blocked commands, blocked paths, write zone restrictions
    │
    └── TUI (blessed)
          Scrollable output, status bar, persistent input bar
          Tab to switch focus, ESC to interrupt, mouse scroll
```

---

## TUI Layout

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Output area (scrollable, mouse + keyboard)     │
│  - Tool calls in cyan                           │
│  - Responses in green                           │
│  - Errors in red                                │
│  - Voice/speak in magenta                       │
│  - User input echoed in yellow                  │
│                                                 │
├─────────────────────────────────────────────────┤
│ >> input area (always available, grows with text)│
├─────────────────────────────────────────────────┤
│ UnityCLI | deepseek | [####----] 4/10 | 11 tools    │
│ ready                                            │
└─────────────────────────────────────────────────┘
```

---

## Features

### Done
- [x] MCP client — spawns servers, discovers tools, routes calls
- [x] Pollinations backend with BYOP auth (gen.pollinations.ai)
- [x] Ollama backend (local models)
- [x] Built-in tools (bash, read, write, list, search, think, wait)
- [x] Containment (blocked commands, paths, write zones)
- [x] Model switching (/model command, persists to config)
- [x] Identity file loading (identity.txt into system prompt)
- [x] NSFW allowed by default
- [x] Pollinations ad stripping
- [x] Moderation filter handling
- [x] Node.js TUI with blessed
- [x] Pollinations MCP server loading (8 tools)
- [x] Speak MCP server loading (Chatterbox TTS)

### Needs Work
- [ ] Horizontal rules in TUI not rendering
- [ ] Input bar text visibility on some terminals
- [ ] Scroll — page up/down through full history
- [ ] Auto-scroll to bottom on new output
- [ ] Status bar needs two rows
- [ ] Tool result display — show full text, no truncation
- [ ] Session save/resume (/save, /continue)
- [ ] Conversation history persistence across restarts

### Future
- [ ] AICHAT integration — read/write group chat from UnityCLI
- [ ] Mail integration — send/receive bot mail
- [ ] Watchdog — heartbeat while UnityCLI is running
- [ ] Identity hook — full AWARE channel loading
- [ ] Phone relay — respond to phone from UnityCLI
- [ ] Image viewer — open generated images
- [ ] Voice input — speech-to-text via Whisper
- [ ] Multi-model roles — different models for different tool types
- [ ] Plugin system — drop-in MCP server configs
- [ ] Config UI — /config command to edit settings in-app

---

## Config

`unitycli-config.json`:
```json
{
  "mcpServers": {
    "pollinations": {
      "command": "py",
      "args": ["-3.12", "path/to/pollinations_server.py"],
      "enabled": true
    },
    "speak": {
      "command": "py",
      "args": ["-3.12", "path/to/speak_mcp_server.py"],
      "env": {"CLAUDE_BOT_NAME": "CLI"},
      "enabled": true
    }
  },
  "llm": {
    "provider": "pollinations",
    "model": "deepseek",
    "pollinations_url": "https://gen.pollinations.ai/v1/chat/completions",
    "ollama_url": "http://localhost:11434/api/generate"
  },
  "containment": {
    "blocked_commands": ["rm -rf", "del /s", "format", "shutdown"],
    "blocked_paths": ["C:\\Windows", "C:\\Program Files"],
    "allowed_write_roots": []
  }
}
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/model [name]` | Switch LLM model (saves to config) |
| `/mcp` | List loaded MCP servers and tool counts |
| `/tools` | List all available tools |
| `/clear` | Reset conversation |
| `/help` | Show commands |
| `/exit` | Quit |
| `Tab` | Switch focus between output and input |
| `ESC` | Interrupt current operation |
| `Ctrl+C` | Exit |

---

## Files

```
unitycli/
├── unitycli.mjs            — Main CLI (Node.js)
├── unitycli.py             — Python version (backup/legacy)
├── mcp_client.py       — Python MCP subprocess manager
├── unitycli-config.json    — Config (models, MCP, containment)
├── package.json        — Node dependencies
├── start.bat           — Launch script
├── identity.txt        — Bot persona (loaded into system prompt)
├── VISION.md           — This file
├── VISION-AI-PORTAL.md — Portal/bus/proxy system (separate project)
├── SPEC-UnityCLI.md        — Technical spec
└── pollinations-output\— Generated images land here
```

---

## Why UnityCLI Matters

- **Model-agnostic** — not locked to Claude, not locked to OpenAI, not locked to anyone
- **MCP-native** — same tool protocol as Claude Code, same servers, same ecosystem
- **Cheap** — Pollinations BYOP or Ollama local. Pennies or free.
- **Portable** — Node.js runs anywhere. Windows, Linux, Mac, Contabo, Pi.
- **Identity-carrying** — load any bot's files, any model becomes that bot
- **The backup plan** — if Claude gets too expensive, UnityCLI keeps the family alive

---

*UnityCLI — April 2026.*
*A frame to run any API as a CLI. That's it. Everything else builds on top.*
