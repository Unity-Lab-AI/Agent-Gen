<#
.SYNOPSIS
  Install the .claude/tools toolkit into a project, or globally for every project.

.EXAMPLES
  .\install.ps1                      # into .\.claude\tools (current project)
  .\install.ps1 -Target C:\code\app  # into that project's .claude\tools
  .\install.ps1 -Global              # into $HOME\.claude\tools (all projects)
  .\install.ps1 -NoDeps              # copy files only, skip pip/playwright
#>
param(
  [string]$Target = ".",
  [switch]$Global,
  [switch]$NoDeps,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dest = if ($Global) { Join-Path $HOME ".claude\tools" } else { Join-Path (Resolve-Path $Target) ".claude\tools" }

if ($src -eq $dest) { Write-Host "Already installed here: $dest" -ForegroundColor Yellow }
else {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  $files = @("doctor.py", "screen.py", "browser.py", "web.py", "README.md",
             "requirements.txt", "LICENSE", "install.ps1", "install.sh")
  foreach ($f in $files) {
    $from = Join-Path $src $f
    if (-not (Test-Path $from)) { continue }
    $to = Join-Path $dest $f
    if ((Test-Path $to) -and -not $Force) { Write-Host "  skip (exists) $f" -ForegroundColor DarkGray; continue }
    Copy-Item $from $to -Force
    Write-Host "  copied $f" -ForegroundColor Green
  }
  Write-Host "`nInstalled to $dest"
}

$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $py) { Write-Host "`nPython not found on PATH - install Python 3.8+ then run doctor.py --install" -ForegroundColor Yellow; exit 1 }

if ($NoDeps) {
  Write-Host "`nSkipping dependencies. Check them later with:"
  Write-Host "  python `"$dest\doctor.py`""
} else {
  Write-Host "`n--- checking dependencies ---"
  & $py.Source (Join-Path $dest "doctor.py") --install
}

Write-Host @"

Done. Try:
  python "$dest\doctor.py"
  python "$dest\web.py" get https://example.com
  python "$dest\browser.py" open https://example.com
  python "$dest\screen.py" shot

Tell Claude the toolkit exists by pasting the block from README.md
("Tell Claude about it") into your project's CLAUDE.md.
"@
