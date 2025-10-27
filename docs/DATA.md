# Data Management

## Fonti pubbliche supportate
| Codice | Fonte | Endpoint principale | Licenza sintetica |
| ------ | ----- | ------------------ | ----------------- |
| `ecb`  | European Central Bank (ECB Data Portal) | `https://data-api.ecb.europa.eu/service/data/EXR` | Uso conforme ai [Terms of Use ECB SDW](https://www.ecb.europa.eu/stats/ecb_statistics/governance/shared_data/en.html) |
| `fred` | Federal Reserve Economic Data | `https://api.stlouisfed.org/fred/series/observations` | [FRED Terms of Use](https://fredhelp.stlouisfed.org/fred/terms-of-use/) |
| `boe`  | Bank of England Data Services | `https://www.bankofengland.co.uk/boeapps/database/_iadb-getTDDownloadCSV` | [BoE Data Terms](https://www.bankofengland.co.uk/terms-and-conditions) |
| `stooq` | Stooq.com EOD | `https://stooq.com/q/d/l/` | [Stooq data policy](https://stooq.com/db/en/) |

Ogni fetcher registra nel log la licenza e l'URL utilizzato per ogni simbolo, fornendo evidenze per l'audit.

Dal 1º ottobre 2025 i redirect SDW sono terminati; usare data-api.ecb.europa.eu.

## Layout directory raw
```
data/
  raw/
    ecb/
    fred/
    boe/
    stooq/
```
Ogni esecuzione di `fair3 ingest` scrive un file `csv` timestampato (`<source>_YYYYMMDDTHHMMSSZ.csv`) con colonne standardizzate:
- `date`: data dell'osservazione (`YYYY-MM-DD`).
- `value`: valore numerico pulito (float).
- `symbol`: codice originale della serie/strumento.

Questi file costituiscono l'input per il successivo step ETL (`fair3 etl`) che costruirà il panel point-in-time.

## Layout directory clean & audit
```
data/
  clean/
    prices.parquet
    returns.parquet
    features.parquet
audit/
  qa_data_log.csv
```
`prices.parquet` contiene prezzi armonizzati (FX applicato) e metadati (`source`, `currency`, `currency_original`, `fx_rate`). `returns.parquet` espone rendimenti semplici/log e la versione winsorizzata per la stima, mentre `features.parquet` salva feature laggate calcolate senza look-ahead. `audit/qa_data_log.csv` registra copertura, null, outlier e currency finale per simbolo/sorgente, fungendo da acceptance evidence per la milestone ETL.


## Utilizzo CLI e filtraggio
Esempio completo:
```bash
fair3 ingest --source fred --symbols DGS10 DCOILWTICO --from 2010-01-01
```
Il parametro `--from` filtra le osservazioni successive alla data indicata dopo il download (utile quando gli endpoint non espongono filtri di query omogenei). Se non vengono specificati simboli, ogni fetcher utilizza un set di default documentato nel rispettivo modulo. Per `fred` il set copre Treasury a scadenze 1-30Y, Treasury Bill a 3 mesi, CPI, breakeven 5Y/10Y e TIPS 5Y/10Y.

## Note di licenza e redistribuzione
- I dati vengono scaricati solo localmente; non devono essere ridistribuiti nel repository.
- Alcune fonti (es. ECB, BoE) richiedono attribuzione e limitano l'uso commerciale: conservare i log prodotti in `artifacts/audit/`.
- In caso di errore HTTP o payload inatteso, il fetcher solleva eccezioni che devono essere intercettate dal livello CLI/ETL per applicare retry o fallback interni.

## Prossimi passi
- L'ETL convertirà i CSV grezzi in pannelli PIT Parquet, applicando controlli di qualità e sincronizzando i fusi orari.
- Il security master SQLite replicherà le ultime anagrafiche disponibili per strumenti UCITS/ETFs.
