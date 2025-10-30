# Estensione e plugin FAIR-III

FAIR-III organizza le estensioni in tre insiemi principali: broker, data
provider e generatori di pipeline. Questa guida illustra come registrare nuove
componenti e come la GUI rileva automaticamente le estensioni.

## Broker

1. Creare un modulo in `fair3/engine/brokers/` che esponga una classe derivata
   da `BrokerFetcher` (vedere `trade_republic.py` come riferimento).
2. Registrare il broker in `fair3/engine/brokers/__init__.py` e aggiornarne la
   funzione `available_brokers`.
3. La GUI leggerà l'elenco aggiornato tramite `fair3.engine.brokers.available_brokers`
   e popolerà la scheda **Broker** senza ulteriori modifiche.

## Data provider

1. Implementare un fetcher derivando da `BaseCSVFetcher` in
   `fair3/engine/ingest/`. Impostare `SOURCE`, `LICENSE` e override di `fetch`/`parse`.
2. Registrare il fetcher in `fair3/engine/ingest/__init__.py` e aggiungere la
   sorgente a `available_sources()`.
3. Se il provider richiede una chiave API, aggiungere una voce a
   `fair3.engine.ingest.registry.PROVIDER_CREDENTIALS` specificando `source`,
   `env`, `label` e URL informativo. La scheda **API key** verrà aggiornata in
   automatico.
4. La scheda **Data provider** della GUI popolerà la combo box con la nuova
   sorgente al prossimo avvio.

## Pipeline personalizzate

Le pipeline principali (`run_factor_pipeline`, `run_estimate_pipeline`, ...)
possono essere estese sostituendo i percorsi in `configs/params.yml` o fornendo
hook personalizzati a livello di CLI. Per aggiungere una nuova fase visibile
nella GUI è consigliabile:

1. Creare una funzione wrapper che esegua la pipeline personalizzata
   utilizzando i percorsi standard (salvataggio in `artifacts/<custom>/`).
2. Aggiungere un bottone secondario nella scheda **Pipeline** modificando
   `fair3/engine/gui/panels/pipeline.py`.
3. Collegare il bottone a un metodo di `FairMainWindow` che invii il job tramite
   `JobRunner` e aggiorni lo stato.

## Packaging

Nuove estensioni dovrebbero esportare le loro dipendenze opzionali tramite
`pyproject.toml` e documentarne l'uso nelle rispettive cartelle `docs/`.
