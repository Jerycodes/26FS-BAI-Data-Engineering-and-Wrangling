# Projektdokumentation: Wechselkurse, Nachrichten-Sentiment und Ölpreise

**Modul:** Data Engineering & Wrangling, Studiengang Business Artificial Intelligence (BAI), Fachhochschule Nordwestschweiz (FHNW), Frühjahrssemester 2026
**Datenzeitraum im Projekt:** 2022-01-01 bis 2026-04-22
**Untersuchungsfokus:** EUR/USD, EUR/CHF, GBP/USD
**Stand des Dokuments:** 2026-06-08

> **Hinweis zum Lesen:** Dieses Dokument ist als **Protokoll** geschrieben. Es folgt der Reihe nach dem Weg der Daten — von der Quelle bis zur Antwort auf unsere Forschungsfrage — und begründet bei jedem Schritt, **warum** wir ihn so gemacht haben. Fachbegriffe und Abkürzungen werden beim ersten Auftreten ausgeschrieben.

---

## Inhaltlicher roter Faden

Die Verarbeitung folgt sechs Pflichtschritten des Moduls. Jeder Schritt hat ein eigenes Kapitel:

1. **Daten laden** (Kapitel 4) — Rohdaten aus den Quellen holen und unverändert ablegen.
2. **Datenbereinigung & Qualitätsprüfung** (Kapitel 5) — fehlende Werte, Duplikate, und ein Qualitätscheck, der einen echten Datierungsfehler aufdeckt.
3. **Harmonisierung** (Kapitel 6) — die Quellen auf ein gemeinsames Format und denselben Markttag bringen.
4. **Transformation & Feature Engineering** (Kapitel 7) — aus Rohdaten analysefähige Grössen bauen (Renditen, Tages-Sentiment, Aggregate).
5. **Sentiment-Analyse** (Kapitel 8) — Stimmung aus Nachrichtentexten messen, auf drei Wegen zur Absicherung.
6. **Analyse & Antwort** (Kapitel 9) — die Forschungsfrage mit einer Lead/Lag-Analyse beantworten.

Kapitel 1–3 erklären Ziel, Quellen und Pipeline; Kapitel 10–15 behandeln Dashboard, Reproduzierbarkeit, Grenzen, Struktur und Entscheidungs-Chronologie.

---

## 1. Worum geht es? Ziel und Forschungsfrage

### 1.1 Die Frage

Das Projekt untersucht, ob die **Stimmung in Finanznachrichten** (das sogenannte *Sentiment*) einen erkennbaren Zusammenhang mit **Wechselkursen** hat — und falls ja, ob die Stimmung der Kursbewegung **vorausläuft**.

> **Forschungsfrage:** *Hat das Sentiment von Finanznachrichten einen Einfluss auf Währungskurse — und wenn ja, mit welcher zeitlichen Verzögerung?*

Wir konkretisieren die Frage in eine **Lead/Lag-Frage** (englisch *lead* = Vorlauf, *lag* = Nachlauf). Dazu vergleichen wir das Sentiment an einem Tag mit der Kursveränderung *k* Tage später:

- **Hypothese H1 — Sentiment führt:** Das Sentiment am Tag *t* sagt die Kursveränderung am Tag *t + k* für ein *k > 0* vorher. Negative Nachrichten heute → fallender Kurs in den Folgetagen. (Das ist die Hypothese, die wir gerne bestätigt sähen.)
- **Alternative A1 — gleichzeitig:** Sentiment und Kurs bewegen sich **am selben Tag** (*k = 0*). Das Sentiment ist dann eine Begleitinformation, kein Vorlauf.
- **Alternative A2 — Markt führt:** Der Kurs bewegt sich zuerst, die Nachrichten reagieren nach (*k < 0*).

Die Antwort steht in Kapitel 9.

### 1.2 Wie der Dozent das Projekt rahmt

Bewertet wird **nicht** ein Prognosemodell, sondern der **Umgang mit unsauberen Daten**: aus heterogenen Quellen vergleichbare Reihen bauen, Qualitätsprobleme erkennen und dokumentieren, und Methodenentscheidungen begründen. Die Antwort auf die Forschungsfrage ist ein Anwendungsbeispiel — das eigentliche Produkt ist die **Datenaufbereitung**.

### 1.3 Was das Projekt *nicht* ist

- Kein Handelssystem und kein Backtesting (rückwirkendes Durchtesten einer Handelsstrategie).
- Kein Modell des maschinellen Lernens.
- **Keine Kausalaussage.** Wir messen einen statistischen Zusammenhang über die Zeit, nicht „Sentiment *verursacht* Kursbewegung". Ein formaler Kausalitätstest (Granger-Test) ist als Erweiterung vermerkt, aber bewusst nicht Teil der Kernaussage (siehe Kapitel 9.6).

---

## 2. Die Datenquellen — woher kommen die Daten?

Wir integrieren **bewusst mehrere Quellen pro Datentyp**. Grund: Nur mit mehreren Quellen lassen sich Unstimmigkeiten überhaupt aufdecken (eine einzelne Quelle kann man nicht gegenprüfen), und man wird nicht von einem Anbieter abhängig. Genau dieser Cross-Check hat in diesem Projekt einen echten Datenfehler sichtbar gemacht (Kapitel 5.3).

| Datentyp | Quelle | Zugang | Historie im Projekt |
|---|---|---|---|
| Wechselkurs | Yahoo Finance | Python-Bibliothek `yfinance` (kein Login nötig) | 2022-01-03 – 2026-04-21 |
| Wechselkurs | EODHD | REST-Programmierschnittstelle (API) mit Schlüssel | 2022-01-02 – 2026-04-22 |
| Wechselkurs | MetaTrader 5 | Manuelle CSV-Exporte (Tages- und 15-Minuten-Daten) | 2022-01-03 – 2025-12-26 |
| Nachrichten | EODHD | REST-API, mit bereits berechnetem Sentiment-Wert | 2022-01 – 2026-04 |
| Nachrichten | RSS-Feeds (ForexLive, FXStreet, Yahoo Finance, Google News, DailyFX) | `requests` + `feedparser` | Scrape-Momentaufnahmen 2024-09 / ab 2025-09 |
| Nachrichten | Reddit (r/Forex, r/investing, r/economics) | öffentlicher JSON-Endpunkt | gleiches Fenster wie RSS |
| Ölpreis | Yahoo Finance (WTI `CL=F`, Brent `BZ=F`) | `yfinance` | 2022-01-03 – 2026-04-21 |

