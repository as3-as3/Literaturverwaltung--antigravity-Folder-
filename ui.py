import customtkinter as ctk
import os
import sys
import threading
import time
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
        self.sidebar_frame.grid_rowconfigure(6, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="APL System", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_autorun = ctk.CTkButton(self.sidebar_frame, text="▶ Auto-Pipeline (lokal)", command=self.on_autorun, fg_color="#1E90FF", hover_color="#1874CD")
        self.btn_autorun.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_scan = ctk.CTkButton(self.sidebar_frame, text="1. Manuell: Index", command=self.on_scan)
        self.btn_scan.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_hydrate = ctk.CTkButton(self.sidebar_frame, text="2. Manuell: Hydrate", command=self.on_hydrate)
        self.btn_hydrate.grid(row=3, column=0, padx=20, pady=10)
        
        self.btn_sort = ctk.CTkButton(self.sidebar_frame, text="3. Manuell: Auto-Sort", command=self.on_sort)
        self.btn_sort.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_export = ctk.CTkButton(self.sidebar_frame, text="4. Manuell: Export", command=self.on_export)
        self.btn_export.grid(row=5, column=0, padx=20, pady=10)
        
        self.btn_import = ctk.CTkButton(self.sidebar_frame, text="5. Ordner Importieren", command=self.on_import)
        self.btn_import.grid(row=6, column=0, padx=20, pady=10)

        # Main content area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.log_textbox = ctk.CTkTextbox(self.main_frame, width=600, height=500)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.log_textbox.insert("0.0", "System Initialized. Awaiting commands...\n")
        self.log_textbox.configure(state="disabled")
        
        self.progressbar = ctk.CTkProgressBar(self.main_frame)
        self.progressbar.pack(fill="x", padx=10, pady=(5, 0))
        self.progressbar.set(0.0)
        
        self.eta_label = ctk.CTkLabel(self.main_frame, text="Wartet...", text_color="gray", font=ctk.CTkFont(size=11))
        self.eta_label.pack(anchor="e", padx=10, pady=(2, 10))

    def log(self, message):
        """Thread-safe logging to the text box."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def set_progress(self, value, eta_text=""):
        self.progressbar.set(value)
        if eta_text:
            self.eta_label.configure(text=eta_text)

    def on_autorun(self):
        self.log("[*] Starte vollständige Auto-Pipeline für den USB-Stick...")
        self.log("[*] Das System bearbeitet ausschließlich den Ordner in dem diese .exe liegt!")
        self.progressbar.set(0)
        self.eta_label.configure(text="Initialisiere...")
        
        def worker():
            start_total = time.time()
            self.log("[+] Schritt 1/4: Indexiere lokale Dokumente...")
            indexer.run_indexer(database.get_base_path(), log_callback=self.log, progress_callback=self.set_progress)
            
            self.log("[+] Schritt 2/4: Sammle Metadaten...")
            hydrator.hydrate_documents(log_callback=self.log, progress_callback=self.set_progress)
            
            self.log("[+] Schritt 3/4: Bibliotheks-Sortierung...")
            sorter.run_sorter(log_callback=self.log, progress_callback=self.set_progress)
            
            self.log("[+] Schritt 4/4: Listen-Export & HTML-Suche...")
            exporter.export_research_list(log_callback=self.log)
            exporter.export_html_search(log_callback=self.log)
            
            elapsed = time.time() - start_total
            m, s = divmod(int(elapsed), 60)
            h, m = divmod(m, 60)
            time_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
            
            self.set_progress(1.0, f"Fertig in {time_str}")
            self.log(f"[*] Komplette Pipeline erfolgreich beendet! (Gesamtdauer: {time_str})")
            
        threading.Thread(target=worker, daemon=True).start()

    def on_scan(self):
        self.log("[*] Folder Scan triggered...")
        self.progressbar.set(0)
        self.eta_label.configure(text="Berechne...")
        def worker():
            st = time.time()
            indexer.run_indexer(database.get_base_path(), log_callback=self.log, progress_callback=self.set_progress)
            m, s = divmod(int(time.time() - st), 60)
            self.set_progress(1.0, f"Fertig in {m}m {s}s")
            self.log(f"[*] Scan task completed in {m}m {s}s.")
        threading.Thread(target=worker, daemon=True).start()

    def on_hydrate(self):
        self.log("[*] API Hydration triggered...")
        self.progressbar.set(0)
        self.eta_label.configure(text="Berechne...")
        def worker():
            st = time.time()
            hydrator.hydrate_documents(log_callback=self.log, progress_callback=self.set_progress)
            m, s = divmod(int(time.time() - st), 60)
            self.set_progress(1.0, f"Fertig in {m}m {s}s")
            self.log(f"[*] Hydration task completed in {m}m {s}s.")
        threading.Thread(target=worker, daemon=True).start()
        
    def on_sort(self):
        self.log("[*] Thematic Sort triggered...")
        self.progressbar.set(0)
        self.eta_label.configure(text="Berechne...")
        def worker():
            st = time.time()
            sorter.run_sorter(log_callback=self.log, progress_callback=self.set_progress)
            m, s = divmod(int(time.time() - st), 60)
            self.set_progress(1.0, f"Fertig in {m}m {s}s")
            self.log(f"[*] Sorting task completed in {m}m {s}s.")
        threading.Thread(target=worker, daemon=True).start()
        
    def on_export(self):
        self.log("[*] Research List Export triggered...")
        st = time.time()
        exporter.export_research_list(log_callback=self.log)
        exporter.export_html_search(log_callback=self.log)
        m, s = divmod(int(time.time() - st), 60)
        self.log(f"[*] Export completed in {m}m {s}s.")

    def on_import(self):
        folder = ctk.filedialog.askdirectory(title="Zu importierenden Ordner auswählen")
        if not folder:
            return
            
        self.log(f"[*] Import gestartet von: {folder}")
        self.progressbar.set(0)
        
        def worker():
            start_total = time.time()
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
                            
            self.log(f"[*] Import abgeschlossen: {copied} Dateien nach '_Inbox' kopiert.")
            self.log("[*] Führe automatischen Index- & Sortierdurchlauf aus...")
            
            # Chain the pipeline immediately for zero-click sorting of the import
            indexer.run_indexer(database.get_base_path(), log_callback=self.log, progress_callback=self.set_progress)
            hydrator.hydrate_documents(log_callback=self.log, progress_callback=self.set_progress)
            sorter.run_sorter(log_callback=self.log, progress_callback=self.set_progress)
            exporter.export_research_list(log_callback=self.log)
            exporter.export_html_search(log_callback=self.log)
            
            elapsed = time.time() - start_total
            m, s = divmod(int(elapsed), 60)
            h, m = divmod(m, 60)
            time_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
            
            self.set_progress(1.0, f"Fertig in {time_str}")
            self.log(f"[*] APL Import-Pipeline erfolgreich abgeschlossen! (Gesamtdauer: {time_str})")
            
        threading.Thread(target=worker, daemon=True).start()
