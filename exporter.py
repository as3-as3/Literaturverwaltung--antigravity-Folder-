import os
import sqlite3
import json
import database

def export_research_list(log_callback=None, use_relative_paths=True):
    path = os.path.join(database.get_base_path(), "Research_List.md")
    
    conn = sqlite3.connect(database.get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT title, author, year, relative_path, isbn, doi FROM documents")
    docs = cursor.fetchall()
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# APL Research List\n\n")
            f.write("*Autonom generierte Recherche-Ablage*\n\n---\n")
            for doc in docs:
                title, author, year, rel_path, isbn, doi = doc
                safe_title = title if title else "Unbekannter Titel"
                safe_author = author if author else "Unbekannter Autor"
                safe_year = f" ({year})" if year else ""
                
                f.write(f"### {safe_title}{safe_year}\n")
                f.write(f"- **Autor:** {safe_author}\n")
                if isbn: f.write(f"- **ISBN:** {isbn}\n")
                if doi: f.write(f"- **DOI:** {doi}\n")
                
                if use_relative_paths:
                    clean_path = str(rel_path).replace('\\', '/')
                    f.write(f"- **Datei:** [{os.path.basename(clean_path)}](./{clean_path})\n")
                f.write("\n---\n\n")
                
        if log_callback: log_callback(f"[OK] Research-List exported to {path}")
    except Exception as e:
        if log_callback: log_callback(f"[Error] Failed to export MD: {e}")
        
    conn.close()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APL Search Explorer</title>
    <style>
        :root {
            --bg-color: #1a1a1a;
            --surface: #2d2d2d;
            --text-main: #f0f0f0;
            --text-muted: #a0a0a0;
            --accent: #2e7d32;
            --accent-hover: #1b5e20;
            --border: #404040;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Segoe UI', system-ui, sans-serif;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            margin-bottom: 25px;
        }
        h1 { margin: 0; color: var(--accent); }
        .search-box {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text-main);
            border-radius: 8px;
            box-sizing: border-box;
            margin-bottom: 20px;
        }
        .search-box:focus {
            outline: none;
            border-color: var(--accent);
        }
        .stats { margin-bottom: 20px; color: var(--text-muted); font-size: 14px; }
        .result-item {
            background: var(--surface);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .info { flex: 1; margin-right: 15px; overflow: hidden; }
        .title { font-weight: bold; font-size: 16px; margin: 0 0 6px 0; color: #fff; word-break: break-word; }
        .meta { font-size: 13px; color: var(--text-muted); margin: 0; line-height: 1.4; }
        .btn-open {
            background-color: var(--accent);
            color: white;
            padding: 10px 18px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
            white-space: nowrap;
            transition: background 0.2s;
        }
        .btn-open:hover {
            background-color: var(--accent-hover);
        }
        #results { list-style: none; padding: 0; margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>APL Search Explorer</h1>
            <p style="color:var(--text-muted); margin-top:5px;">Mobile Offline-Bibliothek</p>
        </header>
        <input type="text" id="searchInput" class="search-box" placeholder="Suchen nach Titel, Autor, Index-Wörtern..." onkeyup="filterDocs()">
        <div class="stats" id="statsField">Lade Dokumente...</div>
        <ul id="results"></ul>
    </div>

    <script>
        const dbItems = __DATA_INJECTION_POINT__;
        const resultsEl = document.getElementById('results');
        const statsEl = document.getElementById('statsField');
        
        function renderItems(items) {
            resultsEl.innerHTML = '';
            statsEl.innerText = items.length + ' Dokument(e) gefunden (Zeigt max. 250 aus Performancegründen)';
            
            const limit = Math.min(items.length, 250);
            for(let i=0; i < limit; i++) {
                const item = items[i];
                const li = document.createElement('li');
                li.className = 'result-item';
                
                let metaText = [];
                if(item.author) metaText.push('👤 ' + item.author);
                if(item.year) metaText.push('📅 ' + item.year);
                if(item.keywords) metaText.push('📌 ' + item.keywords);
                
                li.innerHTML = `
                    <div class="info">
                        <p class="title">${item.title || item.filename}</p>
                        <p class="meta">${metaText.join(' | ') || 'Keine Metadaten verzeichnet'}</p>
                    </div>
                    <a class="btn-open" href="${item.path}" target="_blank">Öffnen</a>
                `;
                resultsEl.appendChild(li);
            }
        }

        function filterDocs() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            if(!query) {
                renderItems(dbItems);
                return;
            }
            
            const terms = query.split(' ').filter(t => t.trim() !== '');
            const filtered = dbItems.filter(item => {
                const searchable = `${item.title || ''} ${item.filename} ${item.author || ''} ${item.keywords || ''}`.toLowerCase();
                return terms.every(term => searchable.includes(term));
            });
            renderItems(filtered);
        }

        renderItems(dbItems);
    </script>
</body>
</html>
"""

def export_html_search(log_callback=None):
    path = os.path.join(database.get_base_path(), "APL_Search.html")
    
    conn = sqlite3.connect(database.get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT filename, title, author, year, keywords, relative_path FROM documents")
    docs = cursor.fetchall()
    
    db_items = []
    for doc in docs:
        filename, title, author, year, keywords, rel_path = doc
        safe_path = ""
        if rel_path:
            safe_path = "./" + str(rel_path).replace("\\", "/")
            
        db_items.append({
            "filename": filename or "",
            "title": title or "",
            "author": author or "",
            "year": year or "",
            "keywords": keywords or "",
            "path": safe_path
        })
        
    json_data = json.dumps(db_items)
    html_content = HTML_TEMPLATE.replace("__DATA_INJECTION_POINT__", json_data)
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        if log_callback: log_callback(f"[OK] Mobile HTML-Suche generiert: {path}")
    except Exception as e:
        if log_callback: log_callback(f"[Error] Failed to generate HTML: {e}")
        
    conn.close()
