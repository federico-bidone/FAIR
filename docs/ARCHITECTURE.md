# Architettura FAIR-III

Questo documento descriverà la progettazione a più livelli del motore FAIR-III attraverso i componenti di acquisizione, ETL, modellazione dei fattori, stima, allocazione, mappatura, sovrapposizione del regime, esecuzione, reporting, robustezza e pianificazione degli obiettivi. Contenuti dettagliati verranno aggiunti man mano che l'implementazione procede attraverso le tappe pianificate.

## Automation & Orchestration Layer (PR-04)
- La GUI PySide6 opzionale (`fair3.engine.gui`) espone tab modulari per broker,
  provider, pipeline, keyring e report e utilizza `QThreadPool` per eseguire i job
  senza bloccare l'interfaccia.
- Le credenziali vengono salvate nel keyring tramite `fair3.engine.infra.secrets`;
  il pannello **API key** maschera i valori nei log e sincronizza le variabili
  d'ambiente della sessione.
- La scheda **Pipeline** implementa sia ingest manuali sia la catena automatica
  Universe → ingest provider suggeriti → ETL → fattori → stime → report in
  `artifacts/reports/<timestamp>/`.

## Factor Layer (PR-05)
- `FactorLibrary` genera gli 8–10 macro-premia deterministici partendo dal pannello
  clean, applicando spread quantili coerenti con i segni economici e seed centrali.
- `enforce_orthogonality` fonde fattori altamente correlati e salva loading PCAper
  audit e governance delle soglie di condizionamento (`tau.delta_rho`).
- Il pipeline orchestrator (`run_factor_pipeline`) scrive `factors.parquet`,
  `factors_orthogonal.parquet`, metadati JSON e, opzionalmente, `validation.csv` (CP-CV,
  DSR, RC Bianco, FDR).`fair3 factors` richiama la pipeline e registra lo snapshot seed/config.

## Livello di stima (Motore Σ – PR-06)
- Stimatori della contrazione (Ledoit–Wolf, lazo grafico tramite BIC, contrazione del fattore)
  produrre covarianze candidate sul pannello dei rendimenti pulito.
- L'aggregazione mediana per elemento e la proiezione Higham mantengono la PSD.
- La fusione EWMA collega stime consecutive per rispettare le tolleranze di deriva
  `configs/thresholds.yml`.
- La diagnostica della deriva alimenta la logica di esecuzione/no-trade e le porte di accettazione.
- `run_estimate_pipeline` orchestri μ/Σ (ensemble + BL fallback) e persiste
  `mu_post.csv`, `sigma.npy`, `blend_log.csv`, aggiornando `risk/sigma_drift_log.csv` e
  l'audit trail(`fair3 estimate`).

## Optimisation Layer (PR-08)
- I generatori A–D rispettano i vincoli ERC cluster, CVaR/EDaR, turnover e DRO e forniscono
  baseline HRP.
- Il meta-learner combina al più tre generatori penalizzando turnover e tracking-error,
  producendo pesi non negativi che sommano a 1.
- `run_optimization_pipeline` salva i pesi di ciascun generatore, l'allocazione finale,
  diagnostiche RC e, se attivo, `meta_weights.csv`.Il comando `fair3 optimize` cura anche
  la registrazione degli audit snapshot.

## Mapping Layer (PR-09)
- Le regressioni rolling ridge traducono i portafogli fattoriali in beta degli strumenti con
  governance dei segni opzionale e metadati per gli audit downstream.
- Le bande Bootstrap CI80 contrassegnano le esposizioni rumorose in modo che le fasi downstream possano limitare o ridurre
  strumenti quando `beta_CI_width` supera le soglie.
- L'HRP intra-cluster assegna budget uguali per etichetta di fattore prima di ridistribuirli
  all'interno dei cluster per mantenere la diversificazione.
- Le protezioni dagli errori di tracciamento e dall'ADV riducono i pesi verso le linee di base e ridimensionano le operazioni
  per rimanere entro le tolleranze di liquidità degli OICVM.
- `run_mapping_pipeline`(CLI: `fair3 map`) allinea fattori/strumenti, calcola beta,
  CI, pesa strumenti con baseline HRP opzionale, applica TE/ADV caps e aggiorna l'audit.

## Regime Layer (PR-10)
- Il comitato deterministico combina un HMM gaussiano a due stati sui rendimenti di mercato,
  indicatori di stress di volatilità e punteggi di rallentamento macro in una crisi
  probabilità.
