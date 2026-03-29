# Autonome Portable Literaturverwaltung (APL)

APL ist ein KI-generiertes System zur automatisierten Katalogisierung, Indexierung und Sortierung umfangreicher PDF- und EPUB-Bibliotheken. Das Programm wurde explizit für den **Offline-First** und **Stand-Alone (USB-Stick)**-Betrieb entwickelt.

## 🚀 Kernfunktionen

### 1. Autonomer Indexer & Extractor (`indexer.py`)
- **Rekursiver Scan**: Durchsucht sämtliche Unterordner ab dem Ausführungsverzeichnis der `.exe`.
- **Intelligente OCR-Fallback Regex:** Extrahiert völlig autark **ISBN** und **DOI** Nummern aus Dateinamen sowie dem Inhalt der ersten 10 Seiten mittels `pypdf` (für PDFs) und `EbookLib` (für EPUBs).

### 2. Meta-Hydration-Modul (`hydrator.py`)
- **Sichere API-Abfragen:** Verbindet sich passiv mit **CrossRef** (für DOIs) und **OpenLibrary** (für ISBNs), um vollautomatisierte Metadaten (Titel, Jahr, Autor, Stichworte) herunterzuladen.
- **Fair-Use Rate-Limiting:** Ein integrierter 1.5-Sekunden-Timer verhindert proaktiv eine Sperrung der IP-Adresse bei Batch-Anfragen von über tausend Büchern.
- Es werden keinerlei redundante Daten abgefragt (`is_hydrated`-State-Flag).

### 3. KI Thematische NLP-Sortierung (`sorter.py`)
- **Unüberwachtes maschinelles Lernen:** Analysiert extrahierte Titel und Keywords per TF-IDF Logik (`scikit-learn`). Stoppwörter (Deutsch & Englisch) werden herausgefiltert.
- **4-Ebenen-Hierarchie:** Verteilt unstrukturierte Literatur physikalisch in Ordner mit bis zu 4 Stichwort-Ebenen Tiefe.
- **CSV-Overrides (`folder_config.csv`):** Falls eine `folder_config.csv` (Aufbau: `Zielordner; Inklusion,Wörter; Exklusion,Wörter`) angelegt wird, überschreibt diese auf letzter Ebene die Sortierlogik. Treffen Stichwörter auf mehrere Ordner zu, wird die Datei physikalisch in alle zutreffenden Ordner kopiert (*Multimatch*).
- Enthält ein robustes Fallback in den Ordner `_Manuelle_Pruefung`.

### 4. Portable Architektur (`database.py` & GUI)
- **Deep Dark UI:** Minimalistisches, asynchrones (Multi-Threading) CustomTkinter-Frontend in Dunkelgrün & Grau mit **grafischem Ladebalken**.
- **USB-Stick Resilient:** SQLite3 Datenbank mit aktivierter FTS5-Volltextsuche und `WAL`-Journal. Garantiert ACID-atomare Transaktionen (Drop-Safe: Bricht nicht bei USB-Disconnects während der Nutzung zusammen).
- Berechnet und speichert immer exakte **Relative Pfade**, egal an welchem Rechner (z.B. Laufwerk D: oder H:) der Stick eingesteckt wird.

### 5. Research Listen-Generator (`exporter.py`)
- Exportiert auf Knopfdruck eine saubere, offline nutzbare Markdown-Referenzdatei (`Research_List.md`).
- Generiert APA-strukturierte Metadaten mit funktionierenden **anklickbaren, relativen System-Links** zu der dazugehörigen .epub oder .pdf Datei.

---

## 🛠 Setup & Kompilierung (Stand-Alone EXE)

Da das System Python Module wie `scikit-learn` benötigt, wurde ein automatisierter Windows-Batch eingebunden, um eine portable ausführbare Datei (`.exe`) zu verpacken:

1. Führen Sie die Datei `build.bat` aus.
2. Im Hintergrund lädt der Manager die Pakete (Python 3.14 kompatibel via `pypdf`) herunter. 
3. Anschließend verpackt `pyinstaller` alles in eine **einzige .exe Datei**.
4. Die fertige `APL.exe` finden Sie im erstellten Ordner `/dist`. Kopieren Sie ausschließlich diese `.exe` auf Ihren USB-Stick und legen Sie los!
