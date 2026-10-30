# Unity Command — Cloudflare Deployment

> Production deploy of the V4 web UI behind Cloudflare. Target: **<https://www.unity.unityailab.com>**

```
                      ┌─────────────────────────────────┐
   Internet ────────▶│  Cloudflare Edge                │
                      │  (TLS termination + WAF + DDoS) │
                      └──────────────┬──────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                  Path A: │                     │  Path B:
                  TUNNEL  │                     │  DNS-PROXY
                  (recommended)                 │  (origin has public IP)
                          │                     │
                          ▼                     ▼
              ┌───────────────────┐    ┌───────────────────┐
              │   cloudflared     │    │  Cloudflare A     │
              │   outbound 443    │    │  record (proxied) │
              │   from origin     │    │  + nginx + cert   │
              └─────────┬─────────┘    └─────────┬─────────┘
                        │                        │
                        └────────────┬───────────┘
                                     ▼
                           ┌───────────────────┐
                           │  V4 web_server.py │
                           │  127.0.0.1:5051   │
                           └───────────────────┘
```

**Two deployment paths.** Pick based on origin network posture:

| Path | When to use | Complexity |
|------|-------------|------------|
| **A. Tunnel** (recommended) | Origin behind NAT, no public IP, want zero inbound firewall holes | Low — one daemon, no cert ceremony |
| **B. DNS-proxy**            | Origin has static public IPv4 (VPS, dedicated, cloud)            | Higher — nginx, Origin Cert, firewall config |

