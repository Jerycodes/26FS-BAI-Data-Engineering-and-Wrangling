# Archivierte Notebooks

Hier liegen Notebooks, die im Verlauf des Projekts entstanden sind, **aber im
finalen Stand nicht mehr Teil des aktiven Auswertungspfads** sind.

Sie sind absichtlich nicht gelöscht: sie dokumentieren Sackgassen,
Vorstufen und Methodik-Experimente. Bei der Bewertung ist nur der Inhalt
ausserhalb dieses Ordners massgeblich.

## Inhalt

| Datei | Warum archiviert |
|---|---|
| `Test_datenanalyse.ipynb` | Frühe Sammelfläche für webscraping-news-wrangling + MetaTrader-EDA + cross-source-comparison. Inhalt ist in den finalen Notebooks (`datenanalyse_forex.ipynb`, `news_forex_korrelation_kombiniert.ipynb`, `poc_webscraping_sentiment.ipynb`) sauber aufgeteilt enthalten. |
| `04_eda_news_webscraping.ipynb` | Ältere Parallel-Variante des Webscraping-EDA-Notebooks. Kanonische Version: `notebooks/rohdaten_laden/04_eda_news_webscraping.ipynb`. |
| `04_eda_news_webscraping_fenlin.ipynb` | Validierungs-Notebook für den feedparser-SSL-Fix (requests + feedparser). Der Fix ist in `src/data_loading/webscraping_loader.py` übernommen und dort im Docstring dokumentiert. |
| `05_merge_und_korrelation.ipynb` | Früher Stand der Merge-/Korrelationsanalyse (April 2026). Überholt durch `notebooks/datenverarbeitung/news_forex_korrelation_kombiniert.ipynb` und `sentiment_kurs_lead_lag_analyse.ipynb`. |
