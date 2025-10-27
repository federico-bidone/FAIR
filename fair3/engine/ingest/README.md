# Ingest Module

## Scopo
Il sottosistema di ingest raccoglie dati grezzi da fonti pubbliche (ECB, FRED, Bank of England, Stooq) e li salva sotto `data/raw/<source>/` in formato CSV, garantendo retry/backoff e tracciabilità della licenza.

## API pubbliche
- `BaseCSVFetcher.fetch(symbols=None, start=None, as_of=None)` scarica uno o più simboli restituendo un `IngestArtifact` con `data`, `path` e metadati (licenza, URL richiesti, timestamp).
- `available_sources()` elenca i codici sorgente supportati.
- `create_fetcher(source, **kwargs)` restituisce l'istanza di fetcher pronta all'uso.
- `run_ingest(source, symbols=None, start=None, raw_root=None, as_of=None)` è l'entry point usato dal CLI.

Tutti i fetcher accettano `raw_root` opzionale per redirigere l'output (utile nei test) e loggano automaticamente licenza e URL tramite `fair3.engine.logging.setup_logger`.

## Utilizzo CLI
```bash
fair3 ingest --source ecb --symbols USD GBP --from 2020-01-01
```
- `--source`: uno tra `ecb`, `fred`, `oecd`, `boe`, `bis`, `cboe`, `stooq`, `french`, `aqr`, `alpha`, `worldbank`, `nareit`, `lbma`, `portviz`, `yahoo`, `alphavantage_fx`, `tiingo`, `coingecko`, `binance`.
- `--symbols`: lista opzionale di simboli specifici della sorgente (default codificati per ogni fetcher).
- `--from`: data minima (ISO `YYYY-MM-DD`) per filtrare le osservazioni.

Per FRED, i simboli predefiniti coprono Treasury a più scadenze, TIPS,
breakeven e CPI:

```
DGS01, DGS02, DGS03, DGS05, DGS07, DGS10, DGS20, DGS30,
DTB3, CPIAUCSL, T5YIE, T10YIE, DFII5, DFII10
```

Per la sorgente `french` i simboli predefiniti includono i fattori mensili di mercato (`research_factors_monthly`),
il pacchetto 5x5 (`five_factors_2x3`), il fattore momentum (`momentum`) e i portafogli 49 industrie (`industry_49`). I valori
sono normalizzati in forma decimale (percentuale/100) e il campo `symbol` è composto come `<dataset>_<fattore>`.

