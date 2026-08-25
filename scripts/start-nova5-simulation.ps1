[CmdletBinding()]
param(
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'

$distribution = 'Ubuntu-24.04'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$linuxRoot = '/mnt/' + $projectRoot.Substring(0, 1).ToLowerInvariant() + $projectRoot.Substring(2).Replace('\', '/')
$linuxWorkspace = "$linuxRoot/nova5_ros_ws"
$setupCommand = "source /opt/ros/jazzy/setup.bash && source $linuxWorkspace/install/setup.bash"

if ($Rebuild) {
    Write-Host 'Compilazione dei pacchetti Nova5...'
    & wsl.exe -d $distribution -- bash -lc "$setupCommand && cd $linuxWorkspace && colcon build --symlink-install --packages-select dobot_rviz nova5_moveit"
    if ($LASTEXITCODE -ne 0) {
        throw 'Compilazione del workspace Nova5 non riuscita.'
    }
}

Write-Host 'Avvio del simulatore Nova5 (MoveIt + RViz). Usa Ctrl+C per arrestarlo.'
& wsl.exe -d $distribution -- bash -lc "$setupCommand && ros2 launch nova5_moveit demo.launch.py"
