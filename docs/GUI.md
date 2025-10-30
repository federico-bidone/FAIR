# FAIR-III GUI (PySide6)

"""Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione."""

La GUI opzionale PySide6 fornisce un sottile livello di orchestrazione sui comandi esistenti
CLI.È destinato ai flussi di lavoro desktop esplorativi in ​​cui un pannello di controllo visivo
 è preferibile alle invocazioni della shell.

## Installazione

Installa PySide6 insieme agli extra di FAIR-III:

```bash
pip install PySide6
```

Non sono necessarie altre dipendenze; la GUI si basa interamente sui motori
già incluso in FAIR-III.

## Avvio della GUI

Utilizzare il wrapper CLI per avviare l'interfaccia:

```bash
fair3 gui --raw-root data/raw --clean-root data/clean --artifacts-root artifacts
```

Il comando accetta lo stesso percorso sovrascrive la CLI per inizializzare l'interfaccia.
Passaggio `--dry-run` stampa la configurazione derivata senza avviare la GUI,
utile quando si convalida la configurazione all'interno di headlessambienti.

## Funzioni

- **Scheda Ingest:** seleziona qualsiasi sorgente registrata, fornisci simboli opzionali e un
  data di inizio e attivare l'importazione. Le righe di stato rispecchiano l'output CLI e
  si aggiungono al pannello di registro.
- **Scheda Pipeline:** i pulsanti inviano ETL, fattore, stima, mappatura, regime,
  e motori obiettivo utilizzando le directory e le soglie configurate.
- **Scheda Rapporti:** fornisce un percorso PDF da aprire con il visualizzatore predefinito della piattaforma.

Tutte le azioni rilevano le eccezioni e le registrano nel registro su schermo in modol'applicazione
 rimane reattiva anche se una fase della pipeline fallisce. Quando PySide6
non è installato, la GUI salta silenziosamente l'esecuzione dopo aver registrato un suggerimento.

## Layout dell'interfaccia

La finestra della GUI è suddivisa in tre schede:**Ingest**, **Pipeline** e
**Rapporti**—impilate nella parte superiore del frame. Un pannello di registro persistente si trova in
in basso e rispecchia gli aggiornamenti di stato della CLI in ordine cronologico. Ogni scheda
espone attivazioni/disattivazioni di prova e selettori di percorso in modo che la GUI rispecchi la semantica della CLI
senza fare affidamento su uno screenshot incorporato.

## Risoluzione dei problemi

- **PySide6 mancante:** installa il pacchetto o fai affidamento sulla CLI (`launch_gui`
  restituisce immediatamente e registra un messaggio informativo).
- **Attività di lunga durata:** le esecuzioni della pipeline si verificano nel thread della GUI e potrebbero
  bloccare la finestra. Per le esecuzioni di produzione, preferisci la CLI o le azioni wrap con
  pianificazione in background.

Ricorda che la GUI eredita tutti i vincoli di conformità UCITS/UE/IT documentati
nel README e non modifica il comportamento deterministico delle pipeline.
