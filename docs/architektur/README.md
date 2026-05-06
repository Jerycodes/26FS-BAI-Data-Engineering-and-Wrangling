# Architekturgrafik

`pipeline.gv` enthält die Pipeline-Übersicht des Projekts in Graphviz-Notation.
Identisch mit der Workflow-Seite des Streamlit-Dashboards (`dashboard.py`),
plus der Lead/Lag-Pipeline (Notebook + Resultate-CSV), die nicht im Dashboard
sichtbar ist.

## Rendern

**Variante A — lokal mit Graphviz:**

```bash
brew install graphviz   # falls noch nicht vorhanden
dot -Tpng pipeline.gv -o pipeline.png
dot -Tsvg pipeline.gv -o pipeline.svg
```

**Variante B — online ohne Installation:**

`pipeline.gv`-Inhalt kopieren, einfügen unter
<https://dreampuf.github.io/GraphvizOnline/>, als PNG/SVG exportieren.

**Variante C — VS Code Extension:**

Extension "Graphviz (dot) language support for Visual Studio Code"
installieren, `pipeline.gv` öffnen, Vorschau anzeigen, Screenshot oder
Export.

## Verwendung im Bericht

Das gerenderte PNG/SVG kann direkt in `DOKUMENTATION.md` (Sektion 3
"Architektur der Datenpipeline") oder in den finalen Word-Bericht eingebunden
werden. Der Vorteil gegenüber dem interaktiven Dashboard-Element: das
Diagramm ist im PDF/Word-Druck statisch sichtbar, ohne dass der Leser die
Streamlit-App starten muss.
