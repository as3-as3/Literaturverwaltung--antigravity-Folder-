import sqlite3
import os
import sys

def get_base_path() -> str:
    """Returns the base path, either from where PyInstaller extracted to, or local file dir."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_db_path() -> str:
    return os.path.join(get_base_path(), "library.db")

def init_db():
    """Initializes the SQLite database with FTS5 and standard metadata fields."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    
    # Robustness rules as promised
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relative_path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            title TEXT,
            author TEXT,
            year TEXT,
            isbn TEXT,
            doi TEXT,
            keywords TEXT,
            is_hydrated INTEGER DEFAULT 0,
            is_sorted INTEGER DEFAULT 0,
            content_hash TEXT
        )
    ''')
    
    # Migration: Add is_sorted if missing
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN is_sorted INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists
    
    # Create the Virtual Table for fast NLP searching (FTS5)
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, author, keywords, content="documents", content_rowid="id"
        )
    ''')
    
    # Triggers to keep FTS virtual table in sync with standard table automatically
    cursor.executescript('''
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, author, keywords) 
            VALUES (new.id, new.title, new.author, new.keywords);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, author, keywords) 
            VALUES('delete', old.id, old.title, old.author, old.keywords);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, author, keywords) 
            VALUES('delete', old.id, old.title, old.author, old.keywords);
            INSERT INTO documents_fts(rowid, title, author, keywords) 
            VALUES (new.id, new.title, new.author, new.keywords);
        END;
    ''')
    
    conn.commit()
    conn.close()

def execute_atomic(query: str, parameters: tuple = ()):
    """Executes a query using atomic transactions."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    
    try:
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.cursor()
        cursor.execute(query, parameters)
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database Error: {e}")
        raise e
    finally:
        conn.close()

def get_unhydrated_documents():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, relative_path, isbn, doi, keywords FROM documents WHERE is_hydrated = 0")
    docs = cursor.fetchall()
    conn.close()
    return docs

def update_document_metadata(doc_id: int, tags: dict, is_hydrated: int = 1):
    """Update metadata and flip hydration bit atomically."""
    # Build query dynamically skipping Nones inside tags dict if any
    set_clauses = ["is_hydrated = ?"]
    params = [is_hydrated]
    for k, v in tags.items():
        if k in ['title', 'author', 'year', 'keywords', 'isbn', 'doi'] and v is not None:
            set_clauses.append(f"{k} = ?")
            params.append(v)
            
    params.append(doc_id)
    query = f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = ?"
    execute_atomic(query, tuple(params))
