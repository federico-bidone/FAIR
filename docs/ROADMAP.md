# Roadmap GUI e automazione

La roadmap a medio termine per FAIR-III prevede le seguenti evoluzioni:

## Breve termine

- Rifinire i worker asincroni della GUI aggiungendo barra di progresso e
  notifica di completamento.
- Validare le credenziali direttamente dai provider quando possibile (ping API).
- Ampliare la copertura dei test con `pytest-qt` e snapshot sugli stylesheet.

## Medio termine

- Integrare un layer di theming completo (Carbon Design System) mantenendo la
  compatibilità con il file `tokens.json`.
- Portare i pannelli più dinamici su Qt Quick/QML per animazioni fluide e
  accelerazione GPU.
- Esporre hook per plugin di terze parti nella scheda Pipeline (pulsanti
  configurabili da YAML).

## Lungo termine

- Internationalizzazione dell'interfaccia (i18n) con file `.qm` caricabili.
- Telemetria opt-in basata su metriche aggregate scritte in `artifacts/logs/`.
- Playbook di distribuzione (packaging con `briefcase` o `PyInstaller`) per
  distribuire la GUI come applicazione desktop autonoma.
- Suite di regression test end-to-end con Playwright / browser embedding.