**Begriffe:**
- **Forex** = *Foreign Exchange*, der Devisenmarkt (Handel mit Währungen).
- **EODHD** = *End-of-Day Historical Data*, ein kommerzieller Finanzdaten-Anbieter.
- **REST-API** = *Representational State Transfer – Application Programming Interface*, eine Programmierschnittstelle, die Daten über Web-Adressen (URLs) ausliefert.
- **RSS** = *Really Simple Syndication*, ein standardisiertes Nachrichten-Feed-Format.
- **WTI / Brent** = zwei weltweite Referenz-Rohölsorten (West Texas Intermediate bzw. Brent).

### 2.1 Warum diese Kombination?

- **Yahoo Finance + EODHD** — zwei unabhängige, öffentlich zugängliche Wechselkurs-Anbieter. Yahoo ist kostenlos; EODHD liefert zusätzlich Sonntagsdaten (der globale Devisenmarkt öffnet Sonntagabend in Asien) und bringt das Nachrichten-Feed inklusive vorberechneter Sentiment-Werte mit. So sind Datenvergleich und Cross-Check möglich.
- **MetaTrader 5** — Daten aus einer brokernahen Handelsplattform, die als technische Referenz dienen. Werden hier nur für den **Quellenvergleich** (Kapitel 5.3) genutzt, weil sie nur lokal exportierbar sind und der Export bis 2025-12-26 reicht.
- **EODHD-Nachrichten** — bereits mit einem Sentiment-Wert pro Artikel versehen → schneller Einstieg und eine Referenz für unsere eigene Sentiment-Berechnung.
- **RSS + Reddit** — eine zweite, unabhängige Nachrichtenquelle als Machbarkeitsnachweis (englisch *Proof of Concept*, Kapitel 8.3). Rohe Texte ohne vorberechnete Werte.
- **Öl (WTI + Brent)** — ein häufig genannter makroökonomischer Einflussfaktor auf Rohstoff- und Petrowährungen. Dient im Dashboard als zuschaltbare Vergleichsreihe.

---

## 3. Die Pipeline im Überblick

Die Daten durchlaufen drei klar getrennte Schichten. Diese Trennung ist das Rückgrat der Reproduzierbarkeit:

![Pipeline-Diagramm](docs/architektur/pipeline.png)

1. **`data/raw/`** — die **unveränderten Rohdaten**, genau so, wie sie aus den Quellen kommen. Jede Datei trägt Quelle und Datum im Dateinamen. Nach dem Laden wird hier nichts mehr verändert. Diese Schicht ist unsere „Ground Truth": Wenn ein späterer Schritt fragwürdig ist, können wir immer auf das Original zurück.
2. **`data/processed/`** — die **bereinigten, harmonisierten und zusammengeführten** Zwischenergebnisse. Erzeugt durch die Skripte in `scripts/` (oder die zugehörigen Notebooks).
3. **`data/final/`** — fertige Datensätze, die direkt in Bericht oder Dashboard einfliessen.

**Reproduzierbarkeit:** Jeder Schritt lässt sich mit einem einzigen Befehl neu ausführen (Kapitel 11). Die Skripte sind *idempotent* — mehrfaches Ausführen führt zum selben Ergebnis.

Das Pipeline-Diagramm liegt als Graphviz-Quelle (`docs/architektur/pipeline.gv`) sowie als PNG und SVG vor und ist im Dashboard unter der Seite „Workflow" interaktiv erreichbar.

---

## 4. Schritt 1 — Laden der Rohdaten

Jede Quelle hat ein eigenes Lade-Skript (`src/data_loading/`). Alle folgen demselben Muster: Daten holen → unverändert nach `data/raw/` schreiben. Bewusst findet hier **keine** Bereinigung statt — das gehört in den nächsten Schritt, damit das Rohmaterial erhalten bleibt.

| Quelle | Skript | Wie genau geladen wird |
|---|---|---|
| Yahoo-Wechselkurse | `yahoo_loader.py` | `yfinance` lädt die Symbole `EURUSD=X`, `EURCHF=X`, `GBPUSD=X` als Tages-Kerzen. Kein Login. |
| EODHD-Wechselkurse | `eodhd_loader.py` | REST-Aufruf `https://eodhd.com/api/eod/{Symbol}` mit `period=d` (täglich); Symbole `EURUSD.FOREX` usw. API-Schlüssel aus `.env`. |
| EODHD-Nachrichten | `eodhd_news_loader.py` | REST-Aufruf `https://eodhd.com/api/news`; Blätter-Logik (*Pagination*) mit `limit=1000`, um die Zahl der Aufrufe klein zu halten. Speichert Roh-JSON **und** verarbeitetes CSV. |
| Webscraping | `webscraping_loader.py` | RSS-Feeds und Reddit-JSON. Holt den Inhalt zuerst mit `requests`, übergibt den Text dann an `feedparser` (siehe SSL-Hinweis unten). |
| Ölpreise | `oil_loader.py` | `yfinance` lädt `CL=F` (WTI) und `BZ=F` (Brent) als Tagesdaten. |