Per `aqr` i simboli predefiniti (`qmj_us`, `bab_us`, `value_global`) richiedono che l'utente scarichi manualmente i file CSV
da [AQR Data Sets](https://www.aqr.com/Insights/Datasets) e li copi nella cartella `data/aqr_manual/`. Il fetcher verifica la
presenza dei file, effettua il parsing in formato FAIR (date, value, symbol) e converte automaticamente i valori percentuali in
decimali. Se i file non sono presenti, viene sollevato un `FileNotFoundError` con istruzioni per il download.

Per `alpha` i simboli predefiniti coprono un mix di sorgenti: `alpha_qmj` e `qfactors_roe` sono scaricati via HTTP dai rispettivi
provider, mentre `novy_profitability` richiede di salvare manualmente la tabella HTML in `data/alpha_manual/`. Il parser gestisce
payload CSV e HTML, scala automaticamente le percentuali e allinea le date a fine mese.

Per `stooq` i suffissi `.us`/`.pl` vengono normalizzati automaticamente, il DataFrame restituisce `symbol` in upper-case e la colonna
`tz="Europe/Warsaw"`. Il fetcher mantiene inoltre un cache in memoria per evitare download ripetuti all'interno della stessa
esecuzione; il filtro `--from` viene applicato dopo il parsing poiché l'endpoint non accetta parametri di data.

Per `oecd` il simbolo deve includere dataset e dimensioni SDMX (es. `MEI_CLI/LOLITOAA.IT.A`). Il fetcher applica automaticamente
`contentType=csv`, `dimensionAtObservation=TimeDimension` e `timeOrder=Ascending`, supporta `startTime` derivato dal parametro
`--from` e rifiuta payload HTML (rate limit o pagine di errore). I default scaricano il Composite Leading Indicator per Italia e
area euro.

Per `bis` il formato del simbolo è `<dataset>:<area>:<freq>` (es. `REER:ITA:M`). Il fetcher compone l'URL SDMX
`https://stats.bis.org/api/v1/data/<dataset>/<freq>.<area>?detail=dataonly&format=csv`, arrotonda `startPeriod`
alla frequenza richiesta (mensile, trimestrale o annuale) e rifiuta payload HTML o senza colonne `TIME_PERIOD`/`OBS_VALUE`.

Per `cboe` i simboli supportati sono `VIX` e `SKEW`. Il fetcher scarica i CSV pubblici da
`https://cdn.cboe.com/api/global/us_indices/daily_prices`, rifiuta le risposte HTML (tipiche di rate limit o errori)
e normalizza il valore di chiusura/indice in formato FAIR. L'eventuale filtro `--from` viene applicato post-download.

Per `worldbank` ogni simbolo segue il formato `<indicatore>:<paese1;paese2>`. Il fetcher effettua richieste JSON verso
`https://api.worldbank.org/v2/country/<paesi>/indicator/<indicatore>` con `per_page=20000`, gestisce automaticamente la
paginação riportata nel metadata e normalizza i valori in colonne `date`, `value`, `symbol` dove `symbol` diventa
`<indicatore>:<ISO3>`. I default scaricano popolazione totale e PIL reale per l'Italia.

Per `nareit` bisogna scaricare manualmente l'Excel `NAREIT_AllSeries.xlsx` e copiarlo in `data/nareit_manual/`. Il fetcher legge il foglio mensile, converte le date a fine mese e normalizza gli indici Total Return (All Equity e Mortgage REIT) in formato FAIR, includendo la licenza “for informational purposes only” nei metadati.

Per `portviz` è necessario scaricare manualmente i CSV (es. US Total Stock Market, International Developed Market) dal sito Portfolio Visualizer e copiarli in `data/portfolio_visualizer_manual/` mantenendo i nomi documentati nel modulo. Il parser scala automaticamente le percentuali contenute nella colonna `Return`, allinea le date a fine mese e riporta nei metadati la licenza “Portfolio Visualizer — informational/educational use”.

Per `lbma` i simboli `gold_pm` e `silver_pm` estraggono la tabella HTML dei fixing delle 15:00 London, convertono i prezzi da USD a EUR tramite i cambi BCE e impostano `pit_flag=1` quando l'orario corrisponde alle 16:00 CET. Se i cambi non sono disponibili localmente il fetcher richiama automaticamente `ECBFetcher`.

Per `yahoo` è necessario installare la dipendenza opzionale `yfinance` (`pip install yfinance`).
Il fetcher usa serie daily auto-aggiustate, limita automaticamente l'intervallo a cinque anni dal
giorno corrente, attende due secondi tra le richieste per rispettare i limiti del servizio e registra
nei metadati la licenza "personal/non-commercial use". In ambienti di test è possibile passare
`delay_seconds=0` al costruttore per evitare attese artificiali.

Per `alphavantage_fx` occorre una chiave API (`ALPHAVANTAGE_API_KEY`). Il fetcher invia richieste
`function=FX_DAILY` verso `https://www.alphavantage.co/query`, aggiunge automaticamente il parametro
`apikey` senza esporlo nei log, rispetta il rate limit gratuito (5 chiamate/minuto) tramite attesa
deterministica e converte i CSV in formato FAIR (`timestamp` → `date`, `close` → `value`). In caso di
rate limit o chiave errata l'API restituisce un payload JSON con `Note`/`Error Message` che viene
tradotto in `ValueError`.

Per `tiingo` è necessario impostare `TIINGO_API_KEY`. Il fetcher invia richieste verso
`https://api.tiingo.com/tiingo/daily/<symbol>/prices`, aggiunge l'header `Authorization: Token <key>`
senza loggare il valore, applica un throttling deterministico (default 1s tra le chiamate) e
normalizza il payload JSON scegliendo `adjClose` se disponibile (fallback `close`). Se la risposta è
HTML o non contiene le colonne attese viene sollevato un `ValueError` informativo.

Per `coingecko` i simboli corrispondono agli identificativi CoinGecko (es. `bitcoin`, `ethereum`).
Il fetcher chiama l'endpoint `coins/<id>/market_chart/range`, applica un throttling minimo di un
secondo tra le richieste, campiona ogni giornata allineando il timestamp alle 16:00 CET (15:00 UTC)
e popola `pit_flag` quando l'osservazione è entro 15 minuti dall'orario target. I prezzi sono
convertiti nella valuta richiesta (default EUR) e i metadati riportano la licenza “CoinGecko API —
attribution required”.

Per `binance` i simboli corrispondono alle coppie del Data Portal (es. `BTCUSDT`). Il fetcher
scarica i file ZIP giornalieri `data/spot/daily/klines/<symbol>/<interval>/...`, li concatena,
aggiunge metadati sulla valuta quotata e imposta `pit_flag=1`. I default coprono `BTCUSDT` con
intervallo `1d`; il CLI accetta `--symbols` e `--from` per restringere l'arco temporale senza
richiedere API key, ricordando che la licenza vieta la redistribuzione bulk.

Il comando stampa un riepilogo con numero di righe e percorso del CSV prodotto. I log ruotati sono salvati in
`artifacts/audit/fair3_ingest_<source>.log`.

## Esempi Python
```python
from fair3.engine.ingest import run_ingest

result = run_ingest("fred", symbols=["DGS10"], start="2022-01-01")
print(result.path)
print(result.data.head())
```

## Flag `--trace`
Il tracciamento fine-grained verrà agganciato nei prossimi PR tramite l'opzione `--trace` del CLI. Al momento i fetcher espongono messaggi INFO con URL e licenza associati a ogni simbolo.

## Errori comuni
- **`ValueError: At least one symbol must be provided`**: nessun simbolo di default e lista vuota passata.
- **`requests.HTTPError`**: risposta non 200 dopo i retry previsti; controllare connettività o permessi della fonte dati.
- **`ValueError: Expected columns ...`**: il payload CSV non contiene le colonne attese, spesso dovuto a simbolo errato.

## Log e audit
Ogni esecuzione registra i dettagli in `IngestArtifact.metadata` (licenza, URL, timestamp, start-date) e crea file CSV datati (`<source>_YYYYMMDDTHHMMSSZ.csv`). Copiare questi metadati in `artifacts/audit/` è responsabilità del modulo `reporting.audit` introdotto nel PR precedente.
