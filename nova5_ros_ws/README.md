# Simulatore DOBOT Nova5

Questo workspace esegue il modello virtuale del DOBOT Nova5 in ROS 2 Jazzy,
MoveIt 2 e RViz. Non si collega a un robot fisico: i comandi vengono eseguiti
dal controllore `FakeSystem` di ROS 2.

## Avvio da Windows

Aprire PowerShell nella cartella principale del progetto ed eseguire:

```powershell
.\scripts\start-nova5-simulation.ps1
```

Al primo avvio RViz può richiedere qualche secondo. Nella scheda
**MotionPlanning**:

1. selezionare il gruppo `nova5_group`;
2. trascinare il marcatore interattivo sull'estremità del braccio;
3. premere **Plan** e poi **Execute**.

Il movimento resta interamente simulato. Chiudere RViz o premere `Ctrl+C` nel
terminale PowerShell per arrestarlo.

## Struttura

- `src/DOBOT_6Axis_ROS2_V3/`: repository ROS 2 ufficiale DOBOT, incluso come
  riferimento per il modello e la configurazione Nova5.
- `install/`, `build/`, `log/`: output generati da `colcon`; non sono codice
  sorgente.

## Nota sulla compatibilita'

La parte Nova5/MoveIt del repository DOBOT e' stata compilata con ROS 2 Jazzy.
Il suo vecchio avvio Gazebo Classic non viene usato: una scena con Gazebo
Harmonic, oggetti e pinza virtuale verra' aggiunta come pacchetto dedicato,
compatibile con Ubuntu 24.04.

RViz mostra soltanto il modello collegato ai TF del simulatore. Le preview e
le animazioni di traiettoria MoveIt sono nascoste per evitare robot duplicati.

Le istruzioni per ricreare l'ambiente e verificare il gateway sono in
[../docs/SETUP.md](../docs/SETUP.md).
