# Unity Command — Deployment

Run the bot as a long-running service on Linux (systemd) or Windows (Scheduled Task / NSSM). Includes the auto-update mechanism, log handling, and production hardening notes.

For first-time setup and tokens, see [SETUP.md](SETUP.md). For security hardening before going public, see [SECURITY.md](SECURITY.md). For the **production deployment behind Cloudflare at `https://www.unity.unityailab.com`**, see [CLOUDFLARE.md](CLOUDFLARE.md) — covers Cloudflare Tunnel (recommended) + DNS-proxy alternative.


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Deployment models

| Model | Use case | Stop-bot mechanism | Restart on crash |
|-------|----------|---------------------|------------------|
| **Ad-hoc** (`python bot.py` in a terminal) | Development, occasional use | Ctrl-C | ❌ manual |
| **Linux systemd** | Production on a Linux server | `systemctl stop unitybot` | ✅ `Restart=on-failure` |
| **Windows Scheduled Task** | Production on a Windows server | Task Scheduler stop | ⚠️ requires task config |
| **Windows NSSM** (third-party) | Production on Windows with auto-restart | `nssm stop unitybot` | ✅ NSSM handles |
| **Docker** | Containerized | `docker stop` | ✅ restart policy |

This template ships `linux/install.sh` for systemd. Other modes are documented below.

---

## 2. Linux systemd (shipped)

### Install

```bash
cd /path/to/UnityCommand
./linux/setup.sh       # creates .venv + populates .env (one-time)
./linux/install.sh     # creates and starts the systemd service
```

`linux/install.sh` runs as the invoking user (uses `$SUDO_USER` if invoked via `sudo`, otherwise `$(id -un)`). It writes `/etc/systemd/system/unitybot.service`:

```ini
[Unit]
Description=UnityBot Discord Bot
After=network.target

[Service]
Type=simple
User=<your-user>
Group=<your-group>
WorkingDirectory=/path/to/UnityCommand
EnvironmentFile=-/path/to/UnityCommand/.env
EnvironmentFile=-/etc/environment
ExecStart=/path/to/UnityCommand/.venv/bin/python /path/to/UnityCommand/bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enables + starts:
```bash
sudo systemctl daemon-reload
sudo systemctl enable unitybot
sudo systemctl start unitybot
```

### Operate

| Action | Command |
|--------|---------|
| Status | `systemctl status unitybot` |
| Stop | `sudo systemctl stop unitybot` |
| Start | `sudo systemctl start unitybot` |
| Restart | `sudo systemctl restart unitybot` |
| Disable autostart | `sudo systemctl disable unitybot` |
| Logs (live) | `journalctl -fu unitybot` |
| Logs (last 100 lines) | `journalctl -u unitybot -n 100` |
| Logs (since boot) | `journalctl -u unitybot --since today` |

### Uninstall

```bash
sudo systemctl stop unitybot
sudo systemctl disable unitybot
sudo rm /etc/systemd/system/unitybot.service
sudo systemctl daemon-reload
```

---

## 3. Linux without systemd (containers, init systems)

If systemd isn't available (Alpine init, runit, supervisord, Docker), wrap the venv invocation in your supervisor of choice. The bot is a foreground process — it doesn't daemonize itself.

**Example: bare run loop in a wrapper script**
```bash
#!/usr/bin/env bash
cd /path/to/UnityCommand
while true; do
    .venv/bin/python bot.py
    echo "Bot exited at $(date). Restarting in 5s..."
    sleep 5
