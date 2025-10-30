# Configurazione FAIR-III

Questo documento riassume i file YAML e le variabili richieste per eseguire la
pipeline FAIR-III sia da CLI sia dalla GUI.

## Directory principali

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `raw_root` | `data/raw` | CSV originali scaricati dai provider. |
| `clean_root` | `data/clean` | Artefatti ETL (panel, macro, mapping). |
| `artifacts_root` | `artifacts` | Directory padre per fattori, stime, pesi. |
| `report_root` | `artifacts/reports` | Cartella dove la GUI salva i report automatici. |
| `universe_root` | `data/clean/universe` | Output della pipeline Universe. |
| `log_root` | `artifacts/logs` | Log JSON e metriche generate da `fair3.engine.logging`. |

Gli stessi percorsi possono essere forniti alla CLI (`--raw-root`, `--report-root`, ...)
o passati al comando `fair3 gui`.

## File YAML

- `configs/thresholds.yml` – soglie di rischio per EWMA, drawdown e accettazione report.
- `configs/params.yml` – parametri household e limiti operativi usati dagli allocator.
- `configs/goals.yml` – obiettivi Monte Carlo per la simulazione finanziaria.
- `configs/testfolio_presets.yml` – preset sintetici utilizzati dai test.

I file vengono validati da `fair3 validate` prima di eseguire la pipeline e copiati
a fini di audit dentro `artifacts/logs/`.

## Credenziali

Le chiavi API non vengono più salvate in chiaro: il pannello **API key** della GUI
utilizza `fair3.engine.infra.secrets` per persistere le credenziali nel keyring del
sistema operativo. I servizi seguono il prefisso `fair3:<env>.lower()`. Esempi:

```bash
keyring set fair3:alphavantage_api_key default
keyring set fair3:tiingo_api_key default
```

## Variabili d'ambiente

| Variabile | Effetto |
| --- | --- |
| `FAIR_JSON_LOGS` | Se impostato a `1`, abilita sempre il logging JSON. |
| `FAIR_LOG_LEVEL` | Forza il livello minimo (`INFO`, `DEBUG`, ...). |
| `PYTHONUTF8` | Consigliato per garantire output UTF-8 coerenti nella CLI. |

Le variabili vengono rispettate sia dalla CLI sia dalla GUI.
