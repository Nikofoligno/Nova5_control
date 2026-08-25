# Checklist per integrazione hardware reale

Questa checklist e' intenzionalmente separata dalla simulazione. Il software
attuale non deve essere collegato a un DOBOT o a un Unitree B2 finche' tutti i
punti seguenti non sono approvati dal responsabile di sicurezza.

## Interfacce da fornire

- Driver ufficiale e documentato per DOBOT/CCBOX, con una modalita' di comando
  che esponga stato del controller, fault e arresto sicuro.
- Telemetria B2 autenticata e a bassa latenza per stato fermo/stabile, fault,
  e-stop e presenza del consenso di movimento.
- Driver della pinza con feedback di apertura, forza/corrente, oggetto rilevato
  e fault; lo stato booleano simulato non e' sufficiente.
- Rete isolata, autenticazione dell'operatore, TLS e audit log dei comandi.

## Sicurezza da validare sul posto

- E-stop fisico indipendente dal gateway e dead-man hardware cablato.
- Limiti articolari, TCP, carico, velocita', accelerazione e zone vietate
  definiti dal costruttore e validati dopo il montaggio sul B2.
- Pose `ready`, `pick`, `carry` e `place` calibrate con pinza, massa reale,
  centro di gravita' e volume di ingombro del B2.
- Collision checking con il modello del B2, dell'end-effector, del carico e
  dell'area di lavoro reale.
- Test di fault: perdita rete, telemetria scaduta, controller non pronto,
  instabilita' B2, e-stop e ripresa dopo arresto.

## Criterio di passaggio

Un responsabile abilitato deve firmare una procedura di collaudo in ambiente
protetto. Solo dopo tale approvazione si puo' sostituire `SimulationArmDriver`
con un driver reale, mantenendo ARM e interlock come condizioni obbligatorie.
