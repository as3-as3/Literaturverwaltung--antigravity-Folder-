import customtkinter as ctk
import sqlite3
import os
import shutil
import database  

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class SearchApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("APL - Search Explorer")
        self.geometry("900x700")
        
        # Grid layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Top Frame (Search Bar)
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        self.top_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Stichwort / Synonymsuche (z.B. auto* or ai*)")
        self.search_entry.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="ew")
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        
        self.search_btn = ctk.CTkButton(self.top_frame, text="Suchen", command=self.perform_search)
        self.search_btn.grid(row=0, column=1, padx=(0, 10), pady=10)
        
        # Bottom Frame (Results)
        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(self, text="Bereit. Datenbank via FTS5 verbunden.", text_color="gray")
        self.status_label.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 10))

    def perform_search(self):
        query = self.search_entry.get().strip()
        
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        if not query:
            self.status_label.configure(text="Bitte einen Suchbegriff eingeben.", text_color="gray")
            return
            
        # Optional synonym-like fuzzy weighting behavior for single words via SQLite GLOB asterisk
        fts_query = f"{query}*" if " " not in query and not query.endswith("*") else query

        conn = sqlite3.connect(database.get_db_path())
        cursor = conn.cursor()
        
        try:
            # JOIN query linking virtual FTS table to main structure while deduplicating exact match titles.
            sql = '''
                SELECT d.title, d.author, d.year, d.filename, d.relative_path, d.keywords
                FROM documents_fts fts
                JOIN documents d ON fts.rowid = d.id
                WHERE documents_fts MATCH ?
                GROUP BY d.filename
                ORDER BY rank
                LIMIT 100
            '''
            cursor.execute(sql, (fts_query,))
            results = cursor.fetchall()
            
            self.status_label.configure(text=f"{len(results)} eindeutige Literatur(en) gefunden (Dedupliziert).", text_color="gray")
            
            for index, res in enumerate(results):
                title, author, year, filename, rel_path, keywords = res
                
                res_box = ctk.CTkFrame(self.results_frame, fg_color="#2b2b2b", corner_radius=5)
                res_box.grid(row=index, column=0, sticky="ew", padx=5, pady=5)
                res_box.grid_columnconfigure(0, weight=1)
                
                t_str = title if title else "Unbekannter Titel"
                a_str = author if author else "Unbekannter Autor"
                y_str = year if year else ""
                
                lbl_title = ctk.CTkLabel(res_box, text=f"{t_str} ({y_str})", font=ctk.CTkFont(weight="bold", size=14), anchor="w")
                lbl_title.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 0))
                
                lbl_sub = ctk.CTkLabel(res_box, text=f"Autor: {a_str} | Tags: {keywords[:50] if keywords else ''}...", text_color="gray", anchor="w")
                lbl_sub.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))
                
                btn_frame = ctk.CTkFrame(res_box, fg_color="transparent")
                btn_frame.grid(row=0, column=1, rowspan=2, padx=10, pady=5)
                
                btn_open = ctk.CTkButton(btn_frame, text="Öffnen", width=80, command=lambda p=rel_path: self.open_file(p))
                btn_open.grid(row=0, column=0, padx=5)
                
                btn_copy = ctk.CTkButton(btn_frame, text="Kopieren", width=80, fg_color="#444", command=lambda p=rel_path, f=filename: self.copy_file(p, f))
                btn_copy.grid(row=0, column=1, padx=5)
                
        except sqlite3.Error as e:
            self.status_label.configure(text=f"Suchfehler: {e}", text_color="red")
            
            # Fallback if Match expression is strictly invalid
            if "syntax error" in str(e).lower():
                self.status_label.configure(text="Ungültige FTS-Syntax (z.B. ein fehlendes '*'). Bitte anders formulieren.", text_color="orange")
        finally:
            conn.close()

    def open_file(self, rel_path):
        full_path = os.path.join(database.get_base_path(), rel_path)
        if os.path.exists(full_path):
            os.startfile(full_path)
        else:
            self.status_label.configure(text=f"Fehler: Datei nicht gefunden unter {rel_path}.", text_color="red")

    def copy_file(self, rel_path, filename):
        full_path = os.path.join(database.get_base_path(), rel_path)
        if not os.path.exists(full_path):
            self.status_label.configure(text="Fehler: Datei nicht im Archiv gefunden.", text_color="red")
            return
            
        target_dir = ctk.filedialog.askdirectory(title="Speicherort zum Herauskopieren wählen")
        if target_dir:
            dest = os.path.join(target_dir, filename)
            try:
                shutil.copy2(full_path, dest)
                self.status_label.configure(text=f"Erfolgreich kopiert nach {dest}.", text_color="green")
            except Exception as e:
                self.status_label.configure(text=f"Kopierfehler: {e}", text_color="red")

if __name__ == "__main__":
    app = SearchApp()
    app.mainloop()
