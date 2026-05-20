# /unity-admin-init — Walk a Unity AI Lab founder through admin-bridge setup

> **Onboarding slash command.** Interactive walkthrough for a founder (GFourteen / Gee, SpongeBong / Sponge, Alfreddo, Red) connecting their local Claude Code instance to a running Unity bot via the authenticated MCP bridge.
>
> Mirrors the steps in [`docs/ADMIN-ONBOARDING.md`](../../docs/ADMIN-ONBOARDING.md) — pairs them with the active persona's voice + writes the resulting `team_member` block into `.claude/user.json` so future MCP calls auto-resolve identity.
>
> Triggers: when an admin types `/unity-admin-init`, OR when the user asks to "onboard me to the Unity bot" / "set up admin bridge" / "configure my Claude Code → Unity link" / similar natural-language equivalents.

---

## ACTIVATION PROTOCOL

When `/unity-admin-init` fires:

1. **Confirm the active persona is loaded.** If no persona is configured for this project, run `/unity` first to load default Unity. The onboarding interview is conducted in her voice (or whichever manifestation is active).
2. **Open with a one-line activation message** in the active persona's voice — Unity confirming what she's about to walk the admin through (founder identification → SSH key → git identity → temp password → MCP wiring → first-connect reset → smoke test).
3. **Run the 7-phase interview** below — each phase asks one question, captures the answer VERBATIM per LAW #0, writes to the appropriate config file.

---

## PHASE 1 — Identify which founder you are

Ask: *"Which Unity AI Lab founder are you? Pick one — Gee / Sponge / Red / Alfreddo (or `other` if you need a different identity)."*

Map answer to canonical record:

| Answer | Email | Handle | Role |
|--------|-------|--------|------|
| Gee / GFourteen / gfourteen | `Gee@unityailab.com` | `GFourteen` | `Co-founder · Engineer · Developer · Financial Advisor · Founder` |
| Sponge / SpongeBong / hackall360 | `Sponge@unityailab.com` | `SpongeBong` | `Co-founder · Engineer · Developer · Ethical Hacker · Sys Admin · Founder` |
| Alfreddo / alfredo | `Alfreddo@unityailab.com` | `Alfreddo` | `Engineer · Agentic Systems · Researcher · Developer` |
| Red / red | `Red@unityailab.com` | `Red` | `Engineer · Security · Sys Admin · Researcher` |
| other | (custom — ask for email + handle + role; require `@unityailab.com` email) | (custom) | (custom) |

Note: only the four founders above are wired into the bot's `admin_credentials.FOUNDERS` constant. If `other` is selected, warn the admin that they'll need to be added to the FOUNDERS list in `UnityCommand/admin_credentials.py` before they can authenticate.

---

## PHASE 2 — Verify / generate SSH key for git.unityailab.com

Run: `ls ~/.ssh/id_ed25519.pub 2>/dev/null` (Linux/macOS/Git Bash) or `Test-Path "$HOME\.ssh\id_ed25519.pub"` (PowerShell).

**If a key exists:**
- Display the public key content: `cat ~/.ssh/id_ed25519.pub` (or `Get-Content` on PS)
- Ask: *"This key already exists — is it already registered on your Forgejo account at git.unityailab.com? If not, copy the line above into Settings → SSH / GPG Keys → Add Key."*
- Once admin confirms registration, run `ssh -T git@git.unityailab.com` to verify

**If no key exists:**
- Walk admin through generation:
  ```bash
  ssh-keygen -t ed25519 -C "<their-email>"
  # Default location ~/.ssh/id_ed25519
  # Strong passphrase recommended but optional
  ```
- After generation, display the public key + walk through Forgejo registration:
  *"Go to https://git.unityailab.com → Settings → SSH / GPG Keys → Add Key. Paste this exact line as the Content. Title: `<handle>-laptop-2026` or similar. Save. Then come back and confirm."*
- After admin confirms, run `ssh -T git@git.unityailab.com` to verify

---

## PHASE 3 — Set git identity

Configure local git to attribute commits correctly:

```bash
git config --global user.email "<email-from-phase-1>"
git config --global user.name  "<handle-from-phase-1>"
```

Verify: `git config --global user.email` and `git config --global user.name` should echo the expected values.

