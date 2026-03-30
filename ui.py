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

class SortingPreviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, category_counts, assignments, on_confirm):
        super().__init__(parent)
        self.title("Sortiervorschau & Kategorien-Setup")
        self.geometry("600x700")
        self.assignments = assignments
        self.on_confirm = on_confirm
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Schritt 1: Kategorien prüfen & anpassen", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=20)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Erkannte Kategorien")
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        self.category_widgets = {}
        # Sort by count descending
        sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        for name, count in sorted_cats:
            frame = ctk.CTkFrame(self.scroll_frame)
            frame.pack(fill="x", pady=5, padx=5)
            
            var_include = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(frame, text=f"({count})", variable=var_include, width=50)
            cb.pack(side="left", padx=5)
            
            entry = ctk.CTkEntry(frame, width=300)
            entry.insert(0, name)
            entry.pack(side="left", padx=5, fill="x", expand=True)
            
            self.category_widgets[name] = {"include": var_include, "entry": entry}

        self.btn_confirm = ctk.CTkButton(self, text="Bestätigen & Fallback berechnen", command=self._confirm)
        self.btn_confirm.grid(row=2, column=0, pady=20)
        
        self.after(100, self.lift)
        self.grab_set()

    def _confirm(self):
        rename_map = {}
        excluded = []
        for old_name, widgets in self.category_widgets.items():
            new_name = widgets["entry"].get().strip()
            if not widgets["include"].get():
                excluded.append(old_name)
            else:
                rename_map[old_name] = new_name
        
        self._on_close = None 
        self.on_confirm(rename_map, excluded, self.assignments)
        self.destroy()

class ManualAssignmentWindow(ctk.CTkToplevel):
    def __init__(self, parent, manual_docs, kept_categories, on_finalize):
        super().__init__(parent)
        self.title("Manuelle Nachbearbeitung")
        self.geometry("800x600")
        self.manual_docs = manual_docs
        self.kept_categories = sorted(kept_categories)
        self.on_finalize = on_finalize
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Schritt 2: Dateien manuell zuordnen", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=20)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Unklare Zuordnungen")
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        self.doc_widgets = []
        for doc_id, data in manual_docs.items():
            frame = ctk.CTkFrame(self.scroll_frame)
            frame.pack(fill="x", pady=5, padx=5)
            
            # Prioritize title over filename
            display_name = data.get("title") or data.get("filename")
            ctk.CTkLabel(frame, text=display_name, width=250, anchor="w").pack(side="left", padx=5)
            
            # Category Dropdown - Only KEPT ones
            initial_val = data["matches"][0][0] if data["matches"][0][0] in self.kept_categories else self.kept_categories[0] if self.kept_categories else "_nicht_zugeordnet"
            cat_var = ctk.StringVar(value=initial_val)
            cb = ctk.CTkComboBox(frame, values=self.kept_categories + ["_nicht_zugeordnet"], variable=cat_var, width=200)
            cb.pack(side="left", padx=5)
            
            # Sub-Subject Entry
            sub_entry = ctk.CTkEntry(frame, width=150)
            sub_entry.insert(0, data.get("top_word", "Allgemein"))
            sub_entry.pack(side="left", padx=5)
            
            self.doc_widgets.append({"id": doc_id, "cat_var": cat_var, "sub_entry": sub_entry})

        self.btn_finalize = ctk.CTkButton(self, text="Sortiervorgang jetzt starten", command=self._finalize)
        self.btn_finalize.grid(row=2, column=0, pady=20)
        
        self.after(100, self.lift)
        self.grab_set()

    def _finalize(self):
        final_assignments = {}
        for item in self.doc_widgets:
            final_assignments[item["id"]] = {
                "cat": item["cat_var"].get(),
                "subcat": item["sub_entry"].get()
            }
        self.on_finalize(final_assignments)
        self.destroy()

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
        """Thread-safe logging to the text box using after()."""
        def _log():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        self.after(0, _log)
        
    def set_progress(self, value, eta_text=""):
        """Thread-safe progress updates using after()."""
        def _update():
            self.progressbar.set(value)
            if eta_text:
                self.eta_label.configure(text=eta_text)
        self.after(0, _update)

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
        self.log("[*] Starte interaktive Thematische Sortierung...")
        self.progressbar.set(0)
        self.eta_label.configure(text="Berechne Vorschau...")
        
        def worker():
            try:
                counts, assignments = sorter.get_sorting_preview(log_callback=self.log)
                if not assignments:
                    self.log("[!] Keine hydrierten Dokumente zum Sortieren gefunden.")
                    self.set_progress(1.0, "Abgebrochen")
                    return
                
                # Switch to main thread for UI
                self.after(0, lambda: self._show_preview(counts, assignments))
            except Exception as e:
                self.log(f"[Error] Vorschau-Fehler: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _show_preview(self, counts, assignments):
        SortingPreviewWindow(self, counts, assignments, self._process_preview_selection)

    def _process_preview_selection(self, rename_map, excluded, assignments):
        self.log(f"[*] Kategorien bestätigt. {len(excluded)} ausgeschlossen.")
        self.eta_label.configure(text="Berechne Fallback...")
        
        def worker():
            # 1. Prepare Fallback & Split docs
            ready_assignments = {}
            manual_docs = {}
            kept_categories = list(rename_map.values())
            
            for doc_id, data in assignments.items():
                primary_cat = data["matches"][0][0]
                
                final_cat = None
                if primary_cat not in excluded and primary_cat != "Verschiedenes":
                    final_cat = rename_map.get(primary_cat, primary_cat)
                else:
                    # Try Fallback (matches 1 to n)
                    for m_cat, m_score in data["matches"][1:]:
                        if m_cat not in excluded and m_cat != "Verschiedenes":
                            final_cat = rename_map.get(m_cat, m_cat)
                            break
                
                if final_cat:
                    ready_assignments[doc_id] = {"cat": final_cat, "subcat": data["top_word"]}
                else:
                    manual_docs[doc_id] = data

            # Switch to UI thread to show next step
            self.after(0, lambda: self._show_manual_or_finalize(ready_assignments, manual_docs, kept_categories))

        threading.Thread(target=worker, daemon=True).start()

    def _show_manual_or_finalize(self, ready_assignments, manual_docs, kept_categories):
        if manual_docs:
            self.log(f"[*] {len(manual_docs)} Dokumente benötigen manuelle Zuordnung.")
            ManualAssignmentWindow(self, manual_docs, kept_categories, 
                                   lambda m_map: self._finalize_sorting(ready_assignments, m_map))
        else:
            self._finalize_sorting(ready_assignments, {})

    def _finalize_sorting(self, ready, manual):
        # Merge
        final_assignments = {**ready, **manual}
        self.log(f"[*] Starte finalen Sortiervorgang ({len(final_assignments)} Dateien)...")
        
        def worker():
            st = time.time()
            sorter.apply_sorting(final_assignments, log_callback=self.log, progress_callback=self.set_progress)
            m, s = divmod(int(time.time() - st), 60)
            self.set_progress(1.0, f"Fertig in {m}m {s}s")
        
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
