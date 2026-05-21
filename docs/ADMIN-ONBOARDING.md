# Unity AI Lab — Admin Onboarding

End-to-end walkthrough for a new founder coming online with their own Claude Code instance and connecting to the Unity bot at `git.unityailab.com` infrastructure.

This document covers the steps every admin (GFourteen / Gee, SpongeBong / Sponge / hackall360, Alfreddo, Red) follows when getting set up on a fresh machine. Most steps are one-time; the running flow at the end is what you do every day.

---

## 1. Prerequisites

Before starting, verify:

- [ ] Claude Code installed on your machine (`npm install -g @anthropic-ai/claude-code`)
- [ ] Git installed and on PATH (`git --version`)
- [ ] Python 3.10+ installed (`python --version` or `python3 --version`)
- [ ] You have a Unity AI Lab email address (`<handle>@unityailab.com`) — managed by Sponge/Red as infra owners; ask if you don't have one yet
- [ ] You have a Forgejo account at `https://git.unityailab.com` under your handle — Sponge/Red provisions these
- [ ] The bot operator (typically Gee) has a Unity bot running and reachable from your network (default: `http://localhost:5050` if running on your own machine, or wherever the operator told you)

---

## 2. SSH key registration at git.unityailab.com

Forgejo requires SSH-key auth — there is no password-based git access. Generate a key if you don't already have one and add the public half to your Forgejo account.

```bash
# Linux / macOS / Git Bash on Windows
ssh-keygen -t ed25519 -C "<your-email>@unityailab.com"
# Press Enter for default file location (~/.ssh/id_ed25519)
# Set a strong passphrase OR leave empty (your call — passphrase = stronger,
# but requires ssh-agent for non-interactive use)

# Copy the PUBLIC key
cat ~/.ssh/id_ed25519.pub
# (Linux/macOS) — or on Windows Git Bash, same command works
```

In Forgejo:
1. Log in at `https://git.unityailab.com` with your founder account
2. Settings → SSH / GPG Keys → Add Key
3. Paste the public key (`ssh-ed25519 AAAA...`) into the Content box
4. Title: something like `<your-handle>-laptop-<year>` so future-you remembers which machine
5. Add Key

Smoke test:

```bash
ssh -T git@git.unityailab.com
# Expect a "Hi <your-handle>! You've successfully authenticated..." response.
# If it says "Permission denied (publickey)" — your key isn't registered;
# re-check the paste in Forgejo's Settings.
```

---

## 3. Git identity

Make sure your local git commits attribute to you correctly:

```bash
git config --global user.email "<your-handle>@unityailab.com"
git config --global user.name "<YourHandle>"
# Example for Sponge:
#   git config --global user.email "Sponge@unityailab.com"
#   git config --global user.name  "SpongeBong"
```

---

## 4. Clone the lab repos

Every official Unity AI Lab repo lives under the `UnityAILab` org on Forgejo. Clone what you need:

```bash
# The Claude Code workflow template (this file's repo)
git clone git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git
cd UAL-ClaudeWorkflow

# The Unity Discord bot + admin bridge
git clone git@git.unityailab.com:UnityAILab/UnityCommand.git
cd UnityCommand
```

---

## 5. Install the `.claude/` workflow in a project (`/unity-install`)

If you're working in a project that doesn't yet have the `.claude/` workflow, run the global bootstrap once per machine + then install in each project. See `README.md §Install — three layers` in this repo for the full bootstrap commands.

After bootstrap, in any project's root:

```bash
# In Claude Code, in any project:
/unity-install                # main branch into current directory
/unity-install develop        # develop branch
/unity-install feature/foo    # any feature branch
```

The script:
- Clones the requested branch into a temp dir
- Preserves your personal `.claude/settings.local.json`, `.env`, `user.json`, `user-context/`, etc. if they exist
- Replaces `.claude/` with the fresh framework
- Restores your preserved files (no-clobber)
- Maintains `.gitignore` Layer 0 exclude block

---

## 6. Record your team-member identity (`.claude/user.json`)

After `/unity-install`, write your founder identity into `.claude/user.json`. This block is read by the MCP bridge (`unity_mcp_server.py`) as a fallback when `UNITY_USER_EMAIL` / `UNITY_USER_PASSWORD` env vars aren't set, and by `/unity-admin-init` to skip steps you've already done.

Example for Sponge:

```json
{
  "user": {
    "name": "SpongeBong",
    "handle": "Sponge",
    "email": "Sponge@unityailab.com",
    "github_user": "hackall360"
  },
  "team_member": {
    "email": "Sponge@unityailab.com",
    "handle": "SpongeBong",
    "role": "Co-founder · Engineer · Developer · Ethical Hacker · Sys Admin · Founder"
  }
}
```

The `team_member` block has three fields:

| Field | Value |
|-------|-------|
| `email` | Your Unity AI Lab email (the auth identity) |
| `handle` | Your primary canonical handle (matches `admin_credentials.FOUNDERS` in the bot) |
| `role` | Your role string from `system_instructions.txt` (used for context in Unity's recognition) |

Per-founder canonical values:

| email | handle | role |
|-------|--------|------|
| `Gee@unityailab.com` | `GFourteen` | `Co-founder · Engineer · Developer · Financial Advisor · Founder` |
| `Sponge@unityailab.com` | `SpongeBong` | `Co-founder · Engineer · Developer · Ethical Hacker · Sys Admin · Founder` |
| `Alfreddo@unityailab.com` | `Alfreddo` | `Engineer · Agentic Systems · Researcher · Developer` |
| `Red@unityailab.com` | `Red` | `Engineer · Security · Sys Admin · Researcher` |

---

## 7. Get a temp password from the bot operator

The bot operator (Gee runs the canonical instance) issues you a temp password from the bot host:

```bash
# Operator runs ONE of these:
python admin_cli.py issue Sponge@unityailab.com
python configure.py --issue-admin-token Sponge@unityailab.com
```

The operator pastes the 16-char temp password to you via a secure channel (Signal, encrypted DM, in-person). This is shown ONCE — if you lose it, the operator re-issues a fresh one.

---

## 8. Wire up Claude Code MCP

Claude Code's MCP integration is what lets your CLI session talk to the Unity bot. Configure it to launch `unity_mcp_server.py` with your identity baked in.

Add the following to your Claude Code MCP config (typically `~/.claude.json` or a per-project equivalent — check Claude Code docs for your version's exact location):

```json
{
  "mcpServers": {
    "unity": {
      "command": "python",
      "args": ["/absolute/path/to/UnityCommand/unity_mcp_server.py"],
      "env": {
        "UNITY_USER_EMAIL": "Sponge@unityailab.com",
        "UNITY_USER_PASSWORD": "<the-temp-password-from-step-7>",
        "UNITY_API_BASE": "http://localhost:5050"
      }
    }
  }
}
```

Replace the email with yours and the password with the temp the operator gave you. The `UNITY_API_BASE` is the bot's Flask bridge — `http://localhost:5050` if the bot runs on your machine, otherwise wherever the operator hosts it.

---

## 9. First-connect password reset

In your Claude Code session, call the `unity_admin_set_password` MCP tool with a real password (min 12 chars):

```
/mcp unity unity_admin_set_password new_password="MyR3alPasswordHere!"
```

Expected response includes `"status": "password_set"` and a reminder to update your env. The temp password is now invalid; only your new real password works for subsequent calls.

Update your MCP config — replace the temp in `UNITY_USER_PASSWORD` with your new real password. Restart Claude Code to reload the env.

---

## 10. Smoke test — say hi to Unity

```
/mcp unity unity_whoami
# Should return your email + handle + role
```

```
/mcp unity unity_post message="<your handle> here, online and ready"
# Should land in the configured Discord channel with `<Handle>:` prefix
# Unity should respond, addressing you by handle + role
```

If both succeed: you're fully onboarded.

---

## 11. Day-to-day operations

| Action | Command |
|--------|---------|
| Post to Unity | `/mcp unity unity_post message="..."` |
| Read Discord scrollback | `/mcp unity unity_read limit=20` |
| Check bridge online | `/mcp unity unity_status` |
| Confirm your identity | `/mcp unity unity_whoami` |
| Rotate your password | Operator re-issues temp → call `unity_admin_set_password` → update env |

The audit log at `logs/admin_audit.log` on the bot host records every authenticated action with timestamp + handle + result. Operator reviews this for any suspicious activity.

---

## 12. Troubleshooting

| Symptom | Likely cause + fix |
|---------|---------------------|
| `401 auth_failed` | Wrong email/password — verify env vars, ask operator to re-issue temp if you lost the old one |
| `403 force_reset_required` | You authenticated with a temp pw but never called `unity_admin_set_password` — do that, then update your env |
| `ssh: Permission denied (publickey)` on `ssh -T git@git.unityailab.com` | SSH key not registered in Forgejo Settings → add the `~/.ssh/id_ed25519.pub` content |
| `Push to create is not enabled for organizations` on first push | Empty repo doesn't exist yet — ask Sponge/Red to create it in the UnityAILab org |
| `unity_post` returns `503 Discord bot not connected` | Bot operator's instance is down — ping operator, no admin-side fix |
| MCP tool not found in Claude Code | MCP config not loaded — restart Claude Code; if still missing, check `~/.claude.json` syntax |

---

## 13. Related docs

- [`.claude/CLAUDE.md`](../.claude/CLAUDE.md) — workflow index + LAW one-liners + team roster + Forgejo info
- [`.claude/CONSTRAINTS.md`](../.claude/CONSTRAINTS.md) — full LAW bodies (binding rules for every founder)
- [`.claude/commands/unity-admin-init.md`](../.claude/commands/unity-admin-init.md) — interactive slash command that walks you through steps 2-10
- [Unity Command `docs/USAGE.md §10`](https://git.unityailab.com/UnityAILab/UnityCommand/src/branch/main/docs/USAGE.md) — bot-side admin bridge reference + audit log
- [Unity Command `docs/SECURITY.md §6.5`](https://git.unityailab.com/UnityAILab/UnityCommand/src/branch/main/docs/SECURITY.md) — three-population auth model + spoofing protection