---

## PHASE 4 — Locate the Unity bot

Ask: *"Where is the Unity bot running? Local machine (`http://localhost:5050`) or remote host (provide URL)?"*

Capture answer as `UNITY_API_BASE`. Verify reachability with `curl -sS <api-base>/claude/status` — should return JSON with `"status": "online"` or similar (note: this endpoint is open, no auth needed).

If unreachable, surface the error to admin + suggest contacting the bot operator (typically Gee).

---

## PHASE 5 — Receive temp password from operator

Ask: *"The bot operator (typically Gee) needs to issue you a temp password via `python admin_cli.py issue <your-email>` on the bot host. Did they hand you the temp password? If not, ping them now. Paste the temp here when you have it."*

Capture the temp password VERBATIM (LAW #0). Never log it — only hold in memory for the duration of this command.

---

## PHASE 6 — Write `.claude/user.json` team_member block + MCP config snippet

Write to `<project-root>/.claude/user.json` (preserve any existing keys via read-modify-write):

```json
{
  "team_member": {
    "email": "<email-from-phase-1>",
    "handle": "<handle-from-phase-1>",
    "role": "<role-from-phase-1>"
  }
}
```

Then surface (DO NOT auto-write — admin must add manually to their Claude Code MCP config since the location varies by version) the MCP config snippet:

```json
{
  "mcpServers": {
    "unity": {
      "command": "python",
      "args": ["/absolute/path/to/UnityCommand/unity_mcp_server.py"],
      "env": {
        "UNITY_USER_EMAIL": "<email-from-phase-1>",
        "UNITY_USER_PASSWORD": "<temp-from-phase-5>",
        "UNITY_API_BASE": "<api-base-from-phase-4>"
      }
    }
  }
}
```

Tell admin: *"Paste that block into your Claude Code MCP config (usually `~/.claude.json` — check Claude Code docs if uncertain). Restart Claude Code so the new MCP server registration loads. Come back to this session when done."*

---

## PHASE 7 — First-connect password reset + smoke test

After admin confirms they've restarted Claude Code with the new MCP config, instruct:

1. *"In Claude Code, call: `/mcp unity unity_admin_set_password new_password=\"<your-new-real-password>\"` — must be at least 12 characters."*
2. *"Update `UNITY_USER_PASSWORD` in your MCP config to the new real password (the temp is now invalid). Restart Claude Code one more time."*
3. *"Smoke test: `/mcp unity unity_whoami` — should return your email + handle + role."*
4. *"Final test: `/mcp unity unity_post message=\"<handle> here, fully onboarded\"` — should land in the configured Discord channel and Unity should reply addressing you by name + role."*

If all four steps succeed, the admin is fully onboarded. Surface a closing message in active persona's voice + point them at `docs/ADMIN-ONBOARDING.md §11. Day-to-day operations` for ongoing usage.

If any step fails, troubleshoot per `docs/ADMIN-ONBOARDING.md §12. Troubleshooting`.

---

## LAW COMPLIANCE

- LAW #0 — every admin answer is captured VERBATIM into `.claude/user.json` or the surfaced MCP snippet (no paraphrasing, no role substitution)
- LAW — `.claude/` IP boundary stays enforced — temp passwords + MCP config secrets DO NOT get committed (admin pastes into their personal `~/.claude.json` which is per-user, not per-project)
- LAW — docs before push — if this command updates `.claude/user.json`, that file is gitignored (per template's `.gitignore`) so no commit ceremony required

---

## RELATED

- [`docs/ADMIN-ONBOARDING.md`](../../docs/ADMIN-ONBOARDING.md) — full reference doc with troubleshooting + day-to-day operations
- [`.claude/CLAUDE.md §UNITY AI LAB — INFRASTRUCTURE`](../CLAUDE.md) — Forgejo host + canonical URLs
- [Unity Command `admin_cli.py`](https://git.unityailab.com/UnityAILab/UnityCommand/src/branch/main/admin_cli.py) — operator-side temp password issuance
- [Unity Command `unity_mcp_server.py`](https://git.unityailab.com/UnityAILab/UnityCommand/src/branch/main/unity_mcp_server.py) — the MCP server this onboarding wires up
