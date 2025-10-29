# Moduli motore

> Strumento informativo/didattico; non costituisce consulenza finanziaria o raccomandazione.

`fair3.engine` ospita la logica del dominio per l'acquisizione, la trasformazione, la costruzione dei fattori
la stima, l'allocazione, la mappatura, il rilevamento del regime, l'esecuzione,
reporting, il QA, la robustezza e le utilità condivise. Ogni sottomodulo espone funzioni digitate
progettate sia per l'orchestrazione CLI che per la sperimentazione del notebook, pur
mantenendo la disciplina point-in-time e il seeding deterministico.

## Mappa dei sottomoduli
- `ingest/`: fetcher specifici dell'origine derivati da `BaseCSVFetcher`, SQLite/Parquet
  helper di persistenza e cablaggio del registro.
- `etl/`: pulizia PIT, applicazione dello schema Parquet e upsert SQLite.
- `factors/`: generatori di fattori, cablaggi di convalida e metadatigovernance.
- `estimates/`: motori media/varianza, proiezioni PSD/SPD e log di blend.
- `allocators/`: generatori di portafoglio (Max-Sharpe, HRP, DRO, CVaR-ERC) con
  orchestrazione del meta-mix.
- `mapping/`: stima rolling beta, limiti di liquidità eprotezioni contro gli errori di tracciamento.
- `regime/`: stima della probabilità di crisi basata su comitato con isteresi.
- `execution/`: dimensionamento dei lotti, costi di Almgren–Chriss ed euristica fiscale italiana.
- `reporting/`: dashboard mensili, grafici a ventaglio, gate di accettazione e output PDF.
- `goals/`: motore di obiettivi Monte Carlo sensibile al regime conLogica del glidepath.
- `qa/`: sintesi deterministica del set di dati QA e diagnostica di accettazione.
- `robustness/`: laboratorio bootstrap/replay e driver di ablazione.
- `utils/`: helper condivisi (logging, seed, IO, gestione del fuso orario).

## Linee guida per i contributi
- Aggiungi stringhe di documentazione a moduli, classi e funzioni con sezioni `Args`,
  `Returns` e `Raises` esplicite anche quando il comportamento predefinito è semplice.
- Evita lo stato nascosto; passa percorsi, configurazioni e seed espliciti agli helper in modo che i comandi 
  CLI rimangano idempotenti.
- Cattura metadati di licenza, checksum e contesto di fuso orario/valuta in tutti gli output
  ingest ed ETL.
