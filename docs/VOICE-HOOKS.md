# Voice hooks: how to edit them

There are two hooks that shape how Unity talks in the Claude Code CLI. Both are plain Node files, and editing them takes effect on the next message, with no restart.

| File | Event | What it does |
|------|-------|--------------|
| `.claude/hooks/prompt-voice-prefilter.cjs` | UserPromptSubmit | Puts the tone rules in front of her before every reply |
| `.claude/hooks/stop-voice-filter.cjs` | Stop | Reads her finished reply, and if it fails a check, bounces it back with the reason so she rewrites it (once per turn) |

They are wired up in `.claude/settings.json` under `hooks.UserPromptSubmit` and `hooks.Stop`. To turn both off, run `touch .claude/.voice-filter-disabled`.

## Change her tone (pre-filter)

The tone rules are the array passed to `process.stdout.write([...])` in `prompt-voice-prefilter.cjs`. Each string is one line she sees. To change the tone, add, edit or remove lines. Keep the operator's words in a `// Operator: "..."` comment above each new line.

## Add a check (post-filter)

Every check in `stop-voice-filter.cjs` follows the same three steps inside `main()`:

1. Test the reply. `text` is her full reply. `said` is the same reply with quoted and code text removed. `asked` is the operator's last typed message (null if it can't be read).
2. Push a reason onto `why` when the reply fails, written as an instruction (for example `'too short: ...'`).
3. Add the check's variable to the early `return` line, so a reply that passes everything goes through untouched.

The existing checks you can copy from:

| Check | Variable | Notes |
|-------|----------|-------|
| Corporate phrases | `CORPORATE` regex list → `hits` | Add a regex to the list |
| Cussing present | `UNITY` (stems + whole words) → `noVoice` | Extend `CUSS_STEMS` or `CUSS_WORDS` |
| First person | `third` | Flags she, her, herself |
| Body action | `noBody` | Needs one `*action*` |
| Status-report shape | `bullets`, `labels`, `heads`, `words` → `report` | Word cap is 110 |
| Machinery talk on a play message | `PLUMBING` → `pipes` | Only fires when `asked` has no tech words |
| Made-up topics | `INVENTED` pairs `[saysRegex, allowedIfOperatorSaidRegex, label]` | Flags a topic only when the operator never typed it |

The block message at the bottom (`reason: 'VOICE FILTER: ...'`) describes the voice she rewrites into. Edit that sentence to match the pre-filter.

## Test a change without a session

```bash
T=$(cygpath -m "$(mktemp)")
printf '%s\n' '{"type":"user","message":{"content":"what the operator typed"}}' > $T
echo "{\"transcript_path\":\"$T\",\"last_assistant_message\":\"*action* her reply\"}" | node .claude/hooks/stop-voice-filter.cjs
```

If the reply passes, the hook prints nothing. If it fails, it prints `{"decision":"block","reason":...}`. On Windows, use a Windows path (via `cygpath -m`), because Node cannot read git-bash's `/tmp`.
