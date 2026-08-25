# NOVA5 Tools

Ambiente di simulazione del manipolatore DOBOT Nova5, gateway ROS 2/WebSocket e
interfaccia tablet per il controllo simulato.

## Avvio rapido

Da PowerShell:

```powershell
.\scripts\test-nova5-gateway.ps1
.\scripts\smoke-nova5-gateway.ps1
.\scripts\start-nova5-control.ps1
```

Aprire `http://localhost:8001` dopo l'avvio completo. Per arrestare:

```powershell
.\scripts\stop-nova5-control.ps1
```

Il repository DOBOT ufficiale e' incluso come submodule. Dopo un clone eseguire:

```powershell
git submodule update --init --recursive
```

Per prerequisiti, setup e test consultare [docs/SETUP.md](docs/SETUP.md).
L'integrazione con robot fisico resta espressamente separata e richiede tutti i
controlli in [docs/REAL-HARDWARE-CHECKLIST.md](docs/REAL-HARDWARE-CHECKLIST.md).
