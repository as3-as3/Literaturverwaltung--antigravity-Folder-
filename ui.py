import customtkinter as ctk
import os
import sys
import threading
import database
import indexer
import hydrator
import sorter
import exporter

def apply_theme():
    """Applies the dark mode and dark green accent theme."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

class APLMainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("APL - Autonome Portable Literaturverwaltung")
        self.geometry("900x600")
        
        # Grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="APL System", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_scan = ctk.CTkButton(self.sidebar_frame, text="1. Index Folder", command=self.on_scan)
        self.btn_scan.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_hydrate = ctk.CTkButton(self.sidebar_frame, text="2. Meta-Hydration", command=self.on_hydrate)
        self.btn_hydrate.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_sort = ctk.CTkButton(self.sidebar_frame, text="3. Auto-Sort (NLP)", command=self.on_sort)
        self.btn_sort.grid(row=3, column=0, padx=20, pady=10)
        
        self.btn_export = ctk.CTkButton(self.sidebar_frame, text="4. Export Lists", command=self.on_export)
        self.btn_export.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_import = ctk.CTkButton(self.sidebar_frame, text="5. Ordner Importieren", command=self.on_import)
        self.btn_import.grid(row=5, column=0, padx=20, pady=10)

        # Main content area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.log_textbox = ctk.CTkTextbox(self.main_frame, width=600, height=500)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.log_textbox.insert("0.0", "System Initialized. Awaiting commands...\n")
        self.log_textbox.configure(state="disabled")
        
        self.progressbar = ctk.CTkProgressBar(self.main_frame)
        self.progressbar.pack(fill="x", padx=10, pady=(5, 10))
        self.progressbar.set(0.0)

    def log(self, message):
        """Thread-safe logging to the text box."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def set_progress(self, value):
        self.progressbar.set(value)

    def on_scan(self):
        self.log("[*] Folder Scan triggered...")
        self.progressbar.set(0)
        def worker():
            indexer.run_indexer(database.get_base_path(), log_callback=self.log, progress_callback=self.set_progress)
            self.set_progress(1.0)
            self.log("[*] Scan task completed.")
        threading.Thread(target=worker, daemon=True).start()

    def on_hydrate(self):
        self.log("[*] API Hydration triggered...")
        self.progressbar.set(0)
        def worker():
            hydrator.hydrate_documents(log_callback=self.log, progress_callback=self.set_progress)
            self.set_progress(1.0)
            self.log("[*] Hydration task completed.")
        threading.Thread(target=worker, daemon=True).start()
        
    def on_sort(self):
        self.log("[*] Thematic Sort triggered...")
        self.progressbar.set(0)
        def worker():
            sorter.run_sorter(log_callback=self.log, progress_callback=self.set_progress)
            self.set_progress(1.0)
            self.log("[*] Sorting task completed.")
        threading.Thread(target=worker, daemon=True).start()
        
    def on_export(self):
        self.log("[*] Research List Export triggered...")
        exporter.export_research_list(log_callback=self.log)

    def on_import(self):
        folder = ctk.filedialog.askdirectory(title="Zu importierenden Ordner auswählen")
        if not folder:
            return
            
        self.log(f"[*] Import gestartet von: {folder}")
        self.progressbar.set(0)
        
        def worker():
            target_base = os.path.join(database.get_base_path(), "_Inbox")
            os.makedirs(target_base, exist_ok=True)
            copied = 0
            
            # Count total bounds
            total_files = sum([len(files) for r, d, files in os.walk(folder)])
            if total_files == 0:
                self.log("[*] Keine Dateien gefunden.")
                return
                
            cur = 0
            for dirpath, _, filenames in os.walk(folder):
                for f in filenames:
                    ext = f.lower().split('.')[-1]
                    cur += 1
                    self.set_progress(cur / float(max(1, total_files)))
                    if ext in ['pdf', 'epub']:
                        import shutil
                        src = os.path.join(dirpath, f)
                        dest = os.path.join(target_base, f)
                        try:
                            if src != dest:
                                shutil.copy2(src, dest)
                                copied += 1
                        except Exception:
                            pass
                            
            self.set_progress(1.0)
            self.log(f"[*] Import abgeschlossen: {copied} Dateien nach '_Inbox' kopiert.")
            self.log("[*] Führe automatischen Index- & Sortierdurchlauf aus...")
            
            # Chain the pipeline immediately for zero-click sorting of the import
            indexer.run_indexer(database.get_base_path(), log_callback=self.log, progress_callback=self.set_progress)
            hydrator.hydrate_documents(log_callback=self.log, progress_callback=self.set_progress)
            sorter.run_sorter(log_callback=self.log, progress_callback=self.set_progress)
            exporter.export_research_list(log_callback=self.log)
            
            self.log("[*] APL Pipeline für Import-Container erfolgreich abgeschlossen!")
            
        threading.Thread(target=worker, daemon=True).start()