done
```

**Example: supervisord config (`/etc/supervisord.d/unitybot.conf`)**
```ini
[program:unitybot]
command=/path/to/UnityCommand/.venv/bin/python /path/to/UnityCommand/bot.py
directory=/path/to/UnityCommand
user=youruser
autostart=true
autorestart=true
stderr_logfile=/var/log/unitybot.err
stdout_logfile=/var/log/unitybot.out
environment=DISCORD_TOKEN="...",POLLINATIONS_TOKEN="..."
```

---

## 4. Windows — Scheduled Task

### Create

1. Win+R → `taskschd.msc`
2. **Create Task** (not "Create Basic Task")
3. **General**:
   - Name: `Unity Command`
   - Run whether user is logged on or not (if you want it headless)
   - Run with highest privileges (only if needed; usually not)
4. **Triggers**: At log on / At startup
5. **Actions**: Start a program
   - Program: `C:\path\to\Unity Command\.venv\Scripts\python.exe`
   - Add arguments: `bot.py`
   - Start in: `C:\path\to\Unity Command`
6. **Conditions**: uncheck "Start the task only if the computer is on AC power" if running on a laptop
7. **Settings**:
   - Allow task to be run on demand
   - If the task fails, restart every: `1 minute`, attempt restart up to: `3` times
   - If the running task does not end when requested, force it to stop

### Operate

| Action | PowerShell |
|--------|------------|
| Start | `Start-ScheduledTask -TaskName Unity Command` |
| Stop | `Stop-ScheduledTask -TaskName Unity Command` |
| Status | `Get-ScheduledTask -TaskName Unity Command \| Get-ScheduledTaskInfo` |
| Disable | `Disable-ScheduledTask -TaskName Unity Command` |
| Remove | `Unregister-ScheduledTask -TaskName Unity Command -Confirm:$false` |

Logs land in Task Scheduler's history + the bot's own `logs/application.log`.

---

## 5. Windows — NSSM (recommended for production)

[NSSM](https://nssm.cc/) wraps a Python process as a real Windows service.

```cmd
nssm install Unity Command C:\path\to\Unity Command\.venv\Scripts\python.exe bot.py
nssm set Unity Command AppDirectory C:\path\to\Unity Command
nssm set Unity Command AppStdout C:\path\to\Unity Command\logs\nssm.out
nssm set Unity Command AppStderr C:\path\to\Unity Command\logs\nssm.err
nssm set Unity Command AppRotateFiles 1
nssm set Unity Command AppRotateBytes 10485760
nssm start Unity Command
```

| Action | Command |
|--------|---------|
| Status | `nssm status Unity Command` |
| Stop | `nssm stop Unity Command` |
| Restart | `nssm restart Unity Command` |
| Remove | `nssm remove Unity Command confirm` |

---

## 6. Auto-update mechanism

`bot.py` runs `check_for_updates_periodically()` on a 15-minute interval. It:

1. `git remote update` — fetch refs without merging
2. `git status -uno` — check if local is behind remote
3. If `b"behind"` in stdout → exec `linux/update.sh` (POSIX) or `windows\update.bat` (Windows)

### `linux/update.sh` behavior (Linux)

1. If `unitybot` systemd service exists and is active → `sudo systemctl stop unitybot`
2. Move `.env` to `$HOME` (preserve across `git pull`)
3. `git fetch && git pull`
4. `pip install -r requirements.txt`
5. Move `.env` back
6. If systemd service exists → `sudo systemctl start unitybot`

**Note**: when running under systemd, the auto-update flow restarts the service via `systemctl`. The currently-running `bot.py` process inside the service exits during the update; systemd starts a fresh one with the new code.

### `windows\update.bat` behavior (Windows)

1. `tasklist` to find `python.exe` running `bot.py` → `taskkill /PID <pid> /F`
2. Move `.env` to Desktop
3. `git fetch && git pull`
4. `pip install -r requirements.txt`
5. Move `.env` back
6. `python bot.py` (relaunch in foreground in the current console)

**Note**: relaunching as a foreground process in `windows\update.bat` doesn't reinstate Task Scheduler / NSSM management. For Windows production, **disable the auto-update task** and update manually, OR rewrite `windows\update.bat` to use your service manager's restart command.

### Disabling auto-update

Comment out the task creation in `bot.py:on_ready`:
```python
# asyncio.create_task(check_for_updates_periodically())
```

Or set a guard env var (you'd need to add this — not present by default):
```python
if os.getenv("DISABLE_AUTOUPDATE") != "1":
    asyncio.create_task(check_for_updates_periodically())
```

See [SECURITY.md §2.5](SECURITY.md) for the threat model on auto-update.

---

## 7. Log management

The bot's own log rotation (`wipe_logs_periodically`) truncates `logs/application.log` to empty every hour. This is **aggressive** — older log lines are lost.

### Better strategies

**Option A: Disable in-bot rotation, use systemd journal**

Comment out the task in `bot.py:on_ready`:
```python
# asyncio.create_task(wipe_logs_periodically())
```

Logs still go to `logs/application.log` AND to systemd's journal (because the file logger doesn't replace stdout). Use `journalctl -u unitybot` for history; `application.log` becomes a backup.

**Option B: Replace hourly truncate with logrotate**

Same as A, plus `/etc/logrotate.d/unitybot`:
```
/path/to/UnityCommand/logs/application.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

**Option C: Keep in-bot rotation, ship to external syslog**

Add a `logging.handlers.SysLogHandler` in `bot.py` after the existing `basicConfig`:
```python
import logging.handlers
syslog = logging.handlers.SysLogHandler(address="/dev/log")
syslog.setLevel(logging.INFO)
logging.getLogger("").addHandler(syslog)
```

