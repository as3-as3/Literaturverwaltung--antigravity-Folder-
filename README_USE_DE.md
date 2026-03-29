# 📖 APL Bedienungsanleitung (Readme4Use)

Willkommen zur **Autonomen Portablen Literaturverwaltung (APL)**. 
Dieses System ist dafür konzipiert, hunderte bis zehntausende von ungeregelten PDF- und EPUB-Dokumenten auf einem USB-Stick oder lokalen Ordner vollautomatisiert zu durchsuchen, Metadaten aus dem Internet anzureichern und sie im Anschluss in saubere, berechnete "Bibliotheks-Überthemen" zu wegsortieren.

---

## ⚙️ Wie benutze ich das System?

Das Haupt-Programm (`APL.exe`) stellt Ihnen fünf Knöpfe zur Verfügung. Die Arbeitsweise ist logisch von oben (1) nach unten (4) aufgebaut.

### Methode A: Der bequeme "Alles-Vollautomatisch" Weg
Sie haben einen Ordner voller roher PDFs auf Ihrem Desktop (oder in E-Mails) und wollen, dass APL sie "schluckt" und in seiner Library wegsortiert?
👉 **Klicken Sie auf `5. Ordner Importieren`**
Wählen Sie den externen Quell-Ordner aus. Das System kopiert die Literatur auf Ihren Speicher und feuert anschließend unsichtbar und in immenser Geschwindigkeit die klassischen Sortier-Schritte vollautomatisiert hintereinander ab. Am Ende ist alles fertig gestaffelt.

### Methode B: Der "Manuelle Phasen" Weg
Haben Sie die PDFs einfach formlos irgendwo auf Ihren USB-Stick gezogen und wollen, dass APL den dortigen "Müll" im Nachhinein aufräumt? Dann klicken Sie bitte die Tasten auf der linken Seite strikt nacheinander von 1 bis 4 ab:

1. **Index Folder (Der Spürhund):** Wühlt sich parallel durch den gesamten Stick, sucht neue PDFs und durchleuchtet rasant die ersten 10 Seiten im Volltext nach ISBN/DOI Indikatoren.
2. **Hydrate Meta (Der Archivar):** Zieht anhand der im ersten Schritt gefundenen IDs offizielle Titel, Autoren, Jahre und Stichworte via Crossref und OpenLibrary aus dem Internet.
3. **Thematic Sort (Der Bibliothek-Bauer):** Nimmt die gesichteten Texte einer jeden Datei und sortiert das physische PDF-Dokument anhand von komplexer Mathematik in offizielle Bibliotheks-Kategorien (z.B. in den Ordner `Informatik & IT / Algorithmus`) weg.
4. **Export Lists (Die Zitation):** Schreibt Ihnen eine exportierte `Research_List.md` mit echten APA-Zitationen und funktionierenden Klick-Links auf das neu verschobene End-PDF.

---

## 🔍 Wie finde ich Literatur wieder? (APL Search Explorer)
Wenn Sie direkt auf ein Fachbuch zugreifen wollen, starten Sie niemals den Explorer und wühlen manuell, sondern starten Sie die zweite Begleit-Anwendungsdatei: **`APL_Search.exe`**.

- **Suchen:** Geben Sie Schlagwörter wie `Soziologie*` oder Auszüge aus dem Titel ein. Der native Explorer dämmt Duplikate (z.B. wenn eine Datei in mehreren Unterordnern liegt) sofort visuell ein.
- **Lesen & Kopieren:** Mit einem Klick auf *Öffnen* greift der APL Explorer in seine unterliegende Datenbank und reicht den echten Dateipfad direkt an Ihren installierten Adobe/Standard-PDF-Viewer durch. Wenn Sie ein Buch extrahieren wollen, klicken Sie auf *Kopieren* und wählen den Desktop – das sortierte Original bleibt unversehrt in der Bibliothek auf dem Stick eingeschlossen.

---

## 📊 Kapazitäten & Systemgrenzen (Wie viel schafft APL?)

Das Programm ist architektonisch extrem stabil und nach reinen Big-Data Prinzipien aufgebaut. Es gibt in keinem der Verarbeitungsschritte ein Limit.

1. **Die Auslastung beim Einlesen (Miner/Indexer):** 
   Dank der fliegenden "Multi-Threading" Softwarearchitektur beansprucht die App Ihren Prozessor optimal, blockiert aber zu keinem Zeitpunkt den RAM. Die Logik schnappt sich immer passend zu Ihren Hardware-Prozessorkernen (z. B. 8 oder 16) parallel eine handvoll PDFs. Ob Sie 100 oder **50.000 PDFs** auf einmal einwerfen: Die CPU ackert schnellstmöglich, Ihr Arbeitsspeicher läuft aber niemals voll.
2. **Der Zeit-Flaschenhals (Metadaten-Hydrator):**
   Das Abfragen gigantischer Datenströme im Internet (Schritt 2) zwingt das System aus gutem Grund zu **1,5 Sekunden Wartezeit** pro Buch. Ansonsten würden Sie einen "DDoS-Angriff" auslösen und die Server-Hostersperre riskieren.
   *Zeit-Aussicht:* Für 1.000 völlig neue Bücher wartet APL entspannt ca. 25 Minuten auf die API. Sie können bedenkenlos 50.000 Bücher am Stück einpflegen, das System stürzt nicht ab. Wundern Sie sich nur nicht, wenn es unaufgeregt eine ganze Nacht lang arbeitet.
3. **Massen-Clustering (Thematic Sorter):**
   Die KI-Vektor-Berechnungen ("Welches Buch passt physikalisch am besten zum Fachgebiet X?") gruppieren die Themen in Sekundenschnelle im Arbeitsspeicher, ohne Ihre Festplatte zu belasten. Selbst das simultane Verschieben von 10.000 fertig erkannten Dateien ist mit dem Programm ein Klacks.
