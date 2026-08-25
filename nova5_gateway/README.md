# Nova5 Simulation Gateway

Gateway ROS 2 + WebSocket e interfaccia mobile web, ottimizzata per tablet.

## Avvio

Da PowerShell, nella radice del progetto:

```powershell
.\scripts\start-nova5-control.ps1
```

Poi aprire [http://localhost:8001](http://localhost:8001).

Per fermare in modo affidabile il gateway, MoveIt e RViz, da un secondo
terminale PowerShell eseguire:

```powershell
.\scripts\stop-nova5-control.ps1
```

Lo script avvia insieme:

1. il Nova5 virtuale in MoveIt/RViz;
2. il controller ROS 2 `FakeSystem`;
3. il gateway WebSocket su porta `8001`;
4. l'interfaccia touch, installabile come web app dal browser.

## Controlli disponibili

- Consenso `ARM`: nessun movimento viene accettato finche' il braccio non e'
  abilitato esplicitamente.
- Interlock B2: se la piattaforma non e' stabile, il gateway annulla il comando
  in corso e disabilita ARM. Nel simulatore si puo' provare dalla scheda
  **Stato**; in produzione il valore arrivera' dalla telemetria Unitree.
- Jog articolare e TCP: scegliere **Click singolo** per un incremento oppure
  **Tieni premuto** per una sequenza di incrementi. Al rilascio il gateway
  annulla il moto in corso senza disabilitare ARM.
- Jog TCP: incremento `X/Y/Z/Rx/Ry/Rz` nel riferimento `base_link`, con
  passi da 1, 5, 10 o 25 mm (5 mm predefinito). MoveIt pianifica e controlla
  il percorso completo; il gateway blocca salti articolari e singolarita'.
- Pose guidate: `Home`, `Sicura`, `Ready`, `Pick`, `Carry`, `Place` per il flusso
  presa → trasporto → deposito.

## Sicurezza e limiti

- Il gateway e' limitato alla simulazione e non comunica con CCBOX/DOBOT.
- I tasti articolari inviano variazioni piccole e rispettano i limiti del modello URDF.
- Jog TCP, pose e jog articolari vengono pianificati da MoveIt con collision
  checking del percorso. La scena contiene pero' solo il modello del braccio:
  B2, pinza, carico e ostacoli reali dovranno essere aggiunti e validati.
- STOP annulla l'ultima traiettoria virtuale; non sostituisce un arresto di emergenza fisico.
- La pinza e' per ora uno stato simulato. La relativa cinematica e' esclusa finche' non sara'
  scelto l'end-effector.
- La posa **Sicura** coincide con `Carry` ed e' valida solo nel simulatore;
  dovra' essere certificata dopo il montaggio sul B2.

Prima di collegare un robot reale, il controllo TCP discreto dovra' essere
evoluto in MoveIt Servo con dead-man switch hardware e pianificazione completa
della traiettoria.

## Verifica e primo setup

Le istruzioni ripetibili di installazione, test del protocollo e smoke test
sono in [../docs/SETUP.md](../docs/SETUP.md). La checklist obbligatoria prima
di qualunque integrazione fisica e' in
[../docs/REAL-HARDWARE-CHECKLIST.md](../docs/REAL-HARDWARE-CHECKLIST.md).
