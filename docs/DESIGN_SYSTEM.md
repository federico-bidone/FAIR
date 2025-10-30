# Design system della GUI

La GUI di FAIR-III utilizza un approccio a design token definito in
`fair3/engine/gui/ui/tokens.json`. Questo file JSON rappresenta il punto di
partenza per future integrazioni con sistemi completi (es. Carbon o
Glassmorphism).

## Token disponibili

```json
{
  "color.primary": "#007AFF",
  "color.surface": "rgba(18, 20, 30, 0.92)",
  "color.text": "#EDEDED",
  "font.family": "Inter",
  "radius.small": 6,
  "radius.large": 12,
  "elevation.1": "0px 1px 3px rgba(0,0,0,0.4)"
}
```

`fair3.engine.gui.ui.theme.apply_tokens()` legge il file, genera uno stylesheet
QSS coerente e lo applica a `QApplication` all'avvio. L'obiettivo è mantenere il
codice pronto per una futura evoluzione verso un design system modulare:

- supporto a temi glassmorphism tramite overlay traslucidi;
- integrazione con token Carbon Design System quando sarà introdotto QML;
- centralizzazione di spaziature, tipografia e componenti comuni.

Gli sviluppatori possono sperimentare modificando `tokens.json`: la GUI aggiorna
automaticamente il tema al prossimo avvio senza necessità di ricompilare.
