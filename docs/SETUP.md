# Setup e verifica locale

## Prerequisiti

- Windows con WSL 2 e distribuzione `Ubuntu-24.04`;
- ROS 2 Jazzy con MoveIt 2 e `colcon` installati in WSL;
- il workspace su un disco Windows montato in WSL (per esempio
  `C:\dev\NOVA5_tools`, corrispondente a `/mnt/c/dev/NOVA5_tools`).

## Primo setup

Dopo un clone del repository, inizializzare prima il sorgente DOBOT:

```powershell
git submodule update --init --recursive
```

In WSL (adattare il percorso se il progetto non e' in `C:\dev\NOVA5_tools`):

```bash
source /opt/ros/jazzy/setup.bash
cd /mnt/c/dev/NOVA5_tools/nova5_ros_ws
rosdep install --from-paths src --ignore-src --rosdistro jazzy -r -y
colcon build --packages-select dobot_rviz nova5_moveit

cd /mnt/c/dev/NOVA5_tools/nova5_gateway
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

`--system-site-packages` e' necessario: il gateway usa `rclpy` e i messaggi
ROS forniti dall'installazione Jazzy di sistema.

## Verifiche

Da PowerShell nella radice del progetto:

```powershell
.\scripts\test-nova5-gateway.ps1
.\scripts\smoke-nova5-gateway.ps1
.\scripts\start-nova5-control.ps1
```

Il primo comando verifica il protocollo WebSocket, il secondo il ciclo di vita
del gateway senza il simulatore grafico. L'ultimo e' il test di accettazione
manuale completo: verificare ARM, jog articolare, jog TCP, pose guidate, STOP
e interlock B2.

Per terminare una sessione completa usare:

```powershell
.\scripts\stop-nova5-control.ps1
```
