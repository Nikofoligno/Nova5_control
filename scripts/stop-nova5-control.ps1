[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$linuxRoot = '/mnt/' + $projectRoot.Substring(0, 1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\', '/')
& wsl.exe -d 'Ubuntu-24.04' -- bash "$linuxRoot/scripts/stop-nova5-control.sh"
