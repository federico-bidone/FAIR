# FAIR-III Data Source Catalog

La tabella seguente mappa le principali fonti dati integrate in FAIR-III
v0.2. Ogni riga riporta frequenza, URL di riferimento, vincoli di licenza e
note operative (lag PIT, conversioni FX, passaggi manuali).

| fonte | serie/simbolo | frequenza | prima_data | URL | licenza | limite_velocità | richiede_chiave | fuso orario | pit_rule | eom_pinning | euro_fx | passi_manuali |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bce | `EXR.D.USD.EUR.SP00. A` | Giornaliero | 04-01-1999 | https://data-api.ecb.europa.eu/service/data/EXR | CC BY 4.0 | ≈20 richieste/min | No | Europa/Roma | T+0 16:00 | No | Fondo | Nessuno |
| Fred | `DGS10`, `T10YIE`, `CPIAUCSL` | Giornaliero/mensile | 02-01-1962 | https://api.stlouisfed.org/fred/series/observations | Data.gov | 120 richieste/min | Sì (`FRED_API_KEY`) | America/New_York | T+1 | Sì (CPI) | Sì (FX BCE) | Nessuno |
| stooq | `spy.us`, `agg.us` | Giornaliero | 2000-01-03 | https://stooq.com | CC BY 4.0 | N/D (CSV statico) | No | Scambio locale | T+0 chiudi | No | Sì (FX BCE) | Nessuno |
| cboe | `vix_historical.csv` | Giornaliero | 02-01-1990 | https://www.cboe.com/us/equity_indices/file_info/ | Proprietario (termini di utilizzo) | Scarica il manuale | No | America/Chicago | T+1 09:15 CT | No | Sì | Nessuno |
| grafici di portafoglio | Simba`Data_Series` | Mensile | 31-01-1900 | https://portfoliocharts.com | Uso didattico | Manuale (Excel) | No | UTC | T+1 fine mese | Sì | Sì | Copiare `Simba` in `data/portfoliocharts_manual/` |
| curvo | MSCI/FTSE/STOXX CSV | Giornaliero/mensile | 2003-01-02 | https://curvo.eu | Proprietario | Scarica il manuale | No | Europa/Bruxelles | T+2 | Sì | Sì | Copia manuale in `data/curvo/` |
| coingecco | `bitcoin`, `ethereum` | Giornaliero | 29-04-2013 | https://api.coingecko.com/api/v3/ | CC BY 4.0 | 50 richieste/min | No | UTC | T+0 16:00 | No | No | Nessuno |

Legenda colonne:

- **rate_limit**: throughput massimo osservato; applicare backoff esponenziale.
- **pit_rule**: lag necessario per garantire point-in-time (es. `T+1`).
- **eom_pinning**: se `Sì`, i valori mensili vengono agganciati all'ultimo
  giorno del mese (`MonthEnd`).
- **eur_fx**: se `Sì`, è richiesta la conversione in EUR tramite FX BCE 16:00
  CET durante l'ETL.
- **manual_steps**: azioni operative richieste dall'utente prima
  dell'ingest (`data/<source>_manual/`).