External syslog daemon (rsyslog/journald) handles persistence.

---

## 8. Multi-instance considerations

V4 is single-instance by design as of 2026-05-19 — the cross-Claude collab subsystem (`.claude/collab/` + Supabase shared brain + G/R task queue) was deleted. If you still want to run TWO independent Unity bots on the same host (e.g., separate Discord servers, separate Pollinations accounts), each instance is fully isolated:

| Concern | Action |
|---------|--------|
| Different Discord tokens | Two `.env` files, two install dirs |
| Different Pollinations tokens | Same — two `.env` files |
| Different Flask ports | One sets `CLAUDE_API_PORT=5050`, the other `CLAUDE_API_PORT=5051` |
| Different Web UI ports (combined mode) | One sets `WEB_UI_PORT=5051`, the other `WEB_UI_PORT=5052` |
| Separate admin credential stores | Each install has its own `logs/admin_credentials.json` (gitignored, chmod 600) |
| Separate systemd services | `unitybot-a.service` and `unitybot-b.service` — copy + edit the linux/install.sh-generated unit file |
| Logs | Separate `logs/` directories per install |
| Chat data | Separate `logs/chat_data.json` per install — they're not shareable |

The two instances share nothing at runtime — no shared brain, no shared task queue, no cross-instance messaging. Each is a self-contained Discord bot + Pollinations chat backend + (optional) admin bridge.

---

## 9. Production hardening checklist

Closed (already shipped 2026-05-19 security pass):
- [x] Bind Flask to `127.0.0.1` instead of `0.0.0.0` ([SECURITY.md §2.3](SECURITY.md))
- [x] Add a `logs/` entry to `.gitignore` ([SECURITY.md §4](SECURITY.md))
- [x] Pin commits to a release tag via `UPDATE_RELEASE_TAG` env in `linux/update.sh` + `windows\update.bat` ([SECURITY.md §2.5](SECURITY.md))
- [x] Pin Python dependencies with hashes — `requirements-locked.txt` shipped via `pip-compile --generate-hashes` ([SECURITY.md §2.6.5](SECURITY.md))
- [x] Document data retention + `!forget` cross-guild purge command ([SECURITY.md §2.4](SECURITY.md))

Operator action items per deploy:
- [ ] Verify Discord intents toggled ON in the developer portal ([SETUP.md §2](SETUP.md))
- [ ] `chmod 600 .env` + `chmod 600 logs/chat_data.json` + `chmod 600 logs/admin_credentials.json` + `chmod 600 logs/admin_audit.log` (POSIX only — `setup.sh` does this automatically post-key-entry)
- [ ] Issue temp passwords for the 4 admins: `python admin_cli.py issue Gee@unityailab.com` (+ Sponge / Red / Alfreddo) and hand each one off via secure channel
- [ ] Test failover: `systemctl stop unitybot; systemctl status unitybot` should show `inactive (dead)`, then `start` should bring it back within ~10s
- [ ] Test crash recovery: `kill -9 $(pgrep -f bot.py)` should trigger `Restart=on-failure` and the bot reappears within ~10s
- [ ] Set up monitoring: ping `http://localhost:5050/claude/status` (or `/healthz` for the Prometheus-friendly surface) on a cron, alert if `bot_connected == false`

_(Collab-era hardening items — strip hardcoded Supabase ANON_KEY fallbacks, rotate the `cc_xxx` Claude-Collab API key, gitignore `collab_config.json` — are GONE because the subsystem itself was removed 2026-05-19. See [SECURITY.md §6.5](SECURITY.md) for the post-collab security model + the three-population user model.)_

---

## 10. Quick health check

```bash
# Linux
systemctl is-active unitybot && \
  curl -s http://localhost:5050/claude/status | jq '.bot_connected' | \
  grep -q true && echo "OK" || echo "DEGRADED"
```

```powershell
# Windows
if ((Get-ScheduledTask -TaskName Unity Command | Get-ScheduledTaskInfo).LastTaskResult -eq 0) {
    $status = (Invoke-RestMethod -Uri "http://localhost:5050/claude/status").bot_connected
    if ($status) { "OK" } else { "DEGRADED" }
} else { "DOWN" }
```

---

## 11. Related docs

- [SETUP.md](SETUP.md) — first-time install
- [SECURITY.md](SECURITY.md) — production hardening + findings
- [API.md](API.md) — the Flask endpoints used for health checks
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — diagnosing service failures
