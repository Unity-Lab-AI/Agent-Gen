# Setup and uninstaller: stop everything Agent Gen runs before any file in the install folder is touched.
# Kills Agent Gen.exe, anything whose exe lives under the folder (her runtimes and venvs in <folder>\data), python/ollama
# started with the folder on their command line, her brain server on :11435, and everything those started; waits until they are gone and the app's
# files can be written. Never touches the setup or uninstaller running this. Log: <folder>\data\logs\setup.log
param([Parameter(Mandatory = $true)][string]$Dir)
$ErrorActionPreference = 'SilentlyContinue'
$Dir = $Dir.TrimEnd('\')
$root = $Dir + '\'
$logDir = Join-Path $Dir 'data\logs'
$log = if (Test-Path $logDir) { Join-Path $logDir 'setup.log' } else { Join-Path $env:TEMP 'agentgen-setup.log' }
function L($m) { ('{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'), $m) | Out-File -Append -Encoding utf8 $log }
$me = $PID
$caller = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
function Spared($p) {
  $p.ProcessId -eq $me -or $p.ProcessId -eq $caller -or $p.Name -like 'Uninstall*' -or $p.Name -like 'Au_*' -or
  $p.Name -like 'Un_*' -or $p.Name -like 'old-uninstaller*' -or $p.Name -like 'AgentGen-Setup*'
}
function Targets {
  $all = @(Get-CimInstance Win32_Process)
  # her private brain server (ollama on :11435) may run from outside the folder; it holds her models in <folder>\data
  $brain = @(Get-NetTCPConnection -LocalPort 11435 -State Listen | ForEach-Object { $_.OwningProcess })
  $hit = @{}
  foreach ($p in $all) {
    if (Spared $p) { continue }
    if ($p.Name -eq 'Agent Gen.exe' -or $brain -contains $p.ProcessId -or
        ($p.ExecutablePath -and $p.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) -or
        (($p.Name -in 'python.exe', 'pythonw.exe', 'ollama.exe', 'ollama_llama_server.exe') -and $p.CommandLine -and
          $p.CommandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0)) { $hit[$p.ProcessId] = $p }
  }
  # and everything they started (sidecars, brain runners, consoles), never a setup or uninstaller
  do {
    $grew = $false
    foreach ($p in $all) {
      if (-not $hit.ContainsKey($p.ProcessId) -and $hit.ContainsKey($p.ParentProcessId) -and -not (Spared $p) -and
          $p.CreationDate -ge $hit[$p.ParentProcessId].CreationDate) {   # a reused parent id is not a parent
        $hit[$p.ProcessId] = $p; $grew = $true
      }
    }
  } while ($grew)
  $hit.Values
}
L "stop: $Dir"
for ($i = 0; $i -lt 60; $i++) {
  $t = @(Targets)
  if ($t.Count -eq 0) { break }
  foreach ($p in $t) {
    if ($i % 10 -eq 0) { L ('kill {0} {1} {2}' -f $p.ProcessId, $p.Name, $p.ExecutablePath) }
    Stop-Process -Id $p.ProcessId -Force
  }
  Start-Sleep -Milliseconds 500
}
foreach ($p in @(Targets)) { L ('STILL RUNNING {0} {1} {2}' -f $p.ProcessId, $p.Name, $p.ExecutablePath) }
# a killed process can hold its files for a moment while the GPU driver lets go: wait until they open for writing
foreach ($f in @((Join-Path $Dir 'Agent Gen.exe'), (Join-Path $Dir 'resources\app.asar'))) {
  if (-not (Test-Path $f)) { continue }
  for ($i = 0; $i -lt 60; $i++) {
    try { $h = [IO.File]::Open($f, 'Open', 'ReadWrite', 'None'); $h.Close(); break }
    catch { if ($i -eq 0) { L "busy: $f" }; Start-Sleep -Milliseconds 500 }
  }
}
L 'stop: done'
