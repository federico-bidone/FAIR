# Roadmap di Manutenzione FAIR-III

Questa roadmap suddivide il lavoro richiesto in una sequenza di pull request
indipendenti ma coordinate. Ogni fase include obiettivi tecnici chiari e criteri
di completamento in modo da rendere trasparente lo stato di avanzamento.

## PR 1 – Inventario e infrastruttura di verifica (in corso)
- Generare un inventario completo di tutte le funzioni Python con metadati
  (percorso, firma, docstring) da usare come checklist per la copertura.
- Introdurre linee guida sulla verbosità del logging e consolidare i test per
  i componenti condivisi (es. utilità di logging) con commenti esplicativi in
  italiano.
- Documentare la roadmap e aggiornare le directory chiave con README locali
  che descrivano il ruolo dei moduli.

## PR 2 – Commenti e docstring in italiano
- Aggiornare sistematicamente ogni modulo per includere docstring e commenti
  in italiano che spieghino cosa fa la funzione, come lo fa e perché.
- Assicurare che i messaggi di log e le eccezioni siano descrittivi e nella
  stessa lingua per favorire il debug da parte del team italiano.

## PR 3 – Copertura test completa *(in corso)*
- Creare o estendere i test in modo che ogni funzione individuata
  nell'inventario abbia almeno un caso base e test per i corner case.
- Rendere la pipeline di test verbosa, con fixture che tracciano passo passo
  la configurazione e i controlli effettuati.
- **Stato attuale:** moduli ``fair3.engine.utils.io``, ``.rand``, ``.psd`` e
  ``.log`` coperti con docstring/commenti italiani e test che validano edge
  case, rotazione dei file di log e riproducibilità dei generatori casuali.
  Il pacchetto ``fair3.engine.robustness`` è stato localizzato con README in
  italiano e test aggiuntivi che coprono bootstrap, scenari e ablation.
  L'ETL ``fair3.engine.etl`` è ora documentato in italiano e dispone di test
  granulari per calendario, pulizia serie, FX, QA e orchestrazione ``TRPanel``.

## PR 4 – Documentazione estesa
- Scrivere README specifici per ogni sottocartella descrivendo dati in input,
  artefatti prodotti e dipendenze.
- Aggiornare il README principale con una mappa di navigazione verso la nuova
  documentazione e includere esempi di configurazioni reali.

## PR 5 – Rifinitura e audit finale
- Riesaminare la coerenza stilistica (naming, formattazione, gestione errori)
  e uniformare eventuali discrepanze.
- Eseguire un audit finale del coverage e della CI assicurandosi che la
  pipeline sia autoesplicativa e pronta all'estensione.