**Automated setup** (Path A only): `python configure.py --setup-cloudflare-tunnel` walks the entire flow — install cloudflared, login (browser), create tunnel, route DNS, write config, install service. See [§1.0](#10-automated-path--one-command-does-§11-through-§16) below.

**Everything you need** — DNS, CNAMEs, firewall, TLS, certs, troubleshooting — is in this one document.

---

## 0. Pre-flight checklist

Before you touch Cloudflare itself, confirm:

### 0.1 Domain is in Cloudflare

The `unityailab.com` zone must already be added to your Cloudflare account.

1. Sign in to <https://dash.cloudflare.com>
2. Confirm `unityailab.com` appears in your zones list. If not:
   - Click **+ Add a site** → enter `unityailab.com` → free plan is fine
   - Cloudflare gives you two nameservers (e.g. `aron.ns.cloudflare.com`, `kate.ns.cloudflare.com`)
   - Log in to wherever the domain is registered (Namecheap, Google Domains, GoDaddy, Porkbun, etc.)
   - Replace the existing nameservers with the two Cloudflare gave you
   - DNS propagation typically takes 5 minutes to 24 hours

### 0.2 Verify nameservers are pointed at Cloudflare

```bash
# From any host
dig unityailab.com NS +short
# Expect: two cloudflare.com nameservers, e.g.:
#   aron.ns.cloudflare.com.
#   kate.ns.cloudflare.com.

# OR check via Cloudflare's own checker
curl -sI https://unityailab.com | head -1
# Expect: HTTP response with server: cloudflare somewhere in headers
```

If you don't see Cloudflare nameservers, the propagation hasn't happened yet OR the registrar hasn't been updated. Don't proceed until DNS resolves to Cloudflare.

### 0.3 Cloudflare API token (optional but useful)

For scripting / automation you'll want an API token:
1. Cloudflare dashboard → **My Profile → API Tokens → Create Token**
2. Use the "Edit zone DNS" template
3. Scope to `unityailab.com` only
4. Save the token somewhere secure (e.g., a password manager — NOT in `.env` for V4)

### 0.4 Origin host requirements

Whichever deployment path you pick, the origin host needs:
- Python 3.8 – 3.11 installed (`python --version`)
- V4 cloned + `python configure.py` complete (`.env` populated)
- `python web_server.py` working locally (test with `curl http://localhost:5051/api/health` — expect `{"status": "ok"}`)
- Network connectivity to `gen.pollinations.ai` (outbound HTTPS — Pollinations chat backend)
- Network connectivity to `discord.com` if combined-mode-with-bot (outbound TLS + WebSocket)

If any of these aren't satisfied, fix the local install before adding Cloudflare to the picture.

### 0.5 Path picker

| Question | Answer | Use |
|----------|--------|-----|
| Does the origin have a static public IPv4? | NO (typical home server, NAT, dynamic IP, VPC private subnet) | **Path A — Cloudflare Tunnel** |
| Does the origin have a static public IPv4? | YES (VPS, dedicated server, cloud instance with public IP) | Either works — Tunnel is still simpler + safer |
| Are you running multiple environments (prod + staging + dev)? | YES | **Path A — Cloudflare Tunnel** — each env gets its own tunnel + hostname |
| Is this a temporary / test setup? | YES | Tunnel — zero-touch teardown when you stop `cloudflared` |
| Do you need to host static files or another service on the same host alongside V4? | YES | DNS-proxy + nginx — easier to host multiple services |

| Path | When to use | Pros | Cons |
|------|-------------|------|------|
| **Cloudflare Tunnel** (recommended) | Origin behind NAT, no public IP, want zero inbound firewall holes | No port-forwarding, no static IP needed, automatic TLS, built-in DDoS protection, identity-aware proxy available | One more daemon (`cloudflared`) running |
| **DNS + Proxied A/AAAA record** | Origin has a public static IP (VPS, dedicated server) | Conceptually simpler, no extra daemon | Origin must be hardened — firewall, fail2ban, TLS cert (Origin Cert) |

The bot's web UI binds to `127.0.0.1:5051` by default ([SECURITY.md §2.3](SECURITY.md)). Cloudflare Tunnel reaches it via localhost — perfect fit. The DNS-proxy path needs Flask bound to `0.0.0.0` AND an origin TLS cert, so the Tunnel path is strictly safer.

---

## 1. Path A — Cloudflare Tunnel (recommended)

### 1.0 Automated path — one command does §1.1 through §1.6

```bash
python configure.py --setup-cloudflare-tunnel
```

This walks the dev through the entire Tunnel setup automatically:
1. Detects `cloudflared` on PATH; offers to install via apt/brew/winget if missing
2. Runs `cloudflared tunnel login` (only manual step — opens browser, you sign in)
3. Runs `tunnel create unity-bot-prod` and captures the UUID
4. Prompts for hostname (default `www.unity.unityailab.com`)
5. Runs `tunnel route dns` to create the CNAME automatically
6. Generates `/etc/cloudflared/config.yml` (or `~/.cloudflared/config.yml` on Windows)
7. Runs `cloudflared service install` + starts the service via systemd / Windows SCM / launchd

After it finishes, your tunnel is live. Skip directly to §3 to smoke-test.

**Use the manual walkthrough below** (§1.1 onward) if:
- The automated flow failed and you need to recover step-by-step
- You want to understand exactly what's happening
- You need a customized config (multiple ingress rules, non-standard service paths, etc.)

### 1.1 One-time Cloudflare setup

1. Sign in to <https://dash.cloudflare.com>, open the `unityailab.com` zone.
2. Left sidebar → **Zero Trust** → **Networks** → **Tunnels**.
3. Click **Create a tunnel**.
   - Connector type: **Cloudflared**
   - Tunnel name: e.g. `unity-bot-prod`
4. Cloudflare gives you an install command for your OS. Copy it — it contains the tunnel token.

### 1.2 Install `cloudflared` on the bot host

**Linux (Debian / Ubuntu):**
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

**Linux (RHEL / Fedora):**
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.rpm -o cloudflared.rpm
sudo rpm -i cloudflared.rpm
```

**Windows:**
```cmd
winget install --id Cloudflare.cloudflared -e
```
or download the MSI from <https://github.com/cloudflare/cloudflared/releases>.

**macOS:**
```bash
brew install cloudflared
```

### 1.3 Authenticate + register the tunnel

If Cloudflare gave you a token (their newer onboarding flow), the install command from §1.1 step 4 already does this. Otherwise:

```bash
cloudflared tunnel login
# Opens a browser → log in → pick the unityailab.com zone
cloudflared tunnel create unity-bot-prod
# Prints a Tunnel UUID — copy it
```

The credentials file lands at `~/.cloudflared/<TUNNEL_UUID>.json`.

### 1.4 Route DNS to the tunnel — automatic CNAME

```bash
cloudflared tunnel route dns unity-bot-prod www.unity.unityailab.com
```

This automatically creates a CNAME record in the Cloudflare zone:
```
www.unity   CNAME   <TUNNEL_UUID>.cfargotunnel.com   Proxied (orange cloud)
```

TLS is terminated at Cloudflare — origin sees plain HTTP. The orange-cloud proxy is what gives you the Cloudflare IP at the edge instead of exposing your origin.

### 1.4b Manual CNAME setup (if `cloudflared tunnel route dns` fails)

If the automated routing fails (permission issue, API hiccup, etc.) you can create the CNAME by hand:

1. Cloudflare dashboard → `unityailab.com` zone → **DNS → Records**
2. Click **+ Add record**
3. Fill in:
   - **Type**: `CNAME`
   - **Name**: `www.unity` (Cloudflare expands this to `www.unity.unityailab.com` automatically)
   - **Target**: `<TUNNEL_UUID>.cfargotunnel.com` (get UUID from `cloudflared tunnel list`)
   - **Proxy status**: **Proxied** (orange cloud) — **CRITICAL**, must be orange not grey
   - **TTL**: Auto
4. Click **Save**

The orange cloud is what makes Cloudflare's edge serve the traffic. A grey cloud (DNS only) would expose your tunnel UUID directly and bypass all Cloudflare protections.

### 1.4c Apex / canonical hostname handling

If you also want `unity.unityailab.com` (no `www`) to work, route a second hostname:
```bash
cloudflared tunnel route dns unity-bot-prod unity.unityailab.com
```

Then enforce a single canonical hostname via Cloudflare Rules:
1. Cloudflare dashboard → **Rules → Redirect Rules → + Create rule**
2. Rule name: `unity-apex-to-www`
3. When incoming requests match: **Custom filter expression**
   ```
   (http.host eq "unity.unityailab.com")
   ```
4. Then: **Static URL redirect**
   - Target URL: `https://www.unity.unityailab.com${http.request.uri}`
   - Status code: `301` (permanent)
   - Preserve query string: ON
5. Deploy

This 301s `unity.unityailab.com/*` → `https://www.unity.unityailab.com/*` so search engines + bookmarks + APIs all canonicalize to the `www` form.

### 1.5 Tunnel config

Create `/etc/cloudflared/config.yml` (Linux) or `%USERPROFILE%\.cloudflared\config.yml` (Windows):

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json   # adjust path on Windows

ingress:
  # Primary — V4 web UI on localhost:5051
  - hostname: www.unity.unityailab.com
    service: http://localhost:5051
    originRequest:
      noTLSVerify: true   # OK — origin is localhost
      httpHostHeader: www.unity.unityailab.com
      connectTimeout: 30s
      keepAliveConnections: 16

  # Apex redirect handled separately via Page Rule (§1.4)
  - hostname: unity.unityailab.com
    service: http://localhost:5051
    originRequest:
      httpHostHeader: unity.unityailab.com

  # Catch-all
  - service: http_status:404
```

Copy the credentials file Cloudflare generated into the path you reference:
```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/<TUNNEL_UUID>.json /etc/cloudflared/
sudo chown root:root /etc/cloudflared/<TUNNEL_UUID>.json
sudo chmod 600 /etc/cloudflared/<TUNNEL_UUID>.json
```

### 1.6 Run as a service

**Linux (systemd):**
```bash
sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```

**Windows (service):**
```cmd
cloudflared --config "%USERPROFILE%\.cloudflared\config.yml" service install
sc start cloudflared
```

**Verify it routes:**
```bash
# From any client
curl -I https://www.unity.unityailab.com/api/health
# Expect: 200 OK with Server: cloudflare
```

### 1.7 Bot host configuration

V4 doesn't need ANY special config — the tunnel reaches it on `127.0.0.1:5051` which is already the default. But:

- Make sure the bot is actually running: `python web_server.py` (or `systemctl status unitybot` if using the bot's systemd service; `python bot.py` with `WEB_UI_ENABLED=1` also exposes it).
- Confirm `WEB_UI_PORT=5051` matches what your tunnel `config.yml` references.
- Leave `WEB_UI_HOST=127.0.0.1` (default) — do NOT bind to `0.0.0.0` for tunnel mode; localhost binding plus Cloudflare's tunnel is the secure combination.

### 1.7b Origin firewall for Tunnel mode

The beauty of Tunnel mode: **you don't need to open ANY inbound ports.** All traffic enters via the outbound `cloudflared` connection.

> **Note**: The host-level firewall (what this section covers) and Discord's `ALLOWED_GUILDS` env-var allowlist (what V4 enforces in `bot.py:on_message`) are **independent defense layers**. The firewall restricts who can reach the *host*; `ALLOWED_GUILDS` restricts which Discord servers the *bot* responds in. Both can (and should) be configured — they're not redundant.

**Linux (UFW) — recommended baseline:**
```bash
# Default-deny inbound, allow outbound
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH only — restrict to your admin IP if possible
sudo ufw allow from <your.admin.ip>/32 to any port 22 proto tcp comment "admin SSH"

# That's it — no 80, no 443, no 5051 needed.
# cloudflared opens outbound TLS to Cloudflare on 443 (allowed by default).

sudo ufw enable
sudo ufw status verbose
```

**Linux (iptables) — equivalent:**
```bash
# Default policies
sudo iptables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo iptables -P OUTPUT ACCEPT

# Allow established connections back in
sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow SSH from admin IP only
sudo iptables -A INPUT -p tcp -s <your.admin.ip>/32 --dport 22 -j ACCEPT

# Allow loopback (Cloudflared → V4 on localhost)
sudo iptables -A INPUT -i lo -j ACCEPT

# Save (Debian/Ubuntu: install iptables-persistent first)
sudo netfilter-persistent save
```

**Linux (nftables) — modern equivalent:**
```bash
# /etc/nftables.conf
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;
        iif lo accept
        ct state established,related accept
        ip saddr <your.admin.ip>/32 tcp dport 22 accept comment "admin SSH"
    }
    chain forward { type filter hook forward priority 0; policy drop; }
    chain output { type filter hook output priority 0; policy accept; }
}

