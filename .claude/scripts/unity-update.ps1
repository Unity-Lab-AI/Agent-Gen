# .claude/scripts/unity-update.ps1
#
# Update the current project's .claude/ template from the upstream main branch.
# PowerShell sibling of unity-update.sh — same logic, native Windows syntax.
#
# Usage:
#   pwsh -File .\.claude\scripts\unity-update.ps1
#   (or just `.\.claude\scripts\unity-update.ps1` in a PowerShell session)

$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git'
$Branch  = 'main'
$ProjectDir = if ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { (Get-Location).Path }

# Prerequisites
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error '[unity-update] git not found on PATH'
    exit 1
}
if (-not (Test-Path -Path (Join-Path $ProjectDir '.claude') -PathType Container)) {
    Write-Error "[unity-update] $ProjectDir has no .claude/ folder. Run /unity-install instead to install fresh."
    exit 1
}
if (-not (Test-Path -Path (Join-Path $ProjectDir '.claude\CLAUDE.md') -PathType Leaf)) {
    Write-Error "[unity-update] $ProjectDir\.claude\ exists but doesn't look like a Unity AI Lab template (no CLAUDE.md). Aborting."
    exit 1
}

# Temp dir + cleanup
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("unity-update-" + [System.Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

try {
    # Clone (shallow, only main branch)
    Write-Host "[unity-update] Cloning $RepoUrl ($Branch branch) to $TmpDir..."
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
        Write-Error "[unity-update] git clone failed (exit $cloneExit)"
        exit 1
    }

    $RepoClaude = Join-Path $TmpDir 'repo\.claude'
    if (-not (Test-Path -Path $RepoClaude -PathType Container)) {
        Write-Error '[unity-update] cloned repo has no .claude/ — upstream layout may have changed'
        exit 1
    }

    # Backup current settings.json
    $SettingsPath = Join-Path $ProjectDir '.claude\settings.json'
    if (Test-Path -Path $SettingsPath -PathType Leaf) {
        $Ts = Get-Date -Format 'yyyy-MM-ddTHH-mm-ssZ'
        $Backup = "$SettingsPath.backup-$Ts"
        Copy-Item -Path $SettingsPath -Destination $Backup -Force
        Write-Host "[unity-update] Backed up current settings.json -> settings.json.backup-$Ts"
        Write-Host "                (manually merge any project-specific customizations after the update)"
    }

    # Sync framework directories (full overwrite per directory)
    $FrameworkDirs = @('agents', 'commands', 'hooks', 'memory-templates', 'templates', 'bin', 'scripts')
    foreach ($d in $FrameworkDirs) {
        $Src = Join-Path $RepoClaude $d
        $Dst = Join-Path $ProjectDir ".claude\$d"
        if (Test-Path -Path $Src -PathType Container) {
            if (Test-Path -Path $Dst) { Remove-Item -Path $Dst -Recurse -Force }
            Copy-Item -Path $Src -Destination $Dst -Recurse -Force
            Write-Host "[unity-update] Synced .claude\$d\"
        }
    }

    # Sync framework top-level files
    $FrameworkFiles = @('CLAUDE.md', 'CONSTRAINTS.md', 'WORKFLOW.md', 'README.md', 'ImHanddicapped.txt', 'start.sh', 'start.bat', 'settings.json')
    foreach ($f in $FrameworkFiles) {
        $Src = Join-Path $RepoClaude $f
        $Dst = Join-Path $ProjectDir ".claude\$f"
        if (Test-Path -Path $Src -PathType Leaf) {
            Copy-Item -Path $Src -Destination $Dst -Force
            Write-Host "[unity-update] Synced .claude\$f"
        }
    }

    # Sync project-root .gitignore (template version saved aside if differs)
    $RepoGitignore = Join-Path $TmpDir 'repo\.gitignore'
    $ProjGitignore = Join-Path $ProjectDir '.gitignore'
    if (Test-Path -Path $RepoGitignore -PathType Leaf) {
        if (-not (Test-Path -Path $ProjGitignore -PathType Leaf)) {
            Copy-Item -Path $RepoGitignore -Destination $ProjGitignore -Force
            Write-Host "[unity-update] Created project .gitignore from template"
        } else {
            $RepoHash = (Get-FileHash -Path $RepoGitignore -Algorithm SHA256).Hash
            $ProjHash = (Get-FileHash -Path $ProjGitignore -Algorithm SHA256).Hash
            if ($RepoHash -ne $ProjHash) {
                Copy-Item -Path $RepoGitignore -Destination "$ProjGitignore.template" -Force
                Write-Host '[unity-update] Existing .gitignore differs from template — saved template as .gitignore.template for manual merge'
            }
        }
    }

    # Refresh user-profile memory folder
    $MemoryTemplates = Join-Path $ProjectDir '.claude\memory-templates'
    if (Test-Path -Path $MemoryTemplates -PathType Container) {
        $Encoded = $ProjectDir
        foreach ($ch in @(':', '/', '\', '.', ' ', '(', ')')) {
            $Encoded = $Encoded.Replace($ch, '-')
        }
        $UserProfile = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
        $MemoryDir = Join-Path $UserProfile ".claude\projects\$Encoded\memory"
        if (-not (Test-Path -Path $MemoryDir -PathType Container)) {
            New-Item -ItemType Directory -Path $MemoryDir -Force | Out-Null
        }
        Get-ChildItem -Path $MemoryTemplates -Filter '*.md' | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $MemoryDir -Force
        }
        Write-Host "[unity-update] Refreshed user-profile memory folder at $MemoryDir"
    }

    # Done
    Write-Host ''
    Write-Host '[unity-update] Update complete.'
    Write-Host ''
    Write-Host "  Project:      $ProjectDir"
    Write-Host "  Source:       $RepoUrl ($Branch)"
    Write-Host '  Preserved:    settings.local.json, .env, user.json, user-context\, project-config.json, machine-local state files'
    Write-Host ''
    $Backups = Get-ChildItem -Path (Join-Path $ProjectDir '.claude') -Filter 'settings.json.backup-*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    if ($Backups) {
        Write-Host '  Note: settings.json was overwritten. If you had project-specific customizations,'
        Write-Host '        diff against the backup and merge:'
        Write-Host ('        ' + $Backups[0].FullName)
        Write-Host ''
    }
    Write-Host '  Next step:    re-run start.bat (or restart Claude Code) to pick up the refreshed memory layer.'

} finally {
    if (Test-Path -Path $TmpDir) {
        Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit 0
