# Data Management

## Fonti pubbliche supportate
| Codice | Fonte | Endpoint principale | Licenza sintetica |
| ------ | ----- | ------------------ | ----------------- |
| `ecb`  | European Central Bank (ECB Data Portal) | `https://data-api.ecb.europa.eu/service/data/EXR` | Uso conforme ai [Terms of Use ECB SDW](https://www.ecb.europa.eu/stats/ecb_statistics/governance/shared_data/en.html) |
| `fred` | Federal Reserve Economic Data | `https://api.stlouisfed.org/fred/series/observations` | [FRED Terms of Use](https://fredhelp.stlouisfed.org/fred/terms-of-use/) |
| `oecd` | Organisation for Economic Co-operation and Development | `https://stats.oecd.org/sdmx-json/data` | [OECD Terms & Conditions](https://www.oecd.org/termsandconditions/) |
| `boe`  | Bank of England Data Services | `https://www.bankofengland.co.uk/boeapps/database/_iadb-getTDDownloadCSV` | [BoE Data Terms](https://www.bankofengland.co.uk/terms-and-conditions) |
| `bis`  | Bank for International Settlements (REER/NEER) | `https://stats.bis.org/api/v1/data/REER` | [BIS terms of use](https://www.bis.org/terms.htm) |
| `cboe` | Cboe VIX & SKEW indices | `https://cdn.cboe.com/api/global/us_indices/daily_prices` | Cboe Exchange, Inc. data subject to terms |
| `lbma` | London Bullion Market Association (PM fix) | `https://www.lbma.org.uk/prices-and-data/precious-metal-prices` (HTML) | LBMA data — informational use only |
| `nareit` | FTSE Nareit REIT indices (manual Excel) | `data/nareit_manual/NAREIT_AllSeries.xlsx` | FTSE Nareit — informational use only |
| `portviz` | Portfolio Visualizer synthetic asset references | `data/portfolio_visualizer_manual/<dataset>.csv` | Portfolio Visualizer — educational/informational use |
| `stooq` | Stooq.com EOD | `https://stooq.com/q/d/l/` (cache in-process, supporto `.us/.pl`) | [Stooq data policy](https://stooq.com/db/en/) |
| `yahoo` | Yahoo Finance fallback (`yfinance`) | `yfinance://<symbol>` (finestra 5 anni, ritardo 2s) | [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) — uso personale/non commerciale |
| `alphavantage_fx` | Alpha Vantage FX daily | `https://www.alphavantage.co/query?function=FX_DAILY` (richiede `ALPHAVANTAGE_API_KEY`, throttle 5/min) | [Alpha Vantage Terms](https://www.alphavantage.co/terms_of_service/) |
| `tiingo` | Tiingo equities/ETF daily | `https://api.tiingo.com/tiingo/daily/<symbol>/prices` (richiede `TIINGO_API_KEY`, throttle 1s) | [Tiingo Terms of Use](https://www.tiingo.com/documentation/general/terms-of-use) |
| `coingecko` | CoinGecko crypto daily (EUR) | `https://api.coingecko.com/api/v3/coins/<id>/market_chart/range` (campionamento 15:00 UTC, throttle 1s) | [CoinGecko Terms of Use](https://www.coingecko.com/en/terms) |
| `binance` | Binance Data Portal klines | `https://data.binance.vision/data/spot/daily/klines/<symbol>/<interval>/<file>.zip` (intervallo 1d/1h, nessuna API key) | Binance Data Portal — redistribuzione bulk vietata |
| `french` | Kenneth R. French Data Library | `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/` | Uso accademico/educational (consultare i termini sul sito) |
| `aqr` | AQR Data Sets (Quality, Value, Betting-Against-Beta) | File manuali `data/aqr_manual/*.csv` | AQR Data Sets — solo uso informativo/educational |
| `alpha` | Alpha Architect / q-Factors / Novy-Marx | CSV pubblici (`alphaarchitect.com`, `global-q.org`) + HTML manuale `data/alpha_manual/` | Educational use only (consultare termini specifici) |
| `worldbank` | World Bank Open Data | `https://api.worldbank.org/v2/country/<ISO3>/indicator/<series>` | [World Bank Terms of Use](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets) |

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