sudo systemctl enable --now nftables
sudo nft -f /etc/nftables.conf
```

**Windows Firewall (PowerShell as admin):**
```powershell
# Block all inbound by default
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block -DefaultOutboundAction Allow

# Allow SSH from your admin IP only (if you've enabled OpenSSH Server)
New-NetFirewallRule -DisplayName "Admin SSH" -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress <your.admin.ip>/32 -Action Allow

# DO NOT add rules for 80, 443, or 5051 — Tunnel handles all of that outbound
```

**Cloud provider firewall (AWS Security Group / GCP firewall / DigitalOcean firewall):**
Same rule — allow outbound 443 (Tunnel needs it), allow inbound SSH from your admin IPs only, deny everything else. No need for inbound 80/443.

### 1.8 Cloudflare-side hardening

In the Cloudflare dashboard, for `unityailab.com`:

1. **SSL/TLS → Overview** → Mode: **Full (strict)** — this is fine since Cloudflare ↔ Origin is over the tunnel (encrypted automatically).
2. **SSL/TLS → Edge Certificates** → **Always Use HTTPS**: ON.
3. **SSL/TLS → Edge Certificates** → **Minimum TLS Version**: TLS 1.2 or higher.
4. **Security → WAF** → enable the Cloudflare Managed Ruleset (free plan gets a useful subset).
5. **Security → Bots** → enable Bot Fight Mode (free plan).
6. **Rules → Page Rules** (or **Rules → Transform Rules** on newer dashboards) → enforce HTTPS canonical redirects + cache the `/web/static/*` assets aggressively.
7. **Access (Zero Trust)** — optional but recommended for the setup wizard step: gate `/api/setup*` and `/setup` behind Cloudflare Access so randos can't hit the wizard form. (Skip if you trust public access to the setup form — the wizard already validates server-side.)

### 1.9 Per-environment env vars

If running multiple environments (dev/staging/prod) on the same Cloudflare zone, distinguish via subdomain:

| Env | URL | Tunnel hostname |
|-----|-----|----------------|
| Prod | `https://www.unity.unityailab.com` | `www.unity.unityailab.com` |
| Staging | `https://staging.unity.unityailab.com` | `staging.unity.unityailab.com` |
| Dev | `http://localhost:5051` | (no tunnel — direct) |

Each environment runs its own `cloudflared` service pointed at its own host.

---

## 2. Path B — DNS + Proxied A/AAAA record (if origin has public IP)

Use this only if your origin VPS has a static public IP AND you're comfortable hardening the origin yourself.

### 2.1 DNS records (manual)

In the Cloudflare dashboard for `unityailab.com`:

1. **DNS → Records** → **+ Add record** for the primary hostname:
   - **Type**: `A` (IPv4) — or `AAAA` if your origin has only IPv6
   - **Name**: `www.unity` (expands to `www.unity.unityailab.com`)
   - **IPv4 address**: `<your.origin.public.ip>` (find with `curl ifconfig.me` from origin)
   - **Proxy status**: **Proxied** (orange cloud) — **CRITICAL**, must be orange not grey
   - **TTL**: Auto
   - Click **Save**

2. Repeat for the apex `unity.unityailab.com` if you want both hostnames to resolve:
   - **Type**: `A`
   - **Name**: `unity` (expands to `unity.unityailab.com`)
   - Same IP, same proxy status, same TTL

3. (Optional) Add IPv6 records (`AAAA`) if your origin has IPv6 — same names, IPv6 address, proxied.

### 2.1b Verifying the DNS records propagated

```bash
# From any client
dig www.unity.unityailab.com +short
# Expect: a Cloudflare IP (104.x / 172.x / 162.x ranges — NOT your origin IP)
# If you see your origin IP, the proxy is OFF (grey cloud) — fix in dashboard

dig unity.unityailab.com +short
# Expect: a Cloudflare IP (proxied)

# Check propagation across global DNS resolvers
curl -s "https://dns.google/resolve?name=www.unity.unityailab.com&type=A" | jq
```

Cloudflare records propagate to the edge in seconds; downstream public DNS caching can take up to 5 minutes for the TTL=Auto value. If you see stale data, wait or flush your local resolver (`sudo systemd-resolve --flush-caches` on Linux, `ipconfig /flushdns` on Windows).

### 2.2 Origin TLS — Cloudflare Origin Cert

To use **Full (strict)** SSL mode (recommended — Cloudflare validates the origin cert), generate a Cloudflare Origin Certificate:

1. Cloudflare dashboard → **SSL/TLS → Origin Server** → **Create Certificate**
2. Defaults are fine — accept (RSA 2048, 15-year validity, hostnames `*.unityailab.com,unityailab.com`)
3. Cloudflare gives you a PEM cert + key — save to:
   - `/etc/ssl/cloudflare-origin.pem` (cert)
   - `/etc/ssl/cloudflare-origin.key` (key — `chmod 600`)

### 2.3 Origin reverse proxy

V4 serves HTTP on `:5051` — you need a TLS-terminating reverse proxy in front. Nginx config:

```nginx
server {
    listen 443 ssl http2;
    server_name www.unity.unityailab.com unity.unityailab.com;

    ssl_certificate     /etc/ssl/cloudflare-origin.pem;
    ssl_certificate_key /etc/ssl/cloudflare-origin.key;

    # Lock direct-to-origin access — only accept connections from Cloudflare IPs.
    # IP list: https://www.cloudflare.com/ips/
    include /etc/nginx/cloudflare-ips.conf;
    deny all;

    location / {
        proxy_pass http://127.0.0.1:5051;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name www.unity.unityailab.com unity.unityailab.com;
    return 301 https://www.unity.unityailab.com$request_uri;
}
```

Where `/etc/nginx/cloudflare-ips.conf` contains (refresh periodically):
```
allow 173.245.48.0/20;
allow 103.21.244.0/22;
# ... etc — full list at https://www.cloudflare.com/ips-v4/
allow 2400:cb00::/32;
# ... etc — IPv6 at https://www.cloudflare.com/ips-v6/
```

The bot itself still binds `127.0.0.1:5051` — nginx is the only thing that reaches it.

### 2.4 Origin firewall (DNS-proxy mode)

DNS-proxy mode needs inbound 80 + 443 open (nginx-to-Cloudflare). Restrict the source to Cloudflare's IP ranges so attackers can't bypass Cloudflare and hit your origin directly.

**Linux (UFW):**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH — admin IP only
sudo ufw allow from <your.admin.ip>/32 to any port 22 proto tcp comment "admin SSH"

# HTTP + HTTPS — Cloudflare IPv4 ranges only (https://www.cloudflare.com/ips-v4/)
# Listed here for reference; refresh quarterly via Cloudflare's IP list endpoint:
#   curl https://www.cloudflare.com/ips-v4/
for ip in \
  173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 \
  141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 \
  197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 \
  104.24.0.0/14 172.64.0.0/13 131.0.72.0/22; do
    sudo ufw allow from $ip to any port 80 proto tcp comment "Cloudflare HTTP"
    sudo ufw allow from $ip to any port 443 proto tcp comment "Cloudflare HTTPS"
done

# Cloudflare IPv6 ranges (https://www.cloudflare.com/ips-v6/)
for ip in \
  2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 \
  2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32; do
    sudo ufw allow from $ip to any port 80 proto tcp comment "Cloudflare HTTP v6"
    sudo ufw allow from $ip to any port 443 proto tcp comment "Cloudflare HTTPS v6"
done

sudo ufw enable
sudo ufw status verbose
```

DO NOT open `5051` to anything — only the local nginx reverse proxy on `127.0.0.1` should hit V4.

**Cloud provider security groups (AWS / GCP / etc.):**
- Inbound 22/tcp from your admin CIDR only
- Inbound 80/tcp + 443/tcp from Cloudflare's CIDR list (above)
- Inbound 5051/tcp: NEVER
- Outbound: allow all (or restrict to Pollinations, Discord, package mirrors)

**Refreshing Cloudflare IP list (Linux cron job — quarterly):**
```bash
# /etc/cron.d/cloudflare-ips
0 4 1 */3 * root /usr/local/sbin/refresh-cf-ips.sh && systemctl reload ufw
```

Where `/usr/local/sbin/refresh-cf-ips.sh` pulls the current list:
```bash
#!/usr/bin/env bash
set -euo pipefail
IP4=$(curl -sf https://www.cloudflare.com/ips-v4/)
IP6=$(curl -sf https://www.cloudflare.com/ips-v6/)
# ... script that rewrites ufw rules based on the new list ...
```

(Or use a config-management tool like Ansible / Chef / Puppet to manage these rules.)

### 2.5 Cloudflare-side hardening

Same as §1.8 — Full (strict), Always HTTPS, TLS 1.2+, WAF, Bot Fight Mode, optional Access.

---

## 3. Smoke tests after either path

```bash
# 1. DNS resolves
dig www.unity.unityailab.com +short
# Expect: a Cloudflare IP (104.x / 172.x / 162.x range)

# 2. HTTPS works
curl -I https://www.unity.unityailab.com/api/health
# Expect: 200 OK
#         server: cloudflare
#         cf-ray: <some-ray-id>

# 3. Chat endpoint reachable
curl -s -X POST https://www.unity.unityailab.com/api/health
# Expect: {"status": "ok", "configured": true, "timestamp": "..."}

# 4. WebSocket / SSE (if added later) — Cloudflare proxies WebSocket by default
#    in the orange-cloud setting. Test with:
# wscat -c wss://www.unity.unityailab.com/api/stream

# 5. Cache validation
curl -I https://www.unity.unityailab.com/web/style.css
# Expect: cf-cache-status: HIT (after a few requests)
```

---

## 3.5 Certificate renewal

**Tunnel mode**: nothing to renew. Cloudflare manages the public-facing cert; origin-side is plain HTTP over the tunnel. Cloudflare auto-renews the edge cert 30 days before expiry.

**DNS-proxy mode (Cloudflare Origin Certificate)**: 15-year validity by default — set a calendar reminder for year 14 to regenerate. No external CA / Let's Encrypt needed. To regenerate early:
1. Cloudflare dashboard → **SSL/TLS → Origin Server**
2. Click on the existing cert → **Revoke** (or just generate a new one)
3. **Create Certificate** → save the new PEM/key to `/etc/ssl/cloudflare-origin.{pem,key}`
4. `sudo systemctl reload nginx` (or restart whichever reverse proxy you use)

**DNS-proxy mode (Let's Encrypt — alternative)**: if you prefer not to use Cloudflare Origin Cert, you can use a normal Let's Encrypt cert via certbot. But you'll need to either (a) temporarily turn off the Cloudflare proxy (grey cloud) for the HTTP-01 challenge, or (b) use the DNS-01 challenge with the Cloudflare API plugin (`pip install certbot-dns-cloudflare`).

## 4. Update flow under Cloudflare

When updating V4:
1. SSH to origin host
2. Stop bot: `systemctl stop unitybot` (or kill `python web_server.py`)
3. `git pull` (or run `linux/update.sh` / `windows\update.bat`)
4. `pip install -r requirements.txt`
5. Start bot: `systemctl start unitybot` (or relaunch `python web_server.py`)
6. Cloudflare picks up the new responses automatically — no Cloudflare-side action needed unless you change DNS / tunnel config

For Cloudflare Tunnel updates:
```bash
sudo cloudflared update
sudo systemctl restart cloudflared
```

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `522 Connection timed out` from Cloudflare | Origin not reachable (firewall, service down) | `curl http://localhost:5051/api/health` on the origin to confirm V4 is up; check cloudflared logs (`journalctl -u cloudflared -n 100` or Windows Event Viewer) |
| `523 Origin is unreachable` | Cloudflare can't find origin IP | DNS-proxy path: check A record points to correct IP; Tunnel path: check `cloudflared` service status; `systemctl restart cloudflared` |
| `525 SSL handshake failed` | Full (strict) mode but origin cert missing/wrong | Tunnel path: shouldn't happen (no origin cert needed); DNS-proxy path: re-issue Cloudflare Origin Certificate (§2.2) |
| `526 Invalid SSL certificate` | Origin cert expired or hostname mismatch | Regenerate Cloudflare Origin Cert with the right SANs (§3.5) |
| `403 Forbidden` immediately | Cloudflare Access denying you | Check Access policy — add yourself to the allowed group; or temporarily disable Access during debugging |
| `1016 Origin DNS error` | Cloudflare can't resolve your origin hostname (DNS-proxy mode only, when CNAME-of-CNAME) | Use A record pointing to IP, not CNAME pointing to another hostname |
| Tunnel works but web UI shows setup wizard | `.env` on origin isn't fully configured | SSH to origin, run `python configure.py --print` to see current state |
| Images don't render in browser | Image URL points to localhost / wrong host | Web UI's chat returns external Pollinations URLs which the browser fetches directly — should work; if not, check browser console for CORS or mixed-content errors |
| `dig` returns origin IP instead of Cloudflare IP | Proxy status is grey-cloud (DNS only) | Edit the DNS record → flip to orange cloud (Proxied) |
| `dig` returns nothing / NXDOMAIN | DNS propagation incomplete OR nameservers not pointed at Cloudflare | Wait 5-30 min; verify nameservers via §0.2; check the registrar dashboard |
| Site loads but `Server: cloudflare` header missing | Bypassing Cloudflare (direct hit to origin IP) | Block direct origin access via firewall (§1.7b / §2.4) — clients should only reach you via Cloudflare |
| Tunnel keeps disconnecting | cloudflared can't maintain outbound 443 connection | Check outbound network policy / corporate firewall; whitelist `*.cloudflareaccess.com` + `*.cloudflare.com` for outbound HTTPS |
| `cloudflared service install` fails on Windows | Running without admin rights | Open PowerShell/CMD as Administrator and re-run |

---

## 6. Related docs

- [DEPLOYMENT.md](DEPLOYMENT.md) — origin systemd/Windows service setup (pair with this doc)
- [SECURITY.md](SECURITY.md) — auth + binding posture
- [SETUP.md](SETUP.md) — first-run configuration
- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) — upstream reference
