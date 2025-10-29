# Guida alla risoluzione dei problemi

Questa guida catalogherà i problemi operativi comuni (installazione, SSL, caratteri, accesso ai dati) e le relative soluzioni. Le voci verranno aggiunte man mano che convalidiamo la pipeline tra gli ambienti.

## Livello di reporting
- **Errori backend Matplotlib su Windows CI**: assicurati che la dipendenza opzionale
  `matplotlib` sia installata e che l'ambiente rispetti il ​​backend Agg. Il modulo di reporting
   applica `matplotlib.use("Agg", force=True)` ma DLL mancanti
  possono comunque verificarsi quando i pacchetti di sistema sono assenti. Installa Visual C++
  ridistribuibile o `pip install --upgrade matplotlib`.
- **Artefatti vuoti in `artifacts/reports/`**: verifica che la pipeline ETL sia stata eseguita
  per il periodo richiesto. La CLI viene fornita con un fallback sintetico deterministico;
  una volta collegati gli artefatti PIT reali, i file parquet mancanti attiveranno questo
  sintomo.
- **Grandi dimensioni PNG**: le stampe vengono eseguite per impostazione predefinita su 8x4, 5 pollici a 150 dpi. Riduci le dimensioni
  richiamando `generate_monthly_report(..., output_dir=...)` e post-elaborando
  le immagini o abbassando il DPI prima di salvare.

## Robustness Lab
- **`summary.json` mancante o vuoto** – assicurati che `run_robustness_lab` abbia ricevuto una serie di restituzione non vuota
  .Il campionatore bootstrap viene generato quando l'iterabile è vuoto; feed
  restituzioni del portafoglio dalla fase di reporting o un segnaposto sintetico.
- **La generazione del PDF non riesce** – conferma che `matplotlib` sia installato e che il processo
  disponga delle autorizzazioni di scrittura su `artifacts/robustness/`.Il laboratorio forza il backend Agg
   ma richiede comunque il pacchetto `matplotlib`.
- **Errori del runner di ablazione**: il callback deve accettare una mappatura dei flag di governance
  e restituire una mappatura dei nomi delle metriche ai float. Facoltativamente accettare a
  Parola chiave `seed` o `rng` per il campionamento deterministico.

## Goals Engine
- **Errore "Nessun obiettivo configurato"** – assicurati che `configs/goals.yml` contenga almeno
  una voce obiettivo con chiavi `name`, `W`, `T_years`, `p_min`.La CLI si attiva se l'elenco
   è vuoto o mal formato.
- **Probabilità fuori range** – verificare che i contributi mensili e gli orizzonti siano
  realistici. Contributi estremamente bassi rispetto agli obiettivi naturalmente
   produrranno probabilità di successo vicine allo 0, 0; regolare `--monthly-contribution` o il
  file `configs/params.yml` per scenari plausibili.
- **PDF non generato** – controllare i permessi di scrittura nella directory
  di output (`--output-dir`).Il motore usa Matplotlib/Agg; installare la
  dipendenza se assente (`pip install matplotlib`).
