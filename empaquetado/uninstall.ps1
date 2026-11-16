# PreceptorOS · desinstalador para Windows.
#
# ESTADO DE PRUEBAS: NO PROBADO. Solo se ha comprobado que PowerShell lo analiza sin errores (pwsh en Linux).
# Nadie lo ha ejecutado en Windows. Procedimiento de aceptación: empaquetado/windows/ACCEPTANCE.md
#
# QUITA solo el árbol clonado por install.ps1 ($env:PRECEPTOROS_DESTINO, por defecto $HOME\preceptoros), y solo si
# es un clon de PreceptorOS sin cambios propios. install.ps1 no crea accesos directos, así que no hay ninguno que quitar.
# NO QUITA tus datos: $HOME\.preceptoros se conserva. Para borrarlos: -BorrarDatos y escribir la frase que se pide.
# No pide administrador.
param([switch]$BorrarDatos, [switch]$Si)
$ErrorActionPreference = 'Stop'
$Destino = if ($env:PRECEPTOROS_DESTINO) { $env:PRECEPTOROS_DESTINO } else { "$HOME\preceptoros" }
$Datos = "$HOME\.preceptoros"
function OK($m) { Write-Host "  ok  $m" }
function ND($m) { Write-Host "  --  $m" }
function NO($m) { Write-Host "  NO  $m" -ForegroundColor Yellow }

Write-Host "PreceptorOS · desinstalar"
Write-Host "  arbol: $Destino"
Write-Host "  datos: $Datos (se conservan)"
if (-not $Si) {
  $r = Read-Host '¿Quitar la aplicacion? [s/N]'
  if ($r -notmatch '^(s|si|sí|y)$') { Write-Host 'nada cambiado'; exit 0 }
}

# 1 · el servidor que corre desde este arbol
$full = (Resolve-Path -LiteralPath $Destino -ErrorAction SilentlyContinue)
if ($full) {
  Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*preceptoros-pwa*' -and $_.CommandLine -like "*$($full.Path)*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; OK "servidor parado (pid $($_.ProcessId))" }
}

# 2 · el arbol: solo un clon limpio
if (Test-Path -LiteralPath "$Destino\.git") {
  $sucio = git -C $Destino status --porcelain 2>$null | Select-Object -First 1
  $propios = git -C $Destino log --oneline '@{u}..' 2>$null | Select-Object -First 1
  if (-not (Test-Path -LiteralPath "$Destino\bin\preceptoros-pwa")) { NO "$Destino no parece PreceptorOS: no lo toco" }
  elseif ($sucio -or $propios) { NO "$Destino tiene cambios tuyos: no lo borro" }
  else { Remove-Item -LiteralPath $Destino -Recurse -Force; OK "arbol quitado" }
} elseif (Test-Path -LiteralPath $Destino) { NO "$Destino existe pero no es un clon: no lo toco" }
else { ND "no habia arbol en $Destino" }

# 3 · los datos
if ($BorrarDatos -and (Test-Path -LiteralPath $Datos)) {
  Write-Host "Vas a borrar ${Datos}: memoria, conversaciones, identidad y ajustes. No se puede deshacer."
  $f = Read-Host 'Escribe exactamente  borrar mis datos  para seguir'
  if ($f -ceq 'borrar mis datos') { Remove-Item -LiteralPath $Datos -Recurse -Force; OK 'datos borrados' }
  else { OK 'frase distinta: datos conservados' }
} elseif (Test-Path -LiteralPath $Datos) { OK "datos conservados en $Datos" } else { ND "no habia datos en $Datos" }
Write-Host 'listo.'
