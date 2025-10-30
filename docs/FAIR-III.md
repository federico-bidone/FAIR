# Metodologia FAIR-III

## Stack dei fattori macro (PR-05)
Il motore dei fattori FAIR-III sintetizza dieci premi macro, combinando spread trasversali lunghi/corti e sovrapposizioni macro. Ciascun fattore è ancorato a un segno economico atteso e costruito in base al pannello point-in-time generato in PR-04.

- **Mercato globale (`global_mkt`)** – proxy beta di uguale ponderazione.
- **Momentum globale/Ciclo di crescita** – rendimenti log finali alti-mini-bassi e acquisizioni di momentum a breve termine migliorate.
- **Inversione a breve termine/rimbalzo del valore** –inclinazioni contrarian che sfruttano la sottoperformance ritardata.
- **Carry Roll-Down** – spread di momentum 5-21 giorni come proxy roll premium.
- **Qualità e stabilità difensiva** – esposizioni a bassa volatilità e momentum per unità di rischio.
- **Rischio di liquidità** – spread di coorte con volatilità alta-bassa.
- **Copertura dall'inflazione/Beta dei tassi** – sovrapposizioni macro guidate da sorprese sull'inflazione e sui tassi ufficiali (ripiego a zero in assenza di dati macro).

Ogni serie di fattori è generata deterministicamente tramite `FactorLibrary` e salvata da
`run_factor_pipeline`(`fair3 factors`) che registra anche metadata (`FactorDefinition.expected_sign`)
e diagnostiche CP-CV/FDR per audit e compliance.

### Validation & Controls
- **Cross-Purged CV (CP-CV)** con embargo garantisce l'assenza di look-ahead nei factor testing.
- **Deflated Sharpe Ratio (DSR)** quantifica la significatività statistica diStime di Sharpe.
- **White Reality Check (bootstrap di permutazione)** protegge dal data mining, con il filtro FDR Benjamini–Hochberg per controllare le false scoperte nella libreria.
- **Guardrail di ortogonalità** uniscono fattori altamente correlati (|ρ| > τ) e applicano la rotazione PCA quando il numero di condizione della matrice di correlazione supera la tolleranza nel `configs/thresholds.yml`.

## Motore dei rendimenti attesi(PR-07)
Lo stack μ segue un design d'insieme deterministico:

- **Baseline ridotta a zero:** campione significa ridotto verso 0 con intensità
  legato a T/N, garantendo stabilità quando la cronologia è breve.
- **Bagging OLS:** modelli lineari bootstrap su macro ritardate + funzionalità di restituzione
  forniscono previsioni condizionali a bassa varianza.
- **Potenziamento del gradiente:** alberi poco profondi con arresto anticipato della cattura della luce
  non linearità senza sacrificare la riproducibilità.
- **impilamento della cresta:** la regressione della cresta non negativa combina gli studenti di base,
  utilizzando pieghe di convalida incrociata di serie temporali per calibrare il mix.
- **Miscela Black–Litterman:** `reverse_opt_mu_eq` deduce rendimenti di equilibrioda
  Σ e pesi di mercato; `blend_mu` applica il fallback ω:=1 ogni volta che il rapporto informazioni
  viola `tau. IR_view` in `configs/thresholds.yml`.

`run_estimate_pipeline` (`fair3 estimate`) persiste `mu_post.csv`, `mu_star.csv`,
`mu_eq.csv`, `sigma.npy` e `blend_log.csv` con ω e IR_view per audit trail, oltre a
`risk/sigma_drift_log.csv` quando confronta tempi consecutivi.

## Covariance Engine (PR-06)
Il covariance stack combina più stimatori per mantenere la struttura PSD e
monitorare la strutturaderiva:

- **Ritiro Ledoit–Wolf** verso la linea di base dell'identità.
- **Lazo grafico** con selezione del modello BIC per promuovere matrici di precisione sparsa
  .
- **Contrazione del fattore** da autovettori principali più rumore idiosincratico positivo
  .
- **Aggregazione mediana per elementi** seguita da **Proiezione PSD di Higham**.
- **Mediana SPD geometrica** consenso opzionale (`--sigma-engine spd_median`) calcolato
  tramite discesa del gradiente affine-invariante con fallback di Higham sunon convergenza.
- **Combinazione del regime EWMA** con `lambda_r` configurabile per agevolare le transizioni
  applicando al tempo stesso la PSD in ogni fase.
