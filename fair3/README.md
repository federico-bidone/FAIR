# Panoramica pacchetto fair3

> Strumento informativo/didattico; non costituisce consulenza finanziaria o raccomandazione.

Il pacchetto `fair3` implementa lo stack di ricerca di portafoglio FAIR-III.Ogni
modulo rispetta la Google Python Style Guide, espone punti di ingresso
tipizzati e riutilizzabili ed è richiamabile sia tramite cablaggio CLI che dal codice Python
 downstream.

## Layout
- `fair3/cli/`: registrazione dei comandi basata su argparse con valori predefiniti deterministici
  e registrazione di facile verifica.
- `fair3/engine/`: motori di dominio che coprono acquisizione, ETL, costruzione di fattori,
  stime, ottimizzazione, mappatura, rilevamento del regime, esecuzione, reporting, QA,
  robustezza e utilità.
- `fair3/configs/`: caricatori di configurazione runtime (non ancora parte dell'API pubblica
   inv0.2).

## Note del contributo
- Segui la struttura della stringa di documentazione PyGuide (`Args`, `Returns`, `Raises`,
  `Attributes`) e mantieni le importazioni raggruppate (stdlib, di terze parti, locale).
- Preferisci helper deterministici che accettano seed espliciti provenienti da
  `audit/seeds.yml`.
- Registra metadati, checksum e percorsi della licenza ogni volta che vengono prodotti nuovi artefatti
  in modo che la pipeline QA possa far emergere immediatamente le discrepanze.
