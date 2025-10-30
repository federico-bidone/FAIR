# Gestione dati

## Fonti pubbliche supportate
| Codice | Fonte | Endpoint principale | Licenza sintetica |
| ------ | ----- | ------------------ | ----------------- |
| `ecb` | Banca centrale europea (portale dati della BCE) | `https://data-api.ecb.europa.eu/service/data/EXR` | Uso conforme ai [Termini di utilizzo dell'SDW della BCE](https://www.ecb.europa.eu/stats/ecb_statistics/governance/shared_data/en.html) |
| `fred` | Dati economici della Federal Reserve | `https://api.stlouisfed.org/fred/series/observations` | [Condizioni d'uso FRED](https://fredhelp.stlouisfed.org/fred/terms-of-use/) |
| `oecd` | Organizzazione per la cooperazione e lo sviluppo economico | `https://stats.oecd.org/sdmx-json/data` | [Termini e condizioni dell'OCSE](https://www.oecd.org/termsandconditions/) |
| `boe` | Servizi dati della Banca d'Inghilterra | `https://www.bankofengland.co.uk/boeapps/database/_iadb-getTDDownloadCSV` | [Termini sui dati BoE](https://www.bankofengland.co.uk/terms-and-conditions) |
| `bis` | Banca dei regolamenti internazionali (REER/NEER) | `https://stats.bis.org/api/v1/data/REER` | [Condizioni d'uso della BRI](https://www.bis.org/terms.htm) |
| `cboe` | Indici Cboe VIX e SKEW | `https://cdn.cboe.com/api/global/us_indices/daily_prices` | I dati di Cboe Exchange, Inc. sono soggetti ai termini |
| `lbma` | London Bullion Market Association (correzione PM) | `https://www.lbma.org.uk/prices-and-data/precious-metal-prices` (HTML) | Dati LBMA: solo uso informativo |
| `nareit` | Indici FTSE Nareit REIT (manuale Excel) | `data/nareit_manual/NAREIT_AllSeries.xlsx` | FTSE Nareit — solo per uso informativo |
| `portviz` | Riferimenti asset sintetici Portfolio Visualizer | `data/portfolio_visualizer_manual/<dataset>.csv` | Visualizzatore portfolio — uso didattico/informativo |
| `portfoliocharts` | PortfolioCharts Foglio di calcolo per il backtest di Simba | `data/portfoliocharts/PortfolioCharts_Simba.xlsx` | PortfolioCharts.com — uso didattico/informativo |
| `curvo` | Curvo.eu Backtest OICVM (CSV manuale + FX) | `data/curvo/<dataset>.csv` + `data/curvo/fx/<CCY>_EUR.csv` | Curvo.eu e fornitori dell'indice sottostante — uso informativo/educativo |
| `testfolio` | Preimpostazioni testfol.io (SPYSIM, VTISIM, GLDSIM) | `configs/testfolio_presets.yml` + `data/testfolio_manual/*.csv` | Preset sintetici testfol.io — uso informativo/educativo |
| `usmarket` | SteelCerberus dati mercato statunitense (S&P 500 storico) | `data/us_market_data/*.csv` | Dati di Bill Schwert e Robert Shiller: uso accademico/informativo |
| `eodhd` | Dati storici EOD (API o CSV manuale) | `https://eodhistoricaldata.com/api/eod/<symbol>?period=m` oppure `data/eodhd/<symbol>.csv` | Dati storici EOD: API commerciale; estratti manuali da backtes.to (solo per uso didattico) |
| `stooq` | Stooq.com EOD | `https://stooq.com/q/d/l/` (cache in-process, supporto `.us/.pl`) | [Politica sui dati di Stooq](https://stooq.com/db/en/) |
| `yahoo` | Fallback di Yahoo Finanza (`yfinance`) | `yfinance://<symbol>` (finestra 5 anni, ritardo 2s) | [Termini di servizio di Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) — uso personale/non commerciale |
| `alphavantage_fx` | Alpha Vantage FX quotidiano | `https://www.alphavantage.co/query?function=FX_DAILY` (richiesto `ALPHAVANTAGE_API_KEY`, acceleratore 5/min) | [Termini di Alpha Vantage](https://www.alphavantage.co/terms_of_service/) |
| `tiingo` | Tiingo azioni/ETF giornaliero | `https://api.tiingo.com/tiingo/daily/<symbol>/prices` (richiede `TIINGO_API_KEY`, manetta 1s) | [Termini di utilizzo di Tiingo](https://www.tiingo.com/documentation/general/terms-of-use) |
| `coingecko` | CoinGecko criptovaluta giornaliera (EUR) | `https://api.coingecko.com/api/v3/coins/<id>/market_chart/range` (campionamento 15:00 UTC, manetta 1s) | [Condizioni d'uso di CoinGecko](https://www.coingecko.com/it/terms) |
| `binance` | Linee guida del portale Binance Data | `https://data.binance.vision/data/spot/daily/klines/<symbol>/<interval>/<file>.zip` (intervallo 1d/1h, nessuna chiave API) | Binance Data Portal — ridistribuzione in blocco vietata |
| `french` | Kenneth R. Biblioteca dati francese | `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/` | Uso accademico/educational (consultare i termini sul sito) |
| `aqr` | Set di dati AQR (qualità, valore, scommesse contro beta) | File manuali `data/aqr_manual/*.csv` | Set di dati AQR — solo uso informativo/educativo |
| `alpha` | Alpha Architect / q-Factors / Novy-Marx | CSV pubblici (`alphaarchitect.com`, `global-q.org`) + HTML manuale `data/alpha_manual/` | Solo per uso didattico (consultare termini specifici) |
| `worldbank` | Dati aperti della Banca Mondiale | `https://api.worldbank.org/v2/country/<ISO3>/indicator/<series>` | [Termini di utilizzo della Banca Mondiale](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets) |

Ogni fetcher registra nel log la licenza e l'URL utilizzato per ogni simbolo, fornendo evidenze per l'audit.

Dal 1º ottobre 2025 i reindirizzamento SDW sono terminati; usare data-api.ecb.europa.eu.

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

Questi file costituiscono l'input per il successivo step ETL (`fair3 etl`) che costruirà il pannello point-in-time.

## Layout directory clean & audit
```
data/
  clean/
    asset_panel.parquet
audit/
  qa_data_log.csv
```
`asset_panel.parquet` è un pannello lungo con colonne`date` (UTC), `symbol`, `field`, `value`, `currency`, `source`, `license`, `tz`, `quality_flag`, `revision_tag`, `checksum`, `pit_flag`.I campi principali sono `adj_close`, `ret`, `log_ret`, `log_ret_estimation` e le feature laggate (`lag_ma_5`, `lag_ma_21`, `lag_vol_21`).`audit/qa_data_log.csv` registra copertura, null, outlier e valuta finale per simbolo/sorgente, fungendo da Acceptance Evidence per la pietra miliare ETL.


## Utilizzo CLI e filtraggio
Esempio completo:
```bash
fair3 ingest --source fred --symbols DGS10 DCOILWTICO --from 2010-01-01
```
Il parametro `--from` filtra le osservazioni successive alla data indicata dopo il download (utile quando gli endpoint non espongono filtri di query omogenei).Se non vengono specificati simboli, ogni fetcher utilizza un set di default documentato nel rispettivo modulo. Per `fred` il set copre Treasury a scadenze 1-30Y, Treasury Bill a 3 mesi, CPI, breakeven 5Y/10Y e TIPS 5Y/10Y.

## Note di licenza e ridistribuzione
- I dati vengono scaricati solo localmente; non devono essere ridistribuiti nel repository.
- Alcune fonti (es. ECB, BoE) richiedono attribuzione e limitano l'uso commerciale: conservare i log prodotti in `artifacts/logs/`.
- In caso di errore HTTP o payload inatteso, il fetcher solleva eccezioni che devono essere intercettate dal livello CLI/ETL per applicare retry o fallback interni.

## Prossimipassi
- L'ETL convertirà i CSV grezzi in pannelli PIT Parquet, applicando controlli di qualità e sincronizzando i fusi orari.
- Il security master SQLite replicherà le ultime anagrafiche disponibili per strumenti UCITS/ETFs.