- **Diagnostica della deriva** (`frobenius_relative_drift`, `max_corr_drift`) alimenta il
  gate di accettazione in `configs/thresholds.yml`.

Gli artefatti sono scritti direttamente in `artifacts/estimates/` e accompagnati
da snapshot seed/config attraverso `reporting.audit`.

## Allocation Stack (PR-08)
Il livello di allocazione introduce quattro generatori deterministici più un meta-leaner:

- **Generatore A (Sharpe + vincoli):**risolve un programma convesso che massimizza il rendimento atteso penalizzato da un raggio DRO di Wasserstein, applicando al contempo pesi long-only, limiti di fatturato/leva lorda e limiti di rischio CVaR95/EDaR basati su scenari. Il bilanciamento del cluster ERC viene applicato dopo la risoluzione per onorare la tolleranza `tau.rc_tol`.
- **Generatore B (HRP):** linea di base di parità di rischio gerarchica classica utilizzando collegamento Ward e quasi-diagonalizzazione, che funge da benchmark al dettaglio e riferimento del gate di accettazione.
- **Generatore C (forma chiusa DRO):** inverso regolarizzato in cresta di Σ scalato in base all'avversione al rischio `γ` e penalità`ρ`, ottenendo un rapido fallback quando le risorse del risolutore sono limitate.
- **Generatore D (CVaR-ERC):** riduce al minimo il CVaR dello scenario soggetto a limiti di turnover/leva e bilanciamento del cluster ERC per allocazioni sensibili al rischio di coda.
- **Meta learner:** adatta pesi simplex non negativi ai PnL del generatore con penalità di rischio quadratico e penalità di turnover/TE relative a un generatore di base (HRP predefinito).

Il pipeline `run_optimization_pipeline`(`fair3 optimize`) genera CSV per ciascun
motore, l'allocazione finale, diagnostiche ERC e, se richiesto, `meta_weights.csv`,
registrando audit snapshot e checksum.

## Mapping & Liquidity (PR-09)
Il livello di mappatura traduce i pesi fattoriali in strumenti implementabili mentre
rispettando i guardrail di liquidità degli OICVM:

- **Beta Rolling Ridge:** `rolling_beta_ridge` centra ciascuna finestra, applica
  parametro Ridge `lambda_beta` e memorizza i metadati dello stimatore per la diagnostica bootstrap downstream
  .I vincoli di segno opzionali applicano i valori a priori economici.
- **Intervalli di confidenza bootstrap:** `beta_ci_bootstrap` ricampiona le finestre con
  flussi RNG deterministici per calcolare gli intervalli CI80 utilizzati per limitare i beta rumorosi quando
  `width > tau.beta_CI_width`.
- **Caps basati su CI:** `cap_weights_by_beta_ci` scala i pesi degli strumentiquando
  CI80 allarga la breccia `tau.beta_CI_width`, preservando il budget dopo
  rinormalizzazione.
- **HRP intra-fattore:** `hrp_weights` divide i quadri strumenti in base all'etichetta del fattore
  e assegna budget cluster uguali prima di eseguire l'HRP all'interno di ciascun gruppo.
- **Budget degli errori di tracciamento:** `enforce_te_budget` limita le deviazioni dei fattori a
  `TE_max_factor`, mentre `enforce_portfolio_te_budget` riduce la mappaturapondera
  verso una linea di base (ad esempio, HRP) per soddisfare la stessa tolleranza.
- **Limiti ADV:** `clip_trades_to_adv` converte i pesi commerciali proposti in
  termini nozionali e li ridimensiona per rispettare i limiti percentuali ADV mentre
  preservando la direzione commerciale.

`run_mapping_pipeline` (`fair3 map`) scrive i rolling betas, le CI80, il riassunto di
tracking-error e `weights/instrument_allocation.csv`, aggiornando i log di audit per
beta, TE e clip ADV prima dell'esecuzione.

## Regime Overlay (PR-10)
The regimeallocazioni di layer guards con una probabilità di crisi deterministica
comitato e controlli di isteresi:

- **Segnali del comitato:** rendimenti di mercato di pari peso alimentano un sistema a due stati fissi
  HMM gaussiano, lo stress di volatilità deriva dai rapporti di volatilità
  mediana mobile normalizzata, mentre i punteggi di rallentamento macro provengono da delta standardizzati degli indicatori macro
  .I pesi dei componenti sono predefiniti su (0, 5, 0, 3, 0, 2) e sono
  normalizzati per la verificabilità.