**Begriffe:**
- **OHLC** = *Open, High, Low, Close* — Eröffnungs-, Höchst-, Tiefst- und Schlusskurs eines Tages (eine „Kerze").
- **JSON** = *JavaScript Object Notation*, ein verschachteltes Textformat; **CSV** = *Comma-Separated Values*, eine flache Tabelle.

**Wichtige Lade-Details, die später relevant werden:**
- Die EODHD-Nachrichten kommen mit einem verschachtelten Sentiment-Objekt. Der Loader flacht es mit `pandas.json_normalize()` in eigene Spalten auf (`polarity`, `neg`, `neu`, `pos`). Artikel ohne Sentiment behalten den fehlenden Wert (`NaN`, siehe Kapitel 5.1) — sie werden **nicht** gelöscht.
- Beim Webscraping trat auf macOS ein Zertifikatsfehler auf (`feedparser.parse(url)` schlug mit SSL-Fehler fehl). Lösung: den Feed-Inhalt erst mit `requests` (das die Zertifikate von `certifi` nutzt) holen und den Text an `feedparser.parse(text)` geben. Dieser Befund ist ein typisches Beispiel für den iterativen Umgang mit Datenquellen: **erkannt → Ursache benannt → behoben → dokumentiert.**

Der Reihenfolge-Befehl zum Neuladen steht in Kapitel 11. **Achtung:** EODHD hat im kostenlosen Tarif ein Tageslimit (20 Aufrufe pro Tag, Nachrichten zählen 5 pro Symbol). Lade-Skripte deshalb nur bewusst ausführen.

---

## 5. Schritt 2 — Datenbereinigung und Qualitätsprüfung

Dieser Schritt entscheidet, welche Lücken wir füllen, welche wir bewusst offen lassen, welche Duplikate wir entfernen — und er enthält den wichtigsten Qualitätsbefund des Projekts (Kapitel 5.3).

### 5.1 Umgang mit fehlenden Werten

Leitprinzip: **Nur dort auffüllen, wo die Lücke rein technisch entsteht — nicht dort, wo das Fehlen selbst eine Information ist.**

Ein fehlender Wert heisst in der Tabellen-Bibliothek `pandas` **`NaN`** (*Not a Number*).

**Wechselkurse — Wochenenden und Feiertage:**
- **Samstag:** fehlt bei allen Quellen, weil der Devisenmarkt weltweit geschlossen ist. → nicht auffüllen, das ist erwartet.
- **Sonntag:** EODHD liefert Werte (Marktöffnung in Asien ab Sonntagabend), Yahoo und MetaTrader nicht. → vorhandene Sonntagswerte **behalten**, weil sie reale Marktdaten sind.
- **Feiertage** (z. B. Neujahr, Karfreitag): teils fehlend. → **nicht** interpoliert (rechnerisch aufgefüllt), weil der Markt an diesem Tag den Wert nicht hergegeben hat. In der kombinierten Tabelle markiert die Spalte `has_gap`, dass an einem Tag eine Quelle fehlt.

**Warum keine pauschale Interpolation der Kurse?** *Interpolation* heisst, fehlende Werte aus den Nachbarwerten zu schätzen (z. B. linear). Für Kurse wäre das ein erfundener Handelstag. Wir bieten Interpolation deshalb nur als **Anzeige-Option im Dashboard** an (Kapitel 7.4), die nichts in die Rohdaten zurückschreibt.

**Nachrichten-Sentiment — Tage ohne Artikel:**
- Liegt an einem Tag **kein Artikel** vor (typisch an Wochenenden, Feiertagen, nachrichtenarmen Tagen), bleibt das Sentiment **`NaN`** — und wird **nirgends** aufgefüllt.
- **Begründung (Theorie-Bezug):** Die Vorlesung Woche 2 unterscheidet drei Arten fehlender Werte:
  - **MCAR** (*Missing Completely At Random*) — rein zufällig fehlend.
  - **MAR** (*Missing At Random*) — fehlend abhängig von *anderen* beobachteten Werten.
  - **MNAR** (*Missing Not At Random*) — fehlend abhängig vom *fehlenden Wert selbst*.

  Tage ohne Artikel sind **MNAR**: Ob ein Artikel existiert, hängt direkt davon ab, ob etwas berichtenswert passiert ist. „Kein Artikel" bedeutet inhaltlich **nicht** „neutraler Tag mit Sentiment 0". Würde man die Lücke mit 0 oder mit dem Nachbarwert füllen, täuschte man eine Nachrichtenlage vor, die es nicht gab — eine strukturelle Verzerrung. Deshalb: bewusst `NaN` lassen.
- Bei der Aggregation auf Wochen/Monate ignoriert `pandas` `NaN` automatisch, d. h. eine Woche mit nur 2 statt 5 Nachrichtentagen wird trotzdem aggregiert — eben auf Basis der vorhandenen Tage.

**Sonderfall EUR/CHF-Nachrichten:** Die EODHD-Nachrichten-Abdeckung für EUR/CHF ist **extrem dünn** (rund 13 Artikel im gesamten Zeitraum), weil dieses Paar international wenig Medienaufmerksamkeit bekommt. Wir führen für EUR/CHF deshalb **keine** belastbare Sentiment-Korrelation durch und sagen das im Bericht offen.

### 5.2 Umgang mit Duplikaten

**Wechselkurse:** Doppelte Datums-Einträge je Quelle entfernen wir mit „erstes behalten" (`keep="first"`). Ursache sind meist zeitzonenbedingte Mehrfacheinträge. **Inhaltliche** Duplikate (zufällig gleiche OHLC-Werte an verschiedenen Tagen) entfernen wir **nicht** — die können in ruhigen Marktphasen echt sein.

**Nachrichten (Webscraping):** Derselbe Artikel taucht in aufeinanderfolgenden Scrape-Momentaufnahmen mehrfach auf. Wir deduplizieren auf der eindeutigen Adresse (`link`), nicht auf dem Titel — denn RSS-Feeds liefern denselben Artikel manchmal mit leicht abweichendem Titel.

**Reddit:** Ein Beitrag kann gleichzeitig in „hot" und „new" stehen. Der Loader entfernt solche Doppel direkt nach dem Scrapen (über `link`).

### 5.3 Qualitätsprüfung über Quellen hinweg — der zentrale Befund

Mehrere Quellen sind nur dann ein Gewinn, wenn man sie **gegeneinander prüft**. Wir haben einen einfachen, aber wirkungsvollen Test gemacht:

> **Sanity-Check:** Zwei Anbieter desselben Wechselkurses müssen sich auf **Tagesrenditen** fast perfekt ähneln (Korrelation nahe 1.0). Tun sie das nicht, stimmt etwas mit der Ausrichtung oder den Werten nicht.

Das Ergebnis war alarmierend:

| Paar | Tagesrendite-Korrelation Yahoo ↔ EODHD (gleicher Tag) | mittlere Tagesdifferenz |
|---|---|---|
| EUR/CHF | **0.92** (in Ordnung) | ~2 Pips |
| EUR/USD | **0.03** (kaputt) | ~42 Pips |
| GBP/USD | **0.03** (kaputt) | ~50 Pips |

Ein *Pip* ist die kleinste übliche Kursbewegung (vierte Nachkommastelle). Zwei echte EUR/USD-Feeds dürften sich am selben Tag niemals um 42 Pips unterscheiden und müssten auf Renditen ~0.99 korrelieren — nicht 0.03.

**Diagnose:** Verschiebt man die EODHD-Reihe um **genau einen Kalendertag**, springt die Korrelation auf 0.66–0.99. Das heisst: Die EODHD-Tagesreihen waren für EUR/USD und GBP/USD **um einen Tag gegenüber Yahoo verschoben** (für EUR/CHF nicht).

**Ursache:** Zwei Konventionsunterschiede treffen zusammen:
1. **Yahoo** stempelt seine Tagesbalken gemischt auf `23:00` oder `00:00` UTC (*Coordinated Universal Time*, die koordinierte Weltzeit). Das ist ein bekanntes Sommerzeit-Artefakt der `yfinance`-Bibliothek: derselbe Handelstag erscheint mal als „Sonntag 23:00", mal als „Montag 00:00".
2. **EODHD** führt den Sonntags-Eröffnungsbalken und labelt ihn je nach Paar anders.

In Summe ist die EODHD-Reihe bei zwei Paaren um einen Tag versetzt.

**Warum das gefährlich war:** Unsere Analyse mittelt die Quellen pro Tag (Kapitel 7.3). Mittelt man zwei um einen Tag versetzte Reihen, mischt man **zwei verschiedene Markttage** zu einem Wert — die resultierenden Renditen sind teils Unsinn. Genau auf diesen Renditen beruht aber die Lead/Lag-Analyse.

**Wichtige Einordnung (Niveau der Differenz):** Dass sich Quellen *etwas* unterscheiden, ist bei Forex **normal und erwartet** — der Devisenmarkt ist dezentral (*over-the-counter*), es gibt keinen einen „offiziellen" Kurs; jeder Handelsplatz quotiert minimal anders. Genau dafür ist ein **Mittelwert** das richtige Werkzeug. Der Punkt ist die **Grössenordnung**: EUR/CHF unterscheidet sich um ~2 Pips (echte Anbieter-Streuung), EUR/USD aber um ~42 Pips — das **20-Fache**. So weit driften zwei echte Feeds nicht auseinander; das war ein **Datierungsfehler**, kein Anbieterrauschen. Nach Ausrichtung schrumpft die Differenz auf ~12 bzw. ~1 Pip — also auf dasselbe kleine Niveau wie EUR/CHF.

**Die Behebung (Kapitel 6.2):** Wir richten jede Nicht-Yahoo-Quelle **datengetrieben** an Yahoo aus (wir wählen den Versatz, der die Rendite-Korrelation maximiert), **bevor** wir mitteln. Der Mittelwert bleibt also unser Werkzeug — er wird nur auf korrekt ausgerichtete Reihen angewandt. Als Nebenbefund war auch MetaTrader bei EUR/USD um einen Tag versetzt; nach Ausrichtung korreliert es mit 0.98 zu Yahoo (starke gegenseitige Bestätigung).

> **Lehrwert:** Dieser Befund ist das Herzstück unserer Qualitätsprüfung. Erst der Cross-Check zwischen Quellen hat einen Fehler sichtbar gemacht, den keine einzelne Quelle je gezeigt hätte. Genau dafür haben wir mehrere Quellen integriert.

---

## 6. Schritt 3 — Harmonisierung

Ziel: Alle Quellen so aufbereiten, dass sie **dasselbe Schema** und **denselben Markttag** sprechen, damit ein Vergleich überhaupt möglich ist.

### 6.1 Die drei Dimensionen der Heterogenität

Die Vorlesung Woche 4 unterscheidet drei Ebenen, an denen sich Quellen unterscheiden. Wir richten uns explizit daran aus:

| Dimension | Ausgangslage | Unsere Harmonisierung |
|---|---|---|
| **Syntax** (Format) | CSV, JSON, Tab-getrennt (MetaTrader) | alles über `pandas` in einheitliche Tabellen |
| **Syntax** (Zeitzone) | Yahoo gemischt UTC, EODHD ortsbezogen, MetaTrader Broker-Zeit | alles auf zeitzonenlose Tagesebene gebracht |
| **Syntax** (Datumsformat) | ISO-Strings, `YYYY.MM.DD` (MetaTrader), Epochensekunden (Reddit) | mit `pandas.to_datetime(...)` in echte Zeitstempel |
| **Struktur** (Spaltennamen) | `Open/High/Low/Close` (Yahoo), `open/...` (EODHD), `<OPEN>/...` (MetaTrader) | alles auf kleingeschriebene `open/high/low/close` |
| **Struktur** (Nachrichtenfelder) | Sentiment als verschachteltes Objekt (EODHD) vs. kein Sentiment (RSS) | `json_normalize()` flacht das EODHD-Objekt in Spalten auf |
| **Semantik** (Bedeutung) | Schreibweise der Paare: `EURUSD=X`, `EURUSD.FOREX`, `EURUSD` | intern einheitlich `EUR_USD`, `EUR_CHF`, `GBP_USD` |
| **Semantik** (Markttag) | gleicher Kalendertag ≠ gleicher Markttag (Kapitel 5.3) | **datengetriebene Datums-Ausrichtung** (siehe 6.2) |

Diese Harmonisierung ist **retrospektiv** (sie passiert *nach* der Erhebung, weil wir die Quellsysteme nicht kontrollieren) — laut Vorlesung die häufigste Form in der Praxis, die aber die erreichbare Datenqualität begrenzt.

### 6.2 Die Datums-Ausrichtung (Semantik des Markttags)

Die letzte Zeile der Tabelle ist der entscheidende Schritt aus Kapitel 5.3. Das Skript `scripts/regenerate_forex_combined.py` macht ihn so:

1. **Referenz festlegen:** Yahoo dient als Zeit-Referenz (seine `23:00/00:00`-Stempel werden mit `ceil("D")` sauber auf den nächsten Tag gerundet, was die Mischung korrekt auflöst).
2. **Versatz messen:** Für jede andere Quelle (EODHD, MetaTrader) wird der Datums-Versatz von −2 bis +2 Tagen gesucht, der die **Tagesrendite-Korrelation** mit Yahoo maximiert.
3. **Schutz gegen Schein-Verschiebungen:** Ein Versatz wird nur angewandt, wenn er die Korrelation um mindestens 0.15 verbessert. So bleibt EUR/CHF (bereits ausgerichtet) unangetastet, während EUR/USD und GBP/USD um +1 Tag korrigiert werden.
4. **Protokollierung:** Das Skript gibt den gewählten Versatz und die Korrelation davor/danach aus — die Entscheidung ist also nachvollziehbar.

Erst **nach** dieser Ausrichtung werden die Quellen kombiniert und gemittelt.

Der harmonisierte Wechselkurs-Datensatz liegt in `data/processed/forex/forex_alle_quellen_kombiniert.csv` im **Langformat**: eine Zeile pro Tag-und-Paar, mit Spalten `yahoo_close`, `eodhd_close`, `metatrader_close` nebeneinander, plus `weekday`, `is_weekend`, `n_sources` (wie viele Quellen an dem Tag einen Wert haben) und `has_gap`.

---

## 7. Schritt 4 — Transformation und Feature Engineering

Hier bauen wir aus den bereinigten Rohdaten die Grössen, mit denen die Analyse rechnet.

### 7.1 Tages-Sentiment aus vielen Artikeln — warum Median statt Mittelwert

An einem Tag gibt es oft mehrere Artikel mit je einem Sentiment-Wert. Wir fassen sie pro Tag zum **Median** zusammen (der mittlere Wert), nicht zum arithmetischen Mittel.

**Begründung (Theorie-Bezug):** Die Vorlesung Woche 3 empfiehlt für ausreisseranfällige Daten den `RobustScaler`, der bewusst **Median und Interquartilsabstand** (englisch *Interquartile Range*, IQR — der Abstand zwischen dem 25-%- und dem 75-%-Wert) nutzt, weil „Ausreisser Median und IQR kaum beeinflussen". Dieselbe Logik gilt hier: Ein einzelner extrem formulierter Artikel (Sentiment ±1.0) verzieht das **Mittel** stark, den **Median** kaum. Da die Sentiment-Werte stark bei 0 gehäuft sind und vereinzelt Extremwerte haben, ist der Median die robustere Wahl.

### 7.2 Renditen statt Kurs-Niveaus — warum

Für die Analyse verwenden wir nicht den Kurs selbst, sondern seine **Tagesrendite** als **logarithmische Rendite**: *r_t = ln(P_t) − ln(P_{t−1})*.

**Begründung:**
- **Stationarität:** Kurs-Niveaus haben langfristige Trends (sie sind *nicht-stationär*). Eine Korrelation auf Niveaus misst vor allem Trend-Übereinstimmung, nicht die Reaktion auf Nachrichten. Renditen sind annähernd stationär.
- **Symmetrie:** Logarithmische Renditen behandeln Anstieg und Abfall symmetrisch.
- Dieser Punkt ist zentral für die richtige Deutung der Dashboard-Grafiken (Kapitel 9.4): Auf **Niveaus** sieht ein gemeinsamer Trend wie ein Vorlauf aus; erst auf **Renditen** trennt sich „bewegt sich gemeinsam" von „sagt vorher".

### 7.3 Mittelwert über die Quellen — warum (und wann er gültig ist)

Wo mehrere Quellen einen Kurs liefern, bilden wir den **Mittelwert** (nur über die an dem Tag vorhandenen Quellen). Grund: Forex hat keinen einen „wahren" Kurs (Kapitel 5.3); der Mittelwert glättet die kleine, normale Anbieter-Streuung und ist robuster als eine willkürlich gewählte Einzelquelle.

**Wichtig:** Dieser Mittelwert ist nur sinnvoll, **nachdem** die Quellen auf denselben Markttag ausgerichtet sind (Kapitel 6.2). Vorher hätte er zwei verschiedene Tage gemischt. Gegenprobe: Die Lead/Lag-Ergebnisse mit dem ausgerichteten Mittel (r ≈ 0.18 / 0.21) stimmen praktisch mit denen einer sauberen Einzelquelle (nur Yahoo: 0.20 / 0.21) überein — der Mittelwert ist nach der Ausrichtung also robust.

### 7.4 Aggregation, Interpolation und Normalisierung (Dashboard-Optionen)

- **Aggregation auf Woche/Monat/Quartal:** über `pandas.resample` mit wählbarer Funktion. Fehlende Tage werden **nicht** vorher gefüllt — `resample` ignoriert `NaN`.
- **Interpolation (optional):** ein Dashboard-Schalter „Fehlende Tage interpolieren (linear)". Er wirkt **nur** auf Kurs- und Ölreihen, **nie** auf Sentiment (Begründung MNAR, Kapitel 5.1), und schreibt nichts in die Rohdaten zurück — er verändert nur die Anzeige. So bleibt die Rohdaten-Integrität gewahrt. In der Analyse dient die interpolierte Variante als **Sensitivitätscheck** (Kapitel 9.5).
- **Normalisierung (Index = 100):** teilt jede Reihe durch ihren ersten gültigen Wert und mal 100. So werden Reihen mit sehr unterschiedlichen Skalen (Kurs ~1.1, Öl ~80, Sentiment ~0.1) optisch vergleichbar.

### 7.5 MetaTrader 15-Minuten → Tagesdaten (eine Validierung)

Die 15-Minuten-Daten von MetaTrader werden auf Tagesbasis verdichtet (Eröffnung = erster Wert, Hoch = Maximum, Tief = Minimum, Schluss = letzter Wert). **Kontrolle:** Die so aggregierten Tageswerte stimmen exakt (100 %) mit dem separat gelieferten MetaTrader-Tagesexport überein — ein Beleg, dass unsere Aggregationslogik korrekt ist.

---

## 8. Schritt 5 — Sentiment-Analyse auf drei Wegen

Wir berechnen die Stimmung auf **drei unterschiedliche Arten**, damit sichtbar wird, wie stark das Ergebnis von der Methode abhängt.

### 8.1 Weg 1 — EODHD-Sentiment (vorberechnet)

EODHD liefert pro Artikel bereits einen *Polarity*-Wert (Stimmungswert) zwischen −1 (negativ) und +1 (positiv). Die Methode ist nicht öffentlich dokumentiert, wir behandeln sie als „Black Box" (undurchsichtiges Verfahren). Einsatz: die saubere Methodik-Referenz im Dashboard (Seite „Master Grafik").

