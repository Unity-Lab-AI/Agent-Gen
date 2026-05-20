<#
.SYNOPSIS
    Forgejo Setup & Verification Script for Windows — UAL-ClaudeWorkflow upstream-only
.DESCRIPTION
    Supports Setup mode and Verify mode. Warns about PATH reloads.
    Tested on Windows PowerShell 5.1 and PowerShell 7+.

.NOTES
    SCOPE — this script lives at the ROOT of the UAL-ClaudeWorkflow template repo
    (NOT under .claude/scripts/). It is UPSTREAM-ONLY admin onboarding tooling that
    helps a new Unity AI Lab founder set up their Windows machine for Forgejo SSH
    auth against git.unityailab.com BEFORE they run /unity-install to consume the
    .claude/ template into a downstream project.

    It is NOT template-shipped to consuming projects via /unity-install (the install
    flow only copies .claude/ content, not repo-root files). Operators who clone
    UAL-ClaudeWorkflow directly to do template work will find this script available
    at the repo root; operators who only consume the template via /unity-install on
    a downstream project will not see it (intended behavior).

    Use mode 1 (Setup) for a fresh Windows machine that hasn't yet been wired to
    git.unityailab.com — installs git, fj CLI, generates SSH key, registers with
    Forgejo, writes SSH config. Use mode 2 (Verify) anytime to confirm a current
    setup is healthy.
#>

$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Forgejo Setup & Verification Tool" -ForegroundColor Cyan
Write-Host "   Target: git.unityailab.com" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# Starting Menu
# ============================================
Write-Host "What would you like to do?"
Write-Host "1 = Run Setup (Guided installation)"
Write-Host "2 = Verify Current Setup"
$mode = Read-Host "Choose [1/2]"

