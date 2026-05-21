# install-unity-globally.ps1
#
# One-shot bootstrap (PowerShell sibling of install-unity-globally.sh):
# clones the Unity AI Lab template repo into a temp dir, copies ONLY the
# /unity-install slash command file into the user's global Claude Code
# commands folder ($HOME\.claude\commands\), then cleans up the temp.
#
# After running this, /unity-install is available in ANY Claude Code session
# the user starts on this machine.
#
# Canonical upstream is Unity AI Lab's self-hosted Forgejo at
# git.unityailab.com — PRIVATE, SSH-key auth via the operator's registered
# ed25519 key (see docs/ADMIN-ONBOARDING.md §2 for first-time setup).
#
# Prereqs: `git` on PATH; SSH key registered on your Forgejo account at
# https://git.unityailab.com/<your-handle>/settings/keys (or under the
# UnityAILab org if you're an org member with access).
#
# Run via clone-pipe (one-line install — RECOMMENDED):
#   $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.Guid]::NewGuid().ToString('N').Substring(0,8)); git clone --depth 1 git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git $tmp; & "$tmp\install-unity-globally.ps1"; Remove-Item -Path $tmp -Recurse -Force
#
# Or clone + inspect first (safer):
#   git clone --depth 1 git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git $env:TEMP\ual
#   notepad "$env:TEMP\ual\install-unity-globally.ps1"   # read it
#   & "$env:TEMP\ual\install-unity-globally.ps1"
#   Remove-Item -Path "$env:TEMP\ual" -Recurse -Force
#
# Override the upstream URL via env (for testing / mirrors):
#   $env:UNITY_REPO_URL = 'git@some-mirror:org/repo.git'; .\install-unity-globally.ps1

$ErrorActionPreference = 'Stop'

# Override via UNITY_REPO_URL env var if mirroring/testing against another host.
$RepoUrl = if ($env:UNITY_REPO_URL) { $env:UNITY_REPO_URL } else { 'git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git' }
$Branch  = 'main'
$UserGlobalCommands = Join-Path $HOME '.claude\commands'

Write-Host "[unity-bootstrap] Installing /unity-install into $UserGlobalCommands\"
Write-Host ''

# Prerequisites
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error '[unity-bootstrap] git not found on PATH. Install git first, then re-run.'
    exit 1
}

# Temp dir + cleanup
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("unity-bootstrap-" + [System.Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

try {
    Write-Host "[unity-bootstrap] Cloning $RepoUrl ($Branch) to $TmpDir..."
    # Native commands like `git` write normal progress (e.g. "Cloning into '...'") to stderr.
    # With $ErrorActionPreference='Stop' AND `2>&1` merging, those stderr lines get wrapped as
    # ErrorRecord objects and trigger a terminating error before $LASTEXITCODE is even checked.
    # Drop the EAP to 'Continue' just for the native call, then restore — and let stderr flow
    # to the console directly instead of merging it into the pipeline.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & git clone --depth 1 --branch $Branch $RepoUrl (Join-Path $TmpDir 'repo')
    $cloneExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($cloneExit -ne 0) {
        Write-Error "[unity-bootstrap] git clone failed (exit $cloneExit)"
        exit 1
    }

    $SrcFile = Join-Path $TmpDir 'repo\.claude\commands\unity-install.md'
    if (-not (Test-Path -Path $SrcFile -PathType Leaf)) {
        Write-Error '[unity-bootstrap] cloned repo has no .claude\commands\unity-install.md — upstream layout may have changed'
        exit 1
    }

    if (-not (Test-Path -Path $UserGlobalCommands -PathType Container)) {
        New-Item -ItemType Directory -Path $UserGlobalCommands -Force | Out-Null
    }
    Copy-Item -Path $SrcFile -Destination (Join-Path $UserGlobalCommands 'unity-install.md') -Force

    Write-Host "[unity-bootstrap] Installed: $UserGlobalCommands\unity-install.md"
    Write-Host ''
    Write-Host '  Done. In ANY Claude Code session on this machine, you can now run:'
    Write-Host '    /unity-install                                       (main branch into current dir)'
    Write-Host '    /unity-install develop                               (develop branch into current dir)'
    Write-Host '    /unity-install feature/foo                           (any feature branch into current dir)'
    Write-Host '    /unity-install C:\path\to\new-project                (main branch into a specific target)'
    Write-Host '    /unity-install develop C:\path\to\new-project        (develop branch into a specific target)'
    Write-Host ''
    Write-Host '  After install, cd into the target and run:'
    Write-Host '    .\.claude\start.bat       # Windows native'
    Write-Host '    bash ./.claude/start.sh   # Linux/macOS/Git Bash'
    Write-Host ''
    Write-Host '  To refresh an existing install, /unity-update is an alias of /unity-install — same flow,'
    Write-Host '  same args. Both are idempotent: running on an existing .claude\ stages your personal files'
    Write-Host '  (settings.local.json, .env, user.json, user-context\, etc.), drops the fresh framework, and'
    Write-Host '  restores the personal files. Project root stays clean.'

} finally {
    if (Test-Path -Path $TmpDir) {
        Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit 0
