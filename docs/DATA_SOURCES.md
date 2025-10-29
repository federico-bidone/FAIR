# FAIR-III Data Source Catalog

La tabella seguente mappa le principali fonti dati integrate in FAIR-III
v0.2. Ogni riga riporta frequenza, URL di riferimento, vincoli di licenza e
note operative (lag PIT, conversioni FX, passaggi manuali).

| source | series/symbol | freq | earliest_date | url | license | rate_limit | requires_key | timezone | pit_rule | eom_pinning | eur_fx | manual_steps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ecb | `EXR.D.USD.EUR.SP00.A` | Daily | 1999-01-04 | https://data-api.ecb.europa.eu/service/data/EXR | CC BY 4.0 | ≈20 req/min | No | Europe/Rome | T+0 16:00 CET | No | Base | Nessuno |
| fred | `DGS10`, `T10YIE`, `CPIAUCSL` | Daily/Monthly | 1962-01-02 | https://api.stlouisfed.org/fred/series/observations | Data.gov | 120 req/min | Sì (`FRED_API_KEY`) | America/New_York | T+1 | Sì (CPI) | Sì (FX BCE) | Nessuno |
| stooq | `spy.us`, `agg.us` | Daily | 2000-01-03 | https://stooq.com | CC BY 4.0 | N/A (static CSV) | No | Exchange local | T+0 close | No | Sì (FX BCE) | Nessuno |
| cboe | `vix_historical.csv` | Daily | 1990-01-02 | https://www.cboe.com/us/equity_indices/file_info/ | Proprietary (terms of use) | Manual download | No | America/Chicago | T+1 09:15 CT | No | Sì | Nessuno |
| portfoliocharts | Simba `Data_Series` | Monthly | 1900-01-31 | https://portfoliocharts.com | Educational use | Manual (Excel) | No | UTC | T+1 month-end | Sì | Sì | Copiare `Simba` in `data/portfoliocharts_manual/` |
| curvo | MSCI/FTSE/STOXX CSV | Daily/Monthly | 2003-01-02 | https://curvo.eu | Proprietary | Manual download | No | Europe/Brussels | T+2 | Sì | Sì | Copia manuale in `data/curvo/` |
| coingecko | `bitcoin`, `ethereum` | Daily | 2013-04-29 | https://api.coingecko.com/api/v3/ | CC BY 4.0 | 50 req/min | No | UTC | T+0 16:00 CET | No | No | Nessuno |

Legenda colonne:

- **rate_limit**: throughput massimo osservato; applicare backoff esponenziale.
- **pit_rule**: lag necessario per garantire point-in-time (es. `T+1`).
- **eom_pinning**: se `Sì`, i valori mensili vengono agganciati all'ultimo
  giorno del mese (`MonthEnd`).
- **eur_fx**: se `Sì`, è richiesta la conversione in EUR tramite FX BCE 16:00
  CET durante l'ETL.
- **manual_steps**: azioni operative richieste dall'utente prima
  dell'ingest (`data/<source>_manual/`).