if ($mode -eq "2") {
    # ============================================
    # VERIFY MODE
    # ============================================
    Write-Host ""
    Write-Host "=== Verification Report ===" -ForegroundColor Yellow
    Write-Host ""

    # Check Git
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Git is installed" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Git is NOT installed" -ForegroundColor Red
    }

    # Check fj
    if (Get-Command fj -ErrorAction SilentlyContinue) {
        Write-Host "[OK] fj is installed and in PATH" -ForegroundColor Green
        fj version
    } else {
        Write-Host "[MISSING] fj is NOT found in PATH" -ForegroundColor Red
    }

    # Check SSH key (private + public)
    $sshKey = "$env:USERPROFILE\.ssh\id_ed25519"
    $sshKeyPub = "$sshKey.pub"
    if ((Test-Path $sshKey) -and (Test-Path $sshKeyPub)) {
        Write-Host "[OK] SSH key exists" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] SSH key not found" -ForegroundColor Red
    }

    # Check SSH Config
    $sshConfig = "$env:USERPROFILE\.ssh\config"
    if ((Test-Path $sshConfig) -and (Select-String -Path $sshConfig -Pattern '^\s*Host\s+git\.unityailab\.com\s*$' -Quiet)) {
        Write-Host "[OK] SSH config for git.unityailab.com exists" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] SSH config for git.unityailab.com not found or incomplete" -ForegroundColor Red
    }

    # Check fj is actually authenticated to git.unityailab.com (not just installed).
    # Catches the half-broken setup where fj install + SSH key files exist but the
    # add-key call was never made or was made with malformed args.
    if (Get-Command fj -ErrorAction SilentlyContinue) {
        try {
            $whoamiOut = & fj --host git.unityailab.com whoami 2>&1
        } catch {
            $whoamiOut = $_.Exception.Message
        }
        if ($whoamiOut -match "currently signed in to") {
            Write-Host ("[OK] fj is authenticated: {0}" -f (($whoamiOut | Out-String).Trim())) -ForegroundColor Green
        } else {
            Write-Host "[MISSING] fj is NOT authenticated to git.unityailab.com" -ForegroundColor Red
            Write-Host "  Fix: fj --host git.unityailab.com auth add-key <USER> <TOKEN>" -ForegroundColor Yellow
        }
    }

    # Check SSH actually connects to Forgejo (validates pubkey is uploaded on server).
    # Forgejo always exits non-zero (no shell access) -scan stderr text for the success line.
    if (Get-Command ssh -ErrorAction SilentlyContinue) {
        try {
            $sshOut = & ssh -T -o BatchMode=yes -o ConnectTimeout=10 git@git.unityailab.com 2>&1
        } catch {
            $sshOut = $_.Exception.Message
        }
        if ($sshOut -match "successfully authenticated") {
            Write-Host ("[OK] SSH connects to Forgejo: {0}" -f (($sshOut | Out-String).Trim())) -ForegroundColor Green
        } else {
            Write-Host "[MISSING] SSH does NOT authenticate against git.unityailab.com" -ForegroundColor Red
            Write-Host ("  Output: {0}" -f (($sshOut | Out-String).Trim())) -ForegroundColor Yellow
            Write-Host "  Fix: upload your public key -either via 'fj --host git.unityailab.com user key upload ~/.ssh/id_ed25519.pub'" -ForegroundColor Yellow
            Write-Host "       -or- paste ~/.ssh/id_ed25519.pub contents into https://git.unityailab.com/user/settings/keys" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "Verification complete." -ForegroundColor Cyan
    exit
}

# ============================================
# SETUP MODE
# ============================================
Write-Host ""
Write-Host "Starting Setup Mode..." -ForegroundColor Green
Write-Host ""

function Get-Choice {
    param([string]$Message)
    do {
        $c = Read-Host "$Message [1=Automatic / 2=Manual]"
    } while ($c -notin @('1','2'))
    return $c
}

function Get-YesNo {
    param([string]$Message)
    do {
        $c = Read-Host "$Message [y/N]"
        if ([string]::IsNullOrWhiteSpace($c)) { $c = 'n' }
    } while ($c -notin @('y','Y','n','N'))
    return ($c -in @('y','Y'))
}

# ============================================
# Phase 1: Git
# ============================================
Write-Host "[Phase 1] Git Installation" -ForegroundColor Yellow
$choice = Get-Choice "Install Git"

if ($choice -eq "1") {
    Write-Host "Resolving latest Git for Windows release..." -ForegroundColor Green
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/git-for-windows/git/releases/latest" `
            -Headers @{ "User-Agent" = "ForgejoUserSetup" }
        $asset = $rel.assets `
            | Where-Object { $_.name -match '^Git-.*-64-bit\.exe$' } `
            | Select-Object -First 1
        if (-not $asset) {
            throw "no 64-bit installer asset found in latest release"
        }
        $installer = "$env:TEMP\GitInstaller.exe"
        Write-Host ("Downloading {0}..." -f $asset.name) -ForegroundColor Green
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $installer -UseBasicParsing
        Start-Process $installer -ArgumentList "/VERYSILENT","/NORESTART" -Wait
        Write-Host "Git installed. You may need to restart your terminal." -ForegroundColor Green
    } catch {
        Write-Host ("Git auto-install failed: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-Host "Please install manually from https://gitforwindows.org/" -ForegroundColor Yellow
        Read-Host "Press Enter when done"
    }
} else {
    Write-Host "Please install Git from https://gitforwindows.org/"
    Read-Host "Press Enter when done"
}

# Refresh PATH for the current session so subsequent steps see newly-installed binaries.
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")

# ============================================
# Phase 2: SSH Key
# ============================================
Write-Host ""
Write-Host "[Phase 2] SSH Key" -ForegroundColor Yellow
$choice = Get-Choice "Generate SSH Key"

$sshDir = "$env:USERPROFILE\.ssh"
$sshKeyPath = "$sshDir\id_ed25519"

if ($choice -eq "1") {
    # Pre-create the .ssh dir -ssh-keygen will fail on a fresh Windows install otherwise.
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null

    $proceed = $true
    if (Test-Path $sshKeyPath) {
        Write-Host "An existing key was found at $sshKeyPath" -ForegroundColor Yellow
        $proceed = Get-YesNo "Overwrite it?"
        if (-not $proceed) {
            Write-Host "Keeping existing SSH key." -ForegroundColor Green
        }
    }

    if ($proceed) {
        # Delete any existing key files first so ssh-keygen doesn't hit its
        # interactive "overwrite y/n" prompt (which would hang this script).
        if (Test-Path $sshKeyPath) { Remove-Item $sshKeyPath -Force }
        if (Test-Path "$sshKeyPath.pub") { Remove-Item "$sshKeyPath.pub" -Force }

        # Direct invocation via splatting handles the empty -N "" passphrase arg
        # without tripping Start-Process's "ArgumentList cannot be null or empty"
        # validation, which fires when any element in the array is "" (the trap the
        # previous Start-Process version hit).
        $kgArgs = @(
            "-t","ed25519",
            "-C","$env:USERNAME@$env:COMPUTERNAME",
            "-f",$sshKeyPath,
            "-N","",
            "-q"
        )
        & ssh-keygen @kgArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Host ("ssh-keygen exited with code {0}" -f $LASTEXITCODE) -ForegroundColor Red
        } else {
            Write-Host "SSH key generated." -ForegroundColor Green
        }
    }

    if (Test-Path "$sshKeyPath.pub") {
        Write-Host ""
        Write-Host "Add this public key to https://git.unityailab.com/user/settings/keys :" -ForegroundColor Yellow
        Get-Content "$sshKeyPath.pub"
        Write-Host ""
        Read-Host "Press Enter after adding the key"
    }
} else {
    Write-Host "Run in any PowerShell window with OpenSSH installed:"
    Write-Host "  ssh-keygen -t ed25519 -f `"$sshKeyPath`""
    Read-Host "Press Enter when done"
}

# ============================================
# Phase 3: SSH Config
# ============================================
Write-Host ""
Write-Host "[Phase 3] SSH Config" -ForegroundColor Yellow
$choice = Get-Choice "Configure SSH"

$sshConfigPath = "$sshDir\config"
if ($choice -eq "1") {
    New-Item -ItemType Directory -Path (Split-Path $sshConfigPath) -Force | Out-Null

    $block = @"
Host git.unityailab.com
    HostName git.unityailab.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
"@

    $alreadyConfigured = $false
    if (Test-Path $sshConfigPath) {
        $alreadyConfigured = Select-String -Path $sshConfigPath `
            -Pattern '^\s*Host\s+git\.unityailab\.com\s*$' -Quiet
    }

    if ($alreadyConfigured) {
        Write-Host "SSH config already has a Host entry for git.unityailab.com -leaving it alone." -ForegroundColor Green
    } else {
        # Append, don't clobber: any existing Host entries for other servers must
        # survive. -Encoding ascii avoids the UTF-8 BOM that Windows PowerShell 5.1
        # writes by default (OpenSSH chokes on BOM in ~/.ssh/config on some builds).
        $prefix = ""
        if ((Test-Path $sshConfigPath) -and ((Get-Item $sshConfigPath).Length -gt 0)) {
            $prefix = "`r`n"
        }
        Add-Content -Path $sshConfigPath -Value ($prefix + $block) -Encoding ascii
        Write-Host "SSH config updated (appended)." -ForegroundColor Green
    }
} else {
    Write-Host "Manually add the Host block for git.unityailab.com in: $sshConfigPath"
    Read-Host "Press Enter when done"
}