### 8.2 Weg 2 — Eigene TextBlob-Analyse auf demselben EODHD-Text

Wir nehmen **denselben** Artikeltext (Titel + Inhalt) und lassen die Python-Bibliothek **TextBlob** den Stimmungswert berechnen. Den Vergleich (eigene Berechnung vs. EODHD-Wert) zeigt das Dashboard auf der Seite „Sentiment-Vergleich". Zweck: einschätzen, wie nah ein einfaches, transparentes Verfahren an den undurchsichtigen EODHD-Wert herankommt.

### 8.3 Weg 3 — TextBlob auf den Webscraping-Texten (Machbarkeitsnachweis)

Titel und Zusammenfassung der gescrapten RSS-/Reddit-Artikel gehen in TextBlob; pro Tag bilden wir wieder den Median. Einsatz: der „Proof of Concept" (Kapitel 10). Idee: Wenn ein Zusammenhang **auch** mit einer ganz anderen Nachrichtenquelle und Methode auftaucht, ist er robuster.

### 8.4 Was man über TextBlob wissen muss

- TextBlob ist **lexikonbasiert** (es schlägt Wörter in einem Wörterbuch nach) und auf Allgemeinsprache trainiert. Für **finanzspezifische** Texte liefert es regelmässig den Wert 0 („neutral", weil das Fachvokabular im Lexikon schwach vertreten ist) — in unseren Daten bei rund einem Drittel der Artikel.
- **Warum trotzdem TextBlob?** Es ist transparent, nachvollziehbar und reproduzierbar — im Bildungskontext wichtiger als ein leistungsstärkeres, aber undurchsichtiges Modell. Eine sinnvolle Erweiterung wären finanzspezifische Verfahren (FinBERT oder VADER mit dem Loughran-McDonald-Finanzlexikon); siehe Kapitel 12.

**Abdeckung der Webscraping-Daten — ehrlich beziffert:** Die gescrapten Nachrichten umfassen **127 Tage**. Davon stammt **ein einziger** Tag aus dem September 2024; die eigentliche Abdeckung beginnt erst im **September 2025** und reicht bis April 2026. An **60 von 127 Tagen** liegt nur ein einziger Artikel vor (Median: 2 Artikel/Tag). Diese dünne und zeitlich konzentrierte Abdeckung ist der Grund, warum der Webscraping-Weg nur als Machbarkeitsnachweis dient, nicht als belastbarer Beleg.

---

## 9. Schritt 6 — Analyse und Antwort auf die Forschungsfrage

### 9.1 Methode

Wir messen die **Kreuzkorrelation** zwischen dem Sentiment am Tag *t* und der Kursrendite am Tag *t + k*, für *k* von −10 bis +10:

> *ρ_k = Korrelation( Sentiment_t , Rendite_{t+k} )*

- *k > 0*: Sentiment führt die Kursrendite (= unsere Hypothese H1).
- *k = 0*: gleichzeitige Bewegung.
- *k < 0*: der Kurs führt das Sentiment.

**Einheit der Verzögerung — Kalendertage:** Die Reihen werden auf tägliche **Kalenderfrequenz** gebracht; der Lag *k* zählt also **Kalendertage**, nicht Handelstage. An Wochenenden ohne Kurs entstehen `NaN`-Renditen, die bei der Korrelation paarweise entfallen.

**Signifikanz:** Unter der Annahme „kein Zusammenhang" (ρ = 0) liegt das 95-%-Konfidenzband bei etwa ±1.96/√n (n = Anzahl gemeinsamer Tage). Werte **innerhalb** des Bandes sind statistisch nicht von Null zu unterscheiden.

**Mehrfachtests:** Wir prüfen 21 Verzögerungen gleichzeitig. Bei so vielen Tests findet man leicht zufällig einen „Treffer". Eine strenge Korrektur (Bonferroni) weitet das Band für 21 zweiseitige Tests auf etwa ±3.0/√n. Da benachbarte Verzögerungen aber stark zusammenhängen (autokorreliert sind), ist die effektive Zahl unabhängiger Tests kleiner — die Wahrheit liegt zwischen ±1.96 und ±3.0/√n. Wir nennen beide Grenzen, wo es darauf ankommt.

Wir rechnen die Analyse **parallel** auf zwei Wegen (sauber = EODHD; dirty = Webscraping) und jeweils mit/ohne Kurs-Interpolation als Sensitivitätscheck.

### 9.2 Ergebnis-Tabelle

Reproduzierbar in `data/processed/news/lead_lag_results.csv`. „r am Maximum" ist die stärkste Korrelation über alle Verzögerungen (mit Vorzeichen), „r bei k=0" die gleichzeitige Korrelation.

| Paar | Weg | Interp. | bestes k | r am Maximum | r bei k=0 | n | ±Band 95 % |
|---|---|---|---:|---:|---:|---:|---:|
| EUR/USD | sauber (EODHD) | nein | **0** | **+0.18** | +0.18 | 988 | ±0.06 |
| EUR/USD | sauber (EODHD) | ja | 0 | +0.11 | +0.11 | 1432 | ±0.05 |
| GBP/USD | sauber (EODHD) | nein | **0** | **+0.21** | +0.21 | 959 | ±0.06 |
| GBP/USD | sauber (EODHD) | ja | 0 | +0.16 | +0.16 | 1401 | ±0.05 |
| EUR/CHF | sauber (EODHD) | nein | 2 | −0.76 | +0.04 | **7** | ±0.74 |
| EUR/CHF | sauber (EODHD) | ja | −4 | +0.66 | −0.08 | 10 | ±0.62 |
| EUR/USD | dirty (Webscraping) | nein | 9 | −0.28 | −0.00 | 85 | ±0.21 |
| GBP/USD | dirty (Webscraping) | nein | −4 | −0.15 | −0.09 | 85 | ±0.21 |
| EUR/CHF | dirty (Webscraping) | nein | 5 | +0.30 | −0.01 | 85 | ±0.21 |

### 9.3 Antwort auf die Forschungsfrage

**Sauberer Weg, EUR/USD und GBP/USD:** Das Maximum der Kreuzkorrelation liegt **eindeutig bei k = 0**, mit r ≈ +0.18 bis +0.21. Bei n ≈ 1000 ist das Band ±0.06 — die Korrelation ist also klar statistisch gesichert, **aber sie ist gleichzeitig**. Für |k| > 0 fällt der Wert unter das Band.

> **Antwort:** **H1 (Sentiment führt den Kurs) wird nicht gestützt.** Das Ergebnis passt zu **A1 (gleichzeitige Bewegung)**: Sentiment und Kurs reagieren auf dieselben Marktinformationen, ohne dass eine Reihe der anderen vorausläuft. Das Sentiment ist hier **Begleitinformation, kein Prognoseinstrument.**

**Sauberer Weg, EUR/CHF:** r = −0.76 bei k = 2 klingt stark, beruht aber auf **n = 7** Tagen (Band ±0.74). Das ist das Lehrbeispiel **„Effektgrösse ohne Stichprobengrösse ist wertlos"** — statistisch nicht von Null zu unterscheiden. Wir führen es als negative Evidenz der dünnen EODHD-Abdeckung auf, nicht als Ergebnis über das Paar.

**Dirty Weg (Webscraping):** Die Maxima liegen bei wechselnden Verzögerungen (k = 9, −4, 5), aber alle nahe oder innerhalb des Bandes ±0.21, bei nur n = 85. Nach Mehrfachtest-Korrektur ist nichts davon robust. → **nicht entscheidbar.** Das ist angesichts der dünnen Abdeckung (Kapitel 8.4) erwartbar.

### 9.4 Warum die Grafik einen Vorlauf suggeriert — die Analyse aber nicht

Im Dashboard kann der Eindruck entstehen, das Sentiment *führe* den Kurs („Sentiment runter, dann Kurs runter"). Wir haben das gezielt geprüft, weil es genau die Hypothese stützen würde. Ergebnis auf mehreren Ebenen:

| Ebene | EUR/USD | GBP/USD |
|---|---|---|
| Renditen **täglich** | Maximum bei Lag **0** (r=0.18) | Lag **0** (r=0.21) |
| Renditen **wöchentlich** | Lag **0** (r=0.23) | Lag **0** (r=0.17) |
| Renditen **monatlich** | Lag +5 (r=0.29) | Lag −5 (r=0.27) |
| **Niveau** monatlich | breit, ~0.16–0.19 | **Plateau ~0.44 über Lags −1 bis +6** |

**Erklärung:** Das Dashboard zeigt **Niveaus** (Kurs-Level und Sentiment-Level, oft auf Index = 100 normiert). Auf Niveau-Ebene korrelieren beide Reihen — bei GBP/USD mit ~0.44 — **aber über ein breites Band von Verzögerungen** (−1 bis +6 alle ~0.4). Genau das sieht das Auge als „Vorlauf".

Ein **echter** Vorlauf zeigt sich als **scharfe Spitze bei einer bestimmten positiven Verzögerung**. Ein **breites Plateau** dagegen ist die Signatur zweier Reihen, die über den Zeitraum **gemeinsam trenden** — nicht von Vorhersage. Sobald man auf **Renditen** wechselt (die stationäre, faire Messung, Kapitel 7.2), verschwindet der scheinbare Vorlauf: das Maximum liegt täglich **und** wöchentlich bei Lag 0. Die monatlichen „Spitzen" (+5 bzw. −5) zeigen in **entgegengesetzte** Richtungen und liegen mit n ≈ 40 **innerhalb** des Bandes (±0.31) — also Rauschen, kein Signal.

> **Kernlektion:** Zwei gemeinsam trendende Reihen sehen im **Niveau** wie ein Vorlauf aus; erst die Analyse auf **Renditen** unterscheidet „bewegt sich gemeinsam" von „sagt vorher". Hier: gemeinsam (Lag 0), kein Vorlauf.

### 9.5 Effekt der Interpolation

Mit linear interpolierten Kurs-Renditen sinkt r für EUR/USD und GBP/USD von ~0.18–0.21 auf ~0.11–0.16. **Das ist erwartbar und methodisch korrekt:** Interpolierte Wochenend-Renditen sind künstlich konstruiert und tragen kein neues Signal — sie verdünnen die Stichprobe. Die Aussage „gleichzeitige Korrelation, kein Vorlauf" gilt in **beiden** Varianten. Deshalb ist die Variante **ohne** Interpolation der primäre Auswertungspfad; die interpolierte dient als Robustheitsnachweis.

### 9.6 Methodische Grenzen (sind Teil der Antwort)

- **Korrelation ≠ Kausalität.** Selbst die klare gleichzeitige Korrelation zeigt nur, dass Markt und Nachrichten gemeinsam reagieren — nicht warum. Ein gemeinsamer dritter Faktor (Makrodaten, Notenbank-Entscheide) kann beide erklären.
- **Lead/Lag wird in der Vorlesung nicht behandelt** — die Methodik folgt der Standard-Statistik-Literatur. Ein formaler **Granger-Test** wäre der nächste Schritt; er ist im Notebook als deaktivierte Zelle vorbereitet (Paket `statsmodels` nötig).
- **EUR/CHF ist bei EODHD praktisch keine Datenquelle** (7 Tage) — negative Evidenz, kein Paar-Ergebnis.
- **Webscraping ist nicht paar-spezifisch** und dünn (Kapitel 8.4).
- **TextBlob auf Finanztexten** liefert oft 0 (Kapitel 8.4).

---

## 10. Die zwei „Master-Grafiken": sauberer Weg vs. Machbarkeitsnachweis

Das Dashboard stellt zwei Wege direkt nebeneinander:

| Baustein | „Master Grafik" (sauberer Weg) | „Master Grafik 2" (Proof of Concept) |
|---|---|---|
| Kurs | Yahoo + EODHD (ausgerichtet, gemittelt) | identisch |
| Öl | Yahoo (WTI/Brent) | identisch |
| **Sentiment** | **EODHD-Polarity, Tagesmedian** | **TextBlob auf Webscraping-Text** |

Der Sinn des zweiten Wegs: Falls der im sauberen Weg gefundene Zusammenhang nur durch die EODHD-Methode entstünde, wäre die Schlussfolgerung wackelig. Taucht ein ähnliches Bild **auch** mit anderer Quelle und Methode auf, ist es robuster. In unserem Fall ist der Webscraping-Weg dafür allerdings zu dünn (Kapitel 8.4) — er bleibt ein Machbarkeitsnachweis.

---

## 11. Das Dashboard

Eine interaktive Streamlit-Anwendung (`dashboard.py`) mit u. a. diesen Seiten:

| Seite | Zweck |
|---|---|
| Übersicht | Projekt-Kennzahlen, Quellenzahl, Datenpunkte |
| Quellenvergleich | Yahoo vs. EODHD vs. MetaTrader, Kursverläufe überlagert |
| Lückenanalyse | welche Tage bei welcher Quelle fehlen |
| Preisabweichungen | Differenz zwischen den Quellen über die Zeit |
| Ölpreise | WTI + Brent mit Rendite-Statistik |
| Nachrichten | Artikel-Browser über die EODHD-Nachrichten |
| Sentiment-Vergleich | EODHD-Wert vs. eigene TextBlob-Berechnung auf demselben Text |
| Master Grafik / Master Grafik 2 | sauberer Weg / Machbarkeitsnachweis (Kapitel 10) |
| Workflow | das Pipeline-Diagramm |

### 11.1 Visualisierungs-Entscheidungen (Theorie-Bezug Woche 8)

| Entscheidung | Begründung |
|---|---|
| **Linien statt Balken** für Zeitreihen | Position auf gemeinsamer Skala ist die effizienteste visuelle Codierung |
| **Vollständige Y-Achse** (kein Beschnitt) | abgeschnittene Achsen können Trends vortäuschen oder verbergen |
| **2D statt 3D** | 3D verzerrt Verhältnisse durch Perspektive |
| **Viridis statt Jet** bei Verläufen | Viridis ist gleichmässig wahrnehmbar (*perceptually uniform*) |
| **Divergierende Farbskala für Sentiment** | Sentiment hat einen natürlichen Nullpunkt |
| **Getrennte Y-Achsen je Kategorie** (Kurs/Öl/Sentiment) | sonst dominiert die Reihe mit der grössten Varianz die Optik |
| **Farbenblind-Verträglichkeit** | rund 8 % der Männer haben eine Rot-Grün-Schwäche; Viridis und Tableau-Farben sind tauglich |

---

## 12. Reproduzierbarkeit — Befehle und Reihenfolge

Alle Schritte sind idempotent. Reihenfolge:

```bash
source .venv/bin/activate

# 1. Rohdaten laden (EODHD-Tageslimit beachten!)
python src/data_loading/yahoo_loader.py
python src/data_loading/eodhd_loader.py
python src/data_loading/eodhd_news_loader.py
python src/data_loading/webscraping_loader.py
python src/data_loading/oil_loader.py

# 2. Bereinigen, ausrichten, zusammenführen
python scripts/regenerate_forex_combined.py          # inkl. Datums-Ausrichtung (Kap. 6.2)
python scripts/regenerate_webscraping_sentiment.py

# 3. Analyse-Ergebnisse erzeugen
python scripts/regenerate_lead_lag_results.py        # schreibt lead_lag_results.csv (headless)
# alternativ das Notebook in Jupyter ausfuehren:
#   notebooks/datenverarbeitung/sentiment_kurs_lead_lag_analyse.ipynb

# 4. Dashboard starten
streamlit run dashboard.py
```

**Hinweis:** Das Lead/Lag-Notebook und `regenerate_lead_lag_results.py` nutzen dieselbe Logik und erzeugen dieselben Zahlen. Das Skript ist der zuverlässige, kernel-freie Weg (die automatische Notebook-Ausführung kann im Jupyter-Kernel hängen bleiben).

---

## 13. Bekannte Einschränkungen

| Punkt | Auswirkung | Behandlung |
|---|---|---|
| EUR/CHF-Nachrichten bei EODHD ≈ 13 Artikel | keine belastbare Sentiment-Korrelation | dokumentiert, aus der Sentiment-Analyse ausgenommen |
| Webscraping nur ab Scrape-Zeitpunkt, dünn (Kap. 8.4) | dirty-Weg nicht belastbar | offen dokumentiert, nur als Machbarkeitsnachweis |
| TextBlob: ~⅓ der Artikel mit Wert 0 | unterschätzt Sentiment-Abdeckung | offen dokumentiert; FinBERT/VADER als Erweiterung |
| MetaTrader-Daten enden 2025-12-26 | kein 2026-Anteil | nur im Quellenvergleich genutzt |
| Quellen-Datierungsfehler (Kap. 5.3) | hätte den Mittelwert verfälscht | datengetrieben ausgerichtet, dokumentiert, behoben |
| DailyFX-/Investing.com-Scraping: HTTP 403 | zwei Quellen blockiert | abgefangen; übrige Feeds reichen |
| RSS-SSL-Fehler auf macOS | anfangs 0 Artikel | über `requests` + `feedparser` behoben |

---

## 14. Projektstruktur (Kurzübersicht)

```
datawrangling/
├── src/data_loading/          # ein Lade-Skript pro Quelle
├── scripts/                   # idempotente Verarbeitungs-/Build-Skripte
│   ├── regenerate_forex_combined.py        # Bereinigung + Datums-Ausrichtung
│   ├── regenerate_webscraping_sentiment.py
│   ├── regenerate_lead_lag_results.py      # Analyse-Ergebnisse (headless)
│   ├── generate_lead_lag_notebook.py
│   └── build_documentation_docx.py
├── notebooks/
│   ├── rohdaten_laden/        # EDA pro Quelle (01–05)
│   └── datenverarbeitung/     # Analyse-Notebooks (inkl. Lead/Lag)
├── data/  (raw / processed / final)
├── docs/architektur/          # Pipeline-Diagramm
├── dashboard.py               # Streamlit-App
└── DOKUMENTATION.md           # dieses Dokument
```

*EDA = Exploratory Data Analysis (explorative Datenanalyse).*

---

## 15. Protokoll — Chronologie der wichtigsten Entscheidungen

| Zeitpunkt (2026) | Entscheidung / Beobachtung |
|---|---|
| Februar | Themenfestlegung: Wechselkurse + Nachrichten-Sentiment + Öl. |
| Anfang März | EODHD-Integration; Tageslimit als Randbedingung erkannt. |
| März | Entscheidung pro **Median** bei der Tagesaggregation des Sentiments (robuster). |
| April | Daten bis 2022 zurück frisch geladen; RSS-SSL-Fehler erkannt und behoben; Webscraping-Machbarkeitsnachweis ergänzt. |
| Mai | Lead/Lag-Notebook erstellt; Outer-Join ohne vorab gebildeten Mittelwert/Interpolation festgelegt (Mittel/Interpolation erst zur Laufzeit). |
| Juni | **Qualitätsprüfung über Quellen:** Datierungsfehler (Yahoo/EODHD/MetaTrader-Tagesversatz) entdeckt, datengetriebene Ausrichtung in die Pipeline eingebaut, Lead/Lag neu gerechnet. **Beobachtung „Grafik suggeriert Vorlauf"** geprüft → Niveau-Trend vs. Renditen-Analyse abgegrenzt. Dokumentation als verständliches Protokoll neu aufgebaut; Umlaute in Code/Kommentaren vereinheitlicht. |

---

## 16. Offen / Ausblick

- **Granger-Test** als formaler Folgeschritt (Paket `statsmodels`).
- **Finanzspezifisches Sentiment** (FinBERT, VADER + Loughran-McDonald-Lexikon) statt TextBlob — würde die ~⅓ Nullwerte deutlich reduzieren.
- **Grafiken in den Bericht einbetten** (Kreuzkorrelations-Kurve, Quellenvergleich, Lückenanalyse, Niveau-vs-Renditen-Gegenüberstellung) — folgt als letzter Schritt vor der Abgabe.
