# Architettura CLI

> Strumento informativo/didattico; non costituisce consulenza finanziaria o raccomandazione.

Il modulo CLI centralizza il comando argparse plumbing per ogni sottocomando FAIR-III.
I nuovi comandi devono rimanere additivi e retrocompatibili con v0.1, rispettare
`--dry-run`, `--progress/--no-progress` e `--json-logs/--no-json-logs` e
utilizzare le funzioni di supporto digitate definite nelmotori.

## Aggiunta di un comando
1. Implementare una funzione del motore con copertura completa della stringa di documenti e deterministico
   comportamento.
2. Estendi l'helper `_add_<feature>_subparser` con stringhe descrittive `help`
   ed esempi.
3. Collega il gestore all'interno del dispatcher nella parte inferiore di `main.py` e assicurati che
   I test di integrazione CLI coprano il nuovo punto di ingresso.

## Elenco di controllo dei test
- Aggiungi test unitari per l'analisi degli argomenti (utilizza`pytest` e `CliRunner` quando
  appropriato).
- Conferma che `pytest -q` e gli hook di pre-commit rimangono verdi su Windows 11.
- Aggiorna le guide `docs/` e il README principale con esempi di utilizzo e sfumature di licenza
   quando il comando tocca dati esterni.
