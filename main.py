import sys
from ui import APLMainWindow, apply_theme
import database

def main():
    # 1. Initialize SQLite Database & apply schema
    database.init_db()

    # 2. Setup GUI with requested theme
    apply_theme()
    app = APLMainWindow()
    
    # Optional: Load icon if built
    # app.iconbitmap("path_to_icon.ico")
    
    app.log(f"[OK] SQLite Portable Base Path: {database.get_base_path()}")
    app.log("[OK] FTS5 Engine Active and Tables Synced.")
    
    # 3. Start Window Loop
    app.mainloop()

if __name__ == "__main__":
    main()
