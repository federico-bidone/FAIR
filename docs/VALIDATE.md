# Convalida della configurazione (`fair3 validate`)

Il comando `fair3 validate` esegue un controllo dello schema sui file di configurazione principali utilizzati dal motore di portafoglio
FAIR-III.È il passaggio pre-flight consigliato prima di eseguire pipeline di ottimizzazione ETL, factor o
 perché rileva tempestivamente le voci YAML con formato errato.

## Utilizzo

```bash
fair3 validate \
  --params configs/params.yml \
  --thresholds configs/thresholds.yml \
  --goals configs/goals.yml \
  --verbose
```

* `--params`, `--thresholds`, `--goals` consente di sovrascrivere le posizioni di configurazione predefinite.
* `--verbose` stampa i payload analizzati in modo che l'operatore possa esaminarli.valori predefiniti e campi derivati.

Lo stato di uscita è `0` quando la convalida ha esito positivo. Gli errori di schema o file vengono scritti sullo stdout con un file
`[fair3] validate error: ...` prefisso e il comando esce con stato `1`.

## Riepilogo schema

| File | Chiavi richieste | Note |
| ---- | ------------- | ----- |
| `params.yml` | `currency_base`, `household`, `rebalancing` | `currency_base` deve essere un codice ISO; `household` ora include i campi opzionali `investor`, `contribution_plan` (regole con `start_year`/`end_year`/`frequency`), e `withdrawals`; `rebalancing.no_trade_bands` ha un limite massimo di 50 bps. |
| `thresholds.yml` | `vol_target_annual`, `tau`, `execution`, `regime`, `drift` | `regime.on` deve superare `regime.off`; le strisce di attivazione/disattivazione sono ≥1; i pesi dei comitati e i pesi macro devono sommarsi a valori positivi; i limiti di fatturato, tracking error e ADV rimangono entro [0, 1]; l'obiettivo annuale di volatilità è compreso tra l'1% e il 50%. |
| `goals.yml` | `goals` (elenco non vuoto) | Ogni obiettivo richiede `name`, `W`, `T_years`, `p_min`, `weight`.Le probabilità si trovano in [0, 1]; i pesi vengono controllati per somme prossime all'unità con una tolleranza del 5%. |

Gli avvisi (ad esempio pesi obiettivo sbilanciati) vengono segnalati ma non falliscono la convalida. Trattateli come
richiede di rivisitare la configurazione prima di eseguire la pipeline completa.

Tutte le regole di convalida sono codificate tramite modelli [pydantic](https://docs.pydantic.dev/) situati in
`fair3/engine/validate.py`.I modelli sono versioni insieme al motore e garantiscono un comportamento deterministico
 su tutte le piattaforme.

> **Disclaimer:** strumento informativo/educativo; non costituisce consiglio finanziario o raccomandazione.