# ============================================
# Phase 4: fj Installation (with PATH warning)
# ============================================
Write-Host ""
Write-Host "[Phase 4] fj CLI Installation" -ForegroundColor Yellow
$choice = Get-Choice "Install fj"

if ($choice -eq "1") {
    Write-Host "Downloading latest fj..." -ForegroundColor Green
    try {
        $release = Invoke-RestMethod `
            -Uri "https://codeberg.org/api/v1/repos/forgejo-contrib/forgejo-cli/releases?limit=1" `
            -Headers @{ "User-Agent" = "ForgejoUserSetup" }
        if (-not $release -or $release.Count -eq 0) {
            throw "no releases returned from Codeberg API"
        }

        # Tighten the asset match: x86_64 Windows .zip only.
        $asset = $release[0].assets `
            | Where-Object { $_.name -match '^forgejo-cli-x86_64-windows\.zip$' } `
            | Select-Object -First 1
        if (-not $asset) {
            throw "no x86_64-windows .zip asset in latest release"
        }

        $fjDir = "$env:LOCALAPPDATA\Programs\fj"
        New-Item -ItemType Directory -Path $fjDir -Force | Out-Null

        $zipPath = Join-Path $fjDir $asset.name
        Write-Host ("Downloading {0}..." -f $asset.name) -ForegroundColor Green
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing

        Write-Host "Extracting..." -ForegroundColor Green
        Expand-Archive -Path $zipPath -DestinationPath $fjDir -Force
        Remove-Item $zipPath -Force

        # Find the .exe the release shipped (binary may be `fj.exe` or `forgejo-cli.exe`)
        # and normalize the name to `fj.exe` so PATH usage matches the Linux convention.
        $exe = Get-ChildItem -Path $fjDir -Filter "*.exe" -File -Recurse `
            | Select-Object -First 1
        if (-not $exe) {
            throw "no .exe found in the extracted archive under $fjDir"
        }
        $finalExe = Join-Path $fjDir "fj.exe"
        if ($exe.FullName -ne $finalExe) {
            Move-Item -Path $exe.FullName -Destination $finalExe -Force
        }

        # Persist to user PATH so future sessions pick it up automatically.
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($null -eq $userPath) { $userPath = "" }
        if ($userPath -notlike "*$fjDir*") {
            $newPath = if ($userPath) { "$userPath;$fjDir" } else { $fjDir }
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        }
        # And refresh THIS session so the subsequent `fj` reference works without
        # the user having to restart their terminal mid-script.
        if ($env:Path -notlike "*$fjDir*") {
            $env:Path = "$env:Path;$fjDir"
        }

        Write-Host "fj installed at $finalExe" -ForegroundColor Green
        Write-Host "NOTE: New terminals will pick up the PATH change automatically." -ForegroundColor Yellow
    } catch {
        Write-Host ("Automatic install failed: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-Host "Download fj manually from: https://codeberg.org/forgejo-contrib/forgejo-cli/releases/latest" -ForegroundColor Yellow
    }
} else {
    Write-Host "Download fj from: https://codeberg.org/forgejo-contrib/forgejo-cli/releases/latest"
    Read-Host "Press Enter when done"
}

# ============================================
# Phase 5: fj Auth (auto + manual paths)
# ============================================
Write-Host ""
Write-Host "[Phase 5] Authenticate fj" -ForegroundColor Yellow
Write-Host "fj signature: fj --host <HOST> auth add-key <USER> <TOKEN>"
Write-Host "Passing only a token (no USER) makes fj parse the token AS the username -broken."
Write-Host "Create a token at: https://git.unityailab.com/user/settings/applications"
Write-Host ""

$fjHost = "git.unityailab.com"
$choice = Get-Choice "Authenticate fj"

if ($choice -eq "1") {
    # Auto: prompt for username + token, run add-key, verify via whoami, then offer pubkey upload.
    if (-not (Get-Command fj -ErrorAction SilentlyContinue)) {
        Write-Host "fj not on PATH yet. Open a NEW terminal and re-run Setup or use Manual." -ForegroundColor Red
    } else {
        $fjUser = Read-Host "Your Forgejo username (NOT email)"
        if ([string]::IsNullOrWhiteSpace($fjUser)) {
            Write-Host "Username empty -skipping auto auth." -ForegroundColor Red
        } else {
            $fjTokenSecure = Read-Host "Paste your Forgejo token" -AsSecureString
            $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($fjTokenSecure)
            $fjToken = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) | Out-Null

            if ([string]::IsNullOrWhiteSpace($fjToken)) {
                Write-Host "Token empty -skipping auto auth." -ForegroundColor Red
            } else {
                Write-Host ""
                Write-Host ("Running: fj --host {0} auth add-key {1} <token-redacted>" -f $fjHost,$fjUser) -ForegroundColor Green
                try {
                    & fj --host $fjHost auth add-key $fjUser $fjToken | Out-Null
                } catch {
                    Write-Host ("fj add-key threw: {0}" -f $_.Exception.Message) -ForegroundColor Red
                }

                # fj add-key sometimes exits non-zero even on success -trust `whoami` text instead.
                $whoami = & fj --host $fjHost whoami 2>&1
                if ($whoami -match "currently signed in to $([regex]::Escape($fjUser))@") {
                    Write-Host ("[OK] fj authed: {0}" -f (($whoami | Out-String).Trim())) -ForegroundColor Green

                    # Offer to auto-upload the SSH pubkey via fj API (saves a trip to the web UI).
                    if (Test-Path "$sshKeyPath.pub") {
                        $doUpload = Get-YesNo "Upload SSH public key to Forgejo now via fj?"
                        if ($doUpload) {
                            $keyTitle = "$env:USERNAME-$env:COMPUTERNAME-$(Get-Date -Format yyyyMMdd)"
                            Write-Host ("Uploading {0}.pub as title '{1}'..." -f $sshKeyPath,$keyTitle) -ForegroundColor Green
                            & fj --host $fjHost user key upload "$sshKeyPath.pub" --title $keyTitle
                            if ($LASTEXITCODE -eq 0) {
                                Write-Host "[OK] SSH public key uploaded." -ForegroundColor Green
                            } else {
                                Write-Host ("[FAIL] SSH key upload exited with code {0}. Upload manually at https://{1}/user/settings/keys" -f $LASTEXITCODE,$fjHost) -ForegroundColor Red
                            }
                        } else {
                            Write-Host "Skipped. Upload your public key later by either:" -ForegroundColor Yellow
                            Write-Host ("  fj --host {0} user key upload `"{1}.pub`"" -f $fjHost,$sshKeyPath)
                            Write-Host ("  -or- paste {0}.pub contents into https://{1}/user/settings/keys" -f $sshKeyPath,$fjHost)
                        }
                    } else {
                        Write-Host ("(No SSH public key found at {0}.pub -skipping upload step)" -f $sshKeyPath) -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "[FAIL] fj whoami did not confirm sign-in." -ForegroundColor Red
                    Write-Host ("whoami output: {0}" -f (($whoami | Out-String).Trim())) -ForegroundColor Red
                    Write-Host ("Re-run manually: fj --host {0} auth add-key <USER> <TOKEN>" -f $fjHost) -ForegroundColor Yellow
                }
            }
        }
    }
} else {
    # Manual: print the EXPLICIT two-arg form + the pubkey-upload reminder.
    Write-Host ""
    Write-Host "Run these commands yourself (in order):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # 1. Authenticate fj -BOTH positional args required (USER then TOKEN):"
    Write-Host ("  fj --host {0} auth add-key <YOUR_USERNAME> <YOUR_TOKEN>" -f $fjHost)
    Write-Host ""
    Write-Host "  # 2. Verify sign-in (should print 'currently signed in to <user>@<host>'):"
    Write-Host ("  fj --host {0} whoami" -f $fjHost)
    Write-Host ""
    Write-Host "  # 3. Upload your SSH public key -ONE of these two paths:"
    Write-Host ("  fj --host {0} user key upload `"{1}.pub`"" -f $fjHost,$sshKeyPath)
    Write-Host ("  -or- paste {0}.pub contents into https://{1}/user/settings/keys" -f $sshKeyPath,$fjHost)
    Write-Host ""
    Read-Host "Press Enter when done"
}

# ============================================
# Phase 6: Final Test (auto-run all three checks, capture pass/fail)
# ============================================
Write-Host ""
Write-Host "[Phase 6] Connection Tests" -ForegroundColor Yellow

# Guard: if either binary is missing we can't test -skip with a hint.
$sshOk = [bool](Get-Command ssh -ErrorAction SilentlyContinue)
$fjOk  = [bool](Get-Command fj  -ErrorAction SilentlyContinue)
if (-not $sshOk) { Write-Host "ssh not on PATH -Test 1 will be skipped." -ForegroundColor Yellow }
if (-not $fjOk)  { Write-Host "fj not on PATH -Tests 2 & 3 will be skipped. Open a NEW terminal." -ForegroundColor Yellow }

# Test 1: SSH auth.
# Forgejo always exits non-zero on `ssh -T` ("Forgejo does not provide shell access")
# so we cannot trust $LASTEXITCODE here -we scan stderr text for the success line.
Write-Host ""
Write-Host ("Test 1/3: ssh -T git@{0}" -f $fjHost) -ForegroundColor Cyan
if ($sshOk) {
    try {
        $sshOut = & ssh -T -o BatchMode=yes -o ConnectTimeout=10 "git@$fjHost" 2>&1
    } catch {
        $sshOut = $_.Exception.Message
    }
    if ($sshOut -match "successfully authenticated") {
        Write-Host ("[OK] SSH authenticated: {0}" -f (($sshOut | Out-String).Trim())) -ForegroundColor Green
    } else {
        Write-Host "[FAIL] SSH did not authenticate. Output:" -ForegroundColor Red
        Write-Host (($sshOut | Out-String).Trim()) -ForegroundColor Red
        Write-Host "Likely cause: SSH pubkey not uploaded to Forgejo, wrong key in ~/.ssh/config, or server-side block." -ForegroundColor Yellow
    }
} else {
    Write-Host "[SKIP] ssh missing from PATH." -ForegroundColor Yellow
}

# Test 2: fj whoami (scoped to --host since fj has no default-instance concept).
Write-Host ""
Write-Host ("Test 2/3: fj --host {0} whoami" -f $fjHost) -ForegroundColor Cyan
$whoami = $null
if ($fjOk) {
    try {
        $whoami = & fj --host $fjHost whoami 2>&1
    } catch {
        $whoami = $_.Exception.Message
    }
    if ($whoami -match "currently signed in to") {
        Write-Host ("[OK] fj: {0}" -f (($whoami | Out-String).Trim())) -ForegroundColor Green
    } else {
        Write-Host "[FAIL] fj is not authenticated. Output:" -ForegroundColor Red
        Write-Host (($whoami | Out-String).Trim()) -ForegroundColor Red
        Write-Host ("Fix: fj --host {0} auth add-key <USER> <TOKEN>" -f $fjHost) -ForegroundColor Yellow
    }
} else {
    Write-Host "[SKIP] fj missing from PATH." -ForegroundColor Yellow
}

# Test 3: fj user repos smoke (uses authed user from Test 2 if available).
Write-Host ""
if ($fjOk -and $whoami -match "currently signed in to (?<user>[^@]+)@") {
    $authedUser = $Matches['user']
    Write-Host ("Test 3/3: fj --host {0} user repos {1}" -f $fjHost,$authedUser) -ForegroundColor Cyan
    try {
        $repos = & fj --host $fjHost user repos $authedUser 2>&1
        $reposCode = $LASTEXITCODE
    } catch {
        $repos = $_.Exception.Message
        $reposCode = 1
    }
    if ($reposCode -eq 0) {
        Write-Host "[OK] fj user repos call succeeded. Output:" -ForegroundColor Green
        Write-Host (($repos | Out-String).Trim())
    } else {
        Write-Host ("[FAIL] fj user repos exited with code {0}. Output:" -f $reposCode) -ForegroundColor Red
        Write-Host (($repos | Out-String).Trim()) -ForegroundColor Red
    }
} else {
    Write-Host "Test 3/3: SKIPPED (no authed user available from Test 2)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup finished!" -ForegroundColor Green