- **Governance delle probabilità:** gli output vengono ritagliati su \[0, 1\] e registrati per
  gate di accettazione downstream. Gli input mancanti vengono ripristinati a priori neutri per mantenere
  la sovrapposizione deterministica.
- **Isteresi + pausa:** `apply_hysteresis` applica soglie di attivazione/disattivazione (impostazione predefinita
  on=0, 65, off=0, 45), permanenza minima (20 giorni di negoziazione) e cooldown (10 giorni)
  prima del rientro. Ciò impedisce rapidi ribaltamenti durante mercati instabili.
- **Mappatura del tilt:** `tilt_lambda` mappa linearmente le probabilità di crisi per il tilt
  pesi in \[0, 1\], combinando le allocazioni di base e di crisi durante l'esecuzione.

La sovrapposizione mostrerà i registri e la diagnostica dei componenti in
`artifacts/audit/regime/` quando il cablaggio CLI si atterra, garantendo la riproducibilitàaudit
percorsi per i controlli di conformità.

## Execution Layer (PR-11)
Il livello di esecuzione applica i guardrail di vendita al dettaglio prima che qualsiasi ordine venga instradato:

- **Dimensionamento dei lotti:** `size_orders` converte i delta di peso in lotti interi utilizzando
  valore del portafoglio, prezzi e dimensioni dei lotti; `target_to_lots` rimane disponibile come alias
  thin per compatibilità con le versioni precedenti.
- **Costi di transazione:** `trading_costs` implementa lo schema Almgren–Chriss –
  commissioni esplicite, slippage di metà spread e impatto di mercato non lineare ridimensionato in base alla percentuale
  ADV – mentre `almgren_chriss_cost` espone l'impatto aggregatoper i riepiloghi
  CLI.
- **Imposte:** `compute_tax_penalty` applica il regime italiano (26% default,
  12, 5% per govies ≥51%, 0, 2% bollo) con abbinamento FIFO/LIFO/min_tax e
  quadriennale `MinusBag` loss carry; `tax_penalty_it` rimane un'euristica aggregata
  rapida.
- **No-trade guard:** `drift_bands_exceeded` controlla il peso e il contributo al rischio
  deriva rispetto alle bande di tolleranza; `expected_benefit_distribution` e
  `expected_benefit_lower_bound` stimano EB_LB tramite bootstrap a blocchi prima
  `should_trade` combinano drift, limiti di fatturato e EB_LB − COST − TAX > 0
  gate di accettazione.
- **Riepiloghi delle decisioni:** `DecisionBreakdown` struttura la valutazione del gate per le prove
  CLI e la registrazione dell'audit prima dell'arrivo completo del controller in PR-12.

Gli output verranno popolati `artifacts/trades/` e `artifacts/costs_tax/` insieme alle istantanee dell'audit
per mantenere la riproducibilità.

## Reporting eInformativa mensile (PR-12)
Il livello di reporting trasforma gli artefatti PIT in informative adatte al dettaglio:

- **Pacchetto di metriche:** `compute_monthly_metrics` annualizza i rendimenti, calcola
  Sharpe, Max Drawdown, CVaR(95) e EDaR a tre anni utilizzando l'arrotondamento deterministico
   (4 d.p.).I risultati vengono emessi sia come CSV che come JSON per la verificabilità.
- **Attribuzione:** I contributi di fattori e strumenti vengono aggregati mensilmente
  ed esportati affiancati con grafici a barre in pila per l'ispezione visiva.
- **Grafici a ventaglio:** `simulate_fan_chart` bootstrap di ricchezza e percorsi di rendimento tramite
  `numpy.random.default_rng(seed)`; `plot_fan_chart`/`plot_fanchart` visualizza
  output PNG deterministici per parametri di ricchezza e rischio in
  `artifacts/reports/<period>/`.
- **Fatturato e costi:** riga/barra di alimentazione delle serie mensili di fatturato, costi e imposte
  combo per evidenziare la conformità con il fatturato e i budget TE.
- **Cluster ERC:** Mappe dei cluster opzionali raggruppano i pesi mensili medi,
  supporto dei cancelli di accettazione sulle tolleranze di parità di rischio dei cluster.
- **Registro di conformità:** Indicatori come idoneità OICVM, completamento dell'audit, e
  l'adesione alle norme no-trade viene mantenuta in `compliance.json` per i controlli a valle.
- **Porte di accettazione:** `acceptance_gates` valuta P(MaxDD > τ) e il CAGR
  limite inferiore, emettendo `acceptance.json` con verdetti pass/fail.
