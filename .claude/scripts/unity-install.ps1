# .claude/scripts/unity-install.ps1
#
# Install the Unity AI Lab .claude/ template into a target directory (new or
# existing). PowerShell sibling of unity-install.sh.
#
# Usage:
#   pwsh -File .\.claude\scripts\unity-install.ps1
#   pwsh -File .\.claude\scripts\unity-install.ps1 C:\path\to\target

param(
    [string]$TargetDir = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git'
$Branch  = 'main'

if (-not (Test-Path -Path $TargetDir -PathType Container)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}
$TargetDir = (Resolve-Path $TargetDir).Path

# Prerequisites
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error '[unity-install] git not found on PATH'
    exit 1
}

$ClaudePath = Join-Path $TargetDir '.claude'
if (Test-Path -Path $ClaudePath -PathType Container) {
    Write-Error "[unity-install] $TargetDir\.claude\ already exists. Use /unity-update (or unity-update.ps1) to refresh existing."
    exit 2
}

# Temp dir + cleanup
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("unity-install-" + [System.Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

try {
    Write-Host "[unity-install] Cloning $RepoUrl ($Branch branch) to $TmpDir..."
    # git writes normal progress ("Cloning into '...'") to stderr. With $ErrorActionPreference='Stop'
    # AND `2>&1` merging, those stderr lines wrap as ErrorRecord and trigger a terminating error
    # before $LASTEXITCODE is checked. Drop EAP to 'Continue' for the native call, restore after,
    # then check the exit code.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & git clone --depth 1 --branch $Branch $RepoUrl (Join-Path $TmpDir 'repo')
    $cloneExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($cloneExit -ne 0) {
        Write-Error "[unity-install] git clone failed (exit $cloneExit)"
        exit 1
    }

    $RepoClaude = Join-Path $TmpDir 'repo\.claude'
    if (-not (Test-Path -Path $RepoClaude -PathType Container)) {
        Write-Error '[unity-install] cloned repo has no .claude/ — upstream layout may have changed'
        exit 1
    }

    Write-Host "[unity-install] Installing .claude/ to $TargetDir\..."
    Copy-Item -Path $RepoClaude -Destination $ClaudePath -Recurse -Force

    # Bring project-root .gitignore if target doesn't have one
    $RepoGitignore = Join-Path $TmpDir 'repo\.gitignore'
    $TargetGitignore = Join-Path $TargetDir '.gitignore'
    if (-not (Test-Path -Path $TargetGitignore -PathType Leaf) -and (Test-Path -Path $RepoGitignore -PathType Leaf)) {
        Copy-Item -Path $RepoGitignore -Destination $TargetGitignore -Force
        Write-Host '[unity-install] Installed project-root .gitignore'
    }

    # Layer 0 of the .claude/ IP-boundary defense-in-depth — ensure .gitignore
    # has a blanket `.claude/` exclude so accidental `git add -A` cannot stage
    # the workflow into the target project. See CONSTRAINTS.md §LAW — .CLAUDE
    # WORKFLOW IP BOUNDARY. Idempotent.
    if (-not (Test-Path -Path $TargetGitignore -PathType Leaf)) {
        New-Item -ItemType File -Path $TargetGitignore -Force | Out-Null
    }
    $existingLines = @()
    if (Test-Path -Path $TargetGitignore -PathType Leaf) {
        $existingLines = Get-Content -Path $TargetGitignore -ErrorAction SilentlyContinue
    }
    $alreadyExcluded = $false
    foreach ($line in $existingLines) {
        if ($line -match '^\.claude/?\s*$') { $alreadyExcluded = $true; break }
    }
    if ($alreadyExcluded) {
        Write-Host '[unity-install] .gitignore already excludes .claude/ — Layer 0 already in place'
    } else {
        $block = @(
            '',
            '# Unity AI Lab .claude/ workflow — proprietary, never commit to public repos.',
            '# See .claude/CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW IP BOUNDARY for full text.',
            '# Removal sanctioned only via /claude-publish after gh confirms private + Unity-Lab-AI.',
            '.claude/'
        )
        Add-Content -Path $TargetGitignore -Value $block
        Write-Host "[unity-install] Added .claude/ exclude to $TargetGitignore (Layer 0 IP-boundary defense-in-depth)"
    }

    Write-Host ''
    Write-Host '[unity-install] Install complete.'
    Write-Host ''
    Write-Host "  Target:       $TargetDir"
    Write-Host "  Source:       $RepoUrl ($Branch)"
    Write-Host ''
    Write-Host '  Next steps:'
    Write-Host "    cd $TargetDir"
    if (Test-Path -Path (Join-Path $TargetDir '.claude\start.bat') -PathType Leaf) {
        Write-Host '    .\.claude\start.bat          # Windows launcher (installs memory + activates Unity + runs /workflow)'
    }
    if (Test-Path -Path (Join-Path $TargetDir '.claude\start.sh') -PathType Leaf) {
        Write-Host '    bash ./.claude/start.sh      # macOS/Linux/Git Bash launcher (same flow)'
    }
    Write-Host ''
    Write-Host "  The launcher handles memory installation idempotently on first run."
    Write-Host "  See $TargetDir\.claude\README.md for full documentation."

} finally {
    if (Test-Path -Path $TmpDir) {
        Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit 0
