# PreceptorOS · Windows acceptance run for an external tester. NOT RUN BY US: Windows state is NO_DATA until a
# third party returns the receipt this prints. Procedure and what to send back: empaquetado/windows/ACCEPTANCE.md
#
# Privacy: the receipt carries PASS/FAIL/NO_DATA words, version numbers and short hashes ONLY. No user name, no
# path, no host name, no IP, no message text. Read the JSON before you send it; you may redact anything.
#
#   powershell -ExecutionPolicy Bypass -File acceptance.ps1 -Installer .\install.ps1 -ExpectedSha256 <digest>
param([Parameter(Mandatory)][string]$Installer, [Parameter(Mandatory)][string]$ExpectedSha256, [int]$Port = 8740)
$ErrorActionPreference = 'Continue'
$R = [ordered]@{ schema = 'preceptoros.windows-acceptance/1' }
function Step($k, $v) { $R[$k] = $v; Write-Host ('{0,-30} {1}' -f $k, $v) }
$U = "http://127.0.0.1:$Port"
function Up { for ($i = 0; $i -lt 60; $i++) { try { Invoke-WebRequest "$U/api/estado" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { Start-Sleep -Milliseconds 500 } }; return $false }
function DataHash {
  $d = "$HOME\.preceptoros"; if (-not (Test-Path $d)) { return 'none' }
  $lines = Get-ChildItem $d -Recurse -File | Where-Object { $_.Name -notmatch '\.(log|pid)$|-(shm|wal)$' } | Sort-Object FullName |
    ForEach-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
  $b = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
  return ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($b)) -replace '-', '').Substring(0, 16).ToLower()
}
Step os ("Windows " + [Environment]::OSVersion.Version.Major + "." + [Environment]::OSVersion.Version.Build)
Step python ((python -V 2>&1) -replace 'Python ', '')

# 1 · download integrity
$h = (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLower()
Step download_digest ($(if ($h -eq $ExpectedSha256.ToLower()) { 'PASS' } else { 'FAIL' }))

# 2 · install
& powershell -ExecutionPolicy Bypass -File $Installer *> $null
$dest = if ($env:PRECEPTOROS_DESTINO) { $env:PRECEPTOROS_DESTINO } else { "$HOME\preceptoros" }
Step install ($(if (Test-Path "$dest\bin\preceptoros-pwa") { 'PASS' } else { 'FAIL' }))
Step installed_head ((git -C $dest rev-parse --short=12 HEAD) 2>$null)
Step shortcut 'NO_DATA:install.ps1_creates_no_shortcut'

# 3 · start, shell, conversation
$env:PRECEPTOROS_PWA_PUERTO = "$Port"
$p = Start-Process python -ArgumentList "-B", "$dest\bin\preceptoros-pwa" -WorkingDirectory $dest -PassThru -WindowStyle Hidden
Step starts ($(if (Up) { 'PASS' } else { 'FAIL' }))
try { $s = (Invoke-WebRequest "$U/app.html" -UseBasicParsing).Content; Step app_shell ($(if ($s -match 'PreceptorOS') { 'PASS' } else { 'FAIL' })) } catch { Step app_shell 'FAIL' }
$hdr = @{ Origin = $U }
try {
  $r = Invoke-RestMethod "$U/api/hexelion/chat" -Method Post -Headers $hdr -ContentType 'application/json' -Body '{"texto":"windows acceptance hello"}'
  Step hexelion_door ("" + $r.state + $r.estado)
} catch { Step hexelion_door ('NO_DATA:' + $_.Exception.Response.StatusCode.value__) }
try {
  $r = Invoke-RestMethod "$U/api/conversacion" -Method Post -Headers $hdr -ContentType 'application/json' -Body '{"para":"claude","texto":"windows acceptance hello"}'
  Step deliver_to_thread ("" + $r.state)
  $t = Invoke-RestMethod "$U/api/conversacion?desde=0"
  Step thread_reads_back ($(if (($t | ConvertTo-Json -Depth 6) -match 'windows acceptance hello') { 'PASS' } else { 'FAIL' }))
} catch { Step deliver_to_thread 'FAIL' }
try { $c = Invoke-RestMethod "$U/api/cerebro"; Step model_discovery ('READ:' + $c.estado) } catch { Step model_discovery 'NO_DATA:unreadable' }
Stop-Process -Id $p.Id -ErrorAction SilentlyContinue

# 4 · update keeps data (re-running the installer is the update: git pull --ff-only)
$before = DataHash
& powershell -ExecutionPolicy Bypass -File $Installer *> $null
Step update_runs 'PASS'
Step update_keeps_data ($(if ((DataHash) -eq $before) { "PASS:$before" } else { 'FAIL' }))
Step update_moved 'NO_DATA:only_a_newer_upstream_commit_can_show_a_fast_forward'

# 5 · uninstall keeps data
$keep = DataHash
& powershell -ExecutionPolicy Bypass -File "$dest\empaquetado\uninstall.ps1" -Si *> $null
Step uninstall_removes_tree ($(if (-not (Test-Path $dest)) { 'PASS' } else { 'FAIL' }))
Step uninstall_keeps_data ($(if ((DataHash) -eq $keep) { 'PASS' } else { 'FAIL' }))
$R.result = $(if (($R.Values | Where-Object { $_ -eq 'FAIL' }).Count -eq 0) { 'PASS' } else { 'FAIL' })
$R | ConvertTo-Json -Compress
