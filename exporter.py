import os
import sqlite3
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
        if log_callback: log_callback(f"[Error] Failed to export: {e}")
        
    conn.close()