- La logica dell'isteresi applica soglie `on > off`, periodi di permanenza e finestre di raffreddamento
  per evitare il ribaltamento tra i regimi.
- La mappatura dell'inclinazione converte le probabilità in una miscelapesi per le allocazioni sensibili alla crisi
  utilizzate dal livello di esecuzione.

## Execution Layer (PR-11)
- Il dimensionamento dei lotti converte i delta di peso in ordini interi utilizzando prezzi e minimi di lotto
  , garantendo che gli strumenti a prezzo zero non generino operazioni spurie.
- Il modello dei costi di transazione combina commissioni esplicite, slippage di metà spread e impatto basato su ADV
  calibrato sulle curve di stile Almgren–Chriss.
- L'euristica fiscale italiana distingue i govies (12, 5%) da altri asset.(26%),
  applica un intervallo di perdite mobili e aggiunge un'imposta di bollo dello 0, 2% sui saldi positivi.
- I cancelli di deriva/fatturato combinano EB_LB − COST − TAX > 0 con bande di tolleranza su
  ponderazioni e contributi al rischio per evitare un abbandono non necessario.
- I riepiloghi decisionali alimentano le prove CLI e gli artefatti di audit in
  `artifacts/costs_tax/` e `artifacts/trades/`.

## Reporting Layer (PR-12)
- `MonthlyReportInputs` pacchetti di artefatti PIT (restituzioni, ponderazioni, fattori &
  attribuzione dello strumento, fatturato, costi, imposte, conformitàflag).
- `compute_monthly_metrics`/`generate_monthly_report` emettono output deterministici
  CSV/JSON più grafici (`fan_chart.png`, `attribution.png`,
  `turnover_costs.png`) all'interno di `artifacts/reports/<period>/`.
- Gli aiutanti di trama si affidano al backend Agg per la compatibilità CI e chiudere le cifre
  dopo il salvataggio per evitare perdite di memoria.
- I riepiloghi dei cluster ERC eseguono il rollup dei pesi per cluster per verificare l'accettazione
  tolleranza `tau.rc_tol` downstream.
- Il wrapper CLI attualmente semina dispositivi sintetici in modo da controllare/testare l'infrastruttura
  può convalidare il contratto di reporting fino al cablaggio completo della pipelinelands.

## Robustness Layer (PR-13)
- `run_robustness_lab` orchestra bootstrap di blocchi, replay di shock e ablazione
  si attiva/disattiva, artefatti persistenti in `artifacts/robustness/` insieme a un riepilogo del gate JSON
  per le asserzioni CI.
- Bootstraps si basa su blocchi sovrapposti di 60 giorni con il flusso `robustness`
  RNG dedicato in modo che le esecuzioni ripetute in CI/Windows riproducano distribuzioni identiche.
- Lo scenario riproduce crisi stilizzate in scala (olio del 1973, 2008Crisi finanziaria globale, COVID 2020, anni '70
  stagflazione) alla volatilità osservata, facendo emergere prelievi nel caso peggiore per
  revisione della governance.
- Il sistema di ablazione prevede un callback che riesegue la pipeline a valle
  componenti con flag di governance specifici disattivati, registrazione delta metrici
  (ad esempio, Sharpe, drawdown, TE) per dimostrare il contributo di ciascun guardrail.

## Goals Layer (PR-14)
- `simulate_goals` campiona gli stati del regime di Bernoulli (base vs crisi) al mese
  utilizzando curve sintetiche seminate tramite `SeedSequence`, producendodistribuzione della ricchezza finale
  per ogni obiettivo familiare configurato.
- I programmi di contribuzione crescono a un tasso annuale configurabile mentre i percorsi di discesa
  spostano linearmente l'allocazione dalla crescita alle attività difensive oltre il massimo
  Horizon.
- `run_goal_monte_carlo` scrive `goals_<investor>_summary.csv`,
  `goals_<investor>_glidepaths.csv`, `goals_<investor>_fan_chart.csv` e un
  PDF `goals_<investor>.pdf` sotto `reports/` (o root custom) così CI e auditor
  possono verificare, fan-chart e glidepath adattivo.
- CLI cablaggio(`fair3 goals`) carica `configs/goals.yml`/`configs/params.yml`,
  applica sostituzioni opzionali e stampa le probabilità di successo ponderate per
  un rapido feedback durante l'ottimizzazione.
