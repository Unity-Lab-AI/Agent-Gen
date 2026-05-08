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
# The repo is PRIVATE — raw https://raw.githubusercontent.com/... URLs return
# 404 to unauthenticated requests. Use the GitHub CLI (`gh`) which authenticates
# via your existing gh login.
#
# Prereqs: `gh` installed + authed (`gh auth login`); `git` on PATH.
#
# Run via gh-pipe (one-line install):
#   gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | iex
#
# Or download + inspect first (safer):
#   gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | Out-File -Encoding utf8 install-unity.ps1
#   notepad install-unity.ps1   # read it
#   pwsh -File install-unity.ps1
#   Remove-Item install-unity.ps1
#
# Alternative — clone-and-run (no gh CLI required, just authed git):
#   $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.Guid]::NewGuid().ToString('N').Substring(0,8))
#   git clone --depth 1 https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git $tmp
#   & "$tmp\install-unity-globally.ps1"
#   Remove-Item -Path $tmp -Recurse -Force

$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git'
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
    & git clone --depth 1 --branch $Branch $RepoUrl (Join-Path $TmpDir 'repo') 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[unity-bootstrap] git clone failed'
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
    Write-Host '    /unity-install                         (installs .claude/ into the current working directory)'
    Write-Host '    /unity-install C:\path\to\new-project  (installs into a specific target)'
    Write-Host ''
    Write-Host '  After install, cd into the target and run:'
    Write-Host '    .\.claude\start.bat       # Windows native'
    Write-Host '    bash ./.claude/start.sh   # Linux/macOS/Git Bash'
    Write-Host ''
    Write-Host '  To update an existing install: cd into a project with .claude/, then run /unity-update.'

} finally {
    if (Test-Path -Path $TmpDir) {
        Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit 0
