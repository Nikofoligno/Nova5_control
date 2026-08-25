[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu-24.04'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$linuxRoot = '/mnt/' + $projectRoot.Substring(0, 1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\', '/')
$linuxLauncher = "$linuxRoot/scripts/start-nova5-control.sh"

Write-Host 'Avvio simulatore ROS, gateway WebSocket e interfaccia tablet.'
Write-Host 'Apri http://localhost:8001 nel browser. Ctrl+C arresta e pulisce tutti i processi Nova5.'

# The Bash launcher owns the background ROS process. Passing a script path,
# rather than an interpolated shell command, preserves the real value of $!.
& wsl.exe -d $distribution -- bash $linuxLauncher
