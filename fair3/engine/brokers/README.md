# Fetcher degli universi broker

Questo pacchetto raccoglie i fetcher che trasformano l'universo investibile
di ciascun broker in una tabella normalizzata (`isin`, `name`, `section`,
`asset_class`). Tutte le classi devono derivare da `BaseBrokerFetcher` e
registrarsi nel registro centralizzato per essere disponibili via CLI.

## Come aggiungere un nuovo broker
1. **Crea un nuovo modulo** in `fair3/engine/brokers/` con una classe che
   estende `BaseBrokerFetcher`. Imposta gli attributi `BROKER` e `SOURCE_URL`
   e implementa `fetch_universe()` restituendo un `BrokerUniverseArtifact`.
2. **Documenta la logica di parsing** con docstring in italiano, indicando
   eventuali filtri, licenze o parametri opzionali per restringere l'universo.
3. **Aggiorna `registry.py`** aggiungendo la tua classe al dizionario
   restituito da `_fetcher_map()`. In questo modo il nuovo broker comparirà
   automaticamente tra le scelte di `fair3 universe --brokers`.
4. **Scrivi test mirati** in `tests/unit/` che validino il parsing con PDF,
   CSV o API di esempio. I test dovrebbero coprire casi con filtri attivi e
   campi mancanti.
5. **Estendi la documentazione utente** (es. `README.md` o guide specifiche)
   descrivendo la fonte, la licenza e le eventuali credenziali richieste.

Seguendo questi passaggi la pipeline `fair3 universe` rileverà il nuovo
broker e arricchirà automaticamente gli ISIN con i listing OpenFIGI e le
preferenze di provider configurate.