- **IC di attribuzione:** `attribution_ic` calcola i contributi degli strumenti,
  i contributi dei fattori e le metriche IC variabili, facoltativamente persistenti come CSV per
  revisioni della governance.
- **Dashboard PDF:** `generate_monthly_report` riunisce metriche, flag di conformità
  , gate di accettazione e artefatti grafici in un PDF compattoutilizzando
  `reportlab`.

Il wrapper CLI (`fair3 report --period ... --monthly`) attualmente alimenta il generatore di report
con dati sintetici deterministici in modo che i gate di accettazione e CI
rimangono verdi mentre l'orchestrazione a monte è collegata. I futuri PR scambieranno lo stub sintetico
 con artefatti PIT reali una volta completata la pipeline end-to-end.

## Robustness Lab & Ablation (PR-13)
Il laboratorio di robustezza estende la governance FAIR-III con stress test deterministici:

- **Block bootstrap:** `block_bootstrap_metrics` campioniBlocchi di 60 giorni (1000 estrazioni predefinite) per
  calcolare le distribuzioni del prelievo massimo, CAGR, Sharpe, CVaR ed EDaR.I cancelli di accettazione applicano
  P(MaxDD ≤ τ) ≥ 95% e il CAGR del 5° percentile ≥ target. Tutte le esecuzioni utilizzano il flusso
  `robustness` RNG in modo che siano riproducibili nell'IC e nella ricerca
  ambientali.
- **Replay shock:** `replay_shocks` ripropone profili di crisi stilizzati (petrolio del 1973,
  2008 GFC, 2020 COVID, stagflazione degli anni '70) adattati alla volatilità realizzata del
  i rendimenti degli input, evidenziando i prelievi nel caso peggiore per le revisioni della governance.
- **Imbracatura dell'ablazione:**`run_ablation_study` attiva/disattiva gli interruttori di governance (BL
  fallback, proiezione Σ PSD, trigger di deriva, sanzioni meta TO/TE, inclinazione del regime,
  no-trade rule) per quantificare il loro incremento sui parametri chiave. L'orchestratore fornisce
  un callback che riesegue la pipeline downstream con i flag forniti.
- **Artefatti:** `run_robustness_lab` consolida disegni bootstrap, scenari,
  tabelle di ablazione e un riepilogo PDF compatto all'interno di `artifacts/robustness/` e
  persiste un riepilogo JSON con i verdetti dei gate per le asserzioni CI.

Questi strumenti diagnostici supportano i gate di accettazione FAIR prima che vengano rilasciati i report mensili
, garantendo che i guardrail al dettaglio rimangano attivi anche in condizioni strutturalipause.

## Goal Planning & Glidepath (PR-14)
Gli obiettivi familiari estendono FAIR-III oltre la costruzione del portafoglio, fornendo un
motore Monte Carlo deterministico per l'analisi delle probabilità di successo:

- **Campionamento basato sul regime:** `simulate_goals` traccia mensilmente gli stati di Bernoulli tra i regimi di base e quelli di crisi
  , con parametri della curva generati tramite
  `SeedSequence` in modo che le esecuzioni rimangano identiche con lo stesso seed.
- **Politica di contribuzione:** `build_contribution_schedule` cresce mensilmente
  contributi a un tasso annuale configurabile (predefinito 2%), garantendoi piani di risparmio a lungo orizzonte
   riflettono la deriva dell'inflazione.
- **Glidepath:** `build_glidepath` passa linearmente l'allocazione da crescita
  pesante a pesi difensivi sull'orizzonte massimo attraverso obiettivi configurati,
  far emergere il mix di asset implicito per la revisione della governance.
- **Output:** `run_goal_monte_carlo` scrive deterministico `goals_<investor>_summary.csv`,
  `goals_<investor>_glidepaths.csv`, `goals_<investor>_fan_chart.csv`, e `goals_<investor>.pdf`
  sotto `reports/` (o root custom);
  il comando CLI`fair3 goals --simulate` stampa le probabilità ponderate e i
  percorsi dei file generati così l'utente può iterare rapidamente sui contributi
  e orizzonti.

Le soglie di accettazione derivano da `configs/goals.yml` (ricchezza target `W`,
probabilità minima `p_min`, pesi) e `configs/params.yml` (ipotesi contributive delle famiglie
).Le probabilità ponderate devono soddisfare i valori
`p_min` specificati per soddisfare il cancello di governance dell'obiettivo FAIR-III.
