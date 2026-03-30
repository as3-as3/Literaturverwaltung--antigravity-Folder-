import os
import re
import time
import concurrent.futures
from pypdf import PdfReader
from ebooklib import epub
import ebooklib
import database

ISBN_REGEX = re.compile(r"(?i)ISBN(?:-1[03])?:?\s*((?:97[89][- ]?)?[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9xX])")
DOI_REGEX = re.compile(r"(?i)\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\b")

def clean_identifier(text):
    text = re.sub(r'(?i)ISBN(?:-1[03])?:?\s*', '', text)
    return re.sub(r'[^0-9X]', '', text.upper())

def extract_keywords(text):
    """Frequency-based keyword extraction with a portable stop-word filter."""
    if not text: return ""
    # Basics for German/English
    stopwords = {
        'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines', 'einen', 'einem',
        'und', 'oder', 'aber', 'denn', 'doch', 'mit', 'auf', 'aus', 'bei', 'bis', 'von', 'zu', 'vor',
        'nach', 'fr', 'gegen', 'ohne', 'um', 'durch', 'wie', 'als', 'ist', 'sind', 'war', 'waren',
        'the', 'and', 'or', 'but', 'for', 'with', 'on', 'at', 'by', 'from', 'up', 'out', 'in', 'of',
        'this', 'that', 'these', 'those', 'it', 'they', 'we', 'was', 'were', 'have', 'had', 'been',
        'abstrakt', 'einleitung', 'fazit', 'schluss', 'anhang', 'abstract', 'introduction', 'conclusion'
    }
    # Clean and split
    words = re.findall(r'\b[a-z--]{4,}\b', text.lower())
    counts = {}
    for w in words:
        if w not in stopwords:
            counts[w] = counts.get(w, 0) + 1
    
    # Sort and take top 15
    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [w for w, c in sorted_words[:15]]
    return ", ".join(top_keywords)

def extract_from_filename(filename):
    isbn = ISBN_REGEX.search(filename)
    doi = DOI_REGEX.search(filename)
    return (clean_identifier(isbn.group(1)) if isbn else None, doi.group(1) if doi else None)

def extract_from_pdf(filepath):
    isbn_val, doi_val = None, None
    try:
        reader = PdfReader(filepath)
        text = ""
        # Scan specifically the first 3 pages for speed and relevance
        scan_limit = min(3, len(reader.pages))
        for page_num in range(scan_limit):
            extracted = reader.pages[page_num].extract_text()
            if extracted: text += extracted + "\n"
        
        isbn = ISBN_REGEX.search(text)
        doi = DOI_REGEX.search(text)
        
        if isbn: isbn_val = clean_identifier(isbn.group(1))
        if doi: doi_val = doi.group(1)
            
    except Exception as e:
        print(f"PDF Error {filepath}: {e}")
    return isbn_val, doi_val, text # Return extracted text for keywords

def extract_from_epub(filepath):
    isbn_val, doi_val = None, None
    try:
        book = epub.read_epub(filepath)
        # Check metadata
        identifier_meta = book.get_metadata('DC', 'identifier')
        for identifier in identifier_meta:
            val = identifier[0]
            if 'isbn' in val.lower(): isbn_val = clean_identifier(val)
            if 'doi' in val.lower(): doi_val = val
        
        # Fallback to pure document string search
        if not isbn_val or not doi_val:
            text = ""
            items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            for item in items[:3]:
                text += item.get_content().decode('utf-8', errors='ignore')
            isbn = ISBN_REGEX.search(text)
            doi = DOI_REGEX.search(text)
            if not isbn_val and isbn: isbn_val = clean_identifier(isbn.group())
            if not doi_val and doi: doi_val = doi.group(1)
            
    except Exception as e:
        print(f"EPUB Error {filepath}: {e}")
    return isbn_val, doi_val, text # Return extracted text for keywords

def process_file_task(f, full_path, ext, status_callback=None):
    """Isolated task for Thread-Pool without DB lock risks."""
    if status_callback:
        status_callback(f, True)
        
    try:
        isbn, doi = extract_from_filename(f)
        
        # Deep extraction
        keywords = ""
        if not isbn or not doi:
            if ext == 'pdf':
                p_isbn, p_doi, text = extract_from_pdf(full_path)
            else:
                p_isbn, p_doi, text = extract_from_epub(full_path)
            
            if not isbn: isbn = p_isbn
            if not doi: doi = p_doi
            keywords = extract_keywords(text)
                
        return f, full_path, isbn, doi, keywords
    finally:
        if status_callback:
            status_callback(f, False)

def run_indexer(root_path, log_callback=None, progress_callback=None, status_callback=None):
    if log_callback: log_callback(f"Indexing (Multithreaded) started from {root_path}")
    
    # Pre-flight calculate total size for progress bar
    target_files = []
    for dirpath, _, filenames in os.walk(root_path):
        for f in filenames:
            ext = f.lower().split('.')[-1]
            if ext in ['pdf', 'epub']:
                target_files.append((dirpath, f, ext))
                
    total = len(target_files)
    if total == 0:
        if log_callback: log_callback("No files found.")
        return 0
        
    docs_inserted = 0
    futures = []
    
    # Use max CPU threads capped at 8 to prevent RAM saturation / freezing on heavy PCs
    workers = min(8, (os.cpu_count() or 1) * 2)
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for dirpath, f, ext in target_files:
            full_path = os.path.join(dirpath, f)
            futures.append(executor.submit(process_file_task, f, full_path, ext, status_callback))
            
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            completed = idx + 1
            if progress_callback:
                elapsed = time.time() - start_time
                avg_speed = elapsed / completed if completed > 0 else 0
                remaining = total - completed
                eta_sec = int(remaining * avg_speed)
                m, s = divmod(eta_sec, 60)
                h, m = divmod(m, 60)
                eta_str = f"Restzeit (Index): {h}h {m}m {s}s" if h > 0 else f"Restzeit (Index): {m}m {s}s"
                progress_callback(completed / float(total), eta_str)
            
            try:
                f, full_path, isbn, doi, keywords = future.result()
                rel_path = os.path.relpath(full_path, start=database.get_base_path())
                
                # DB Sync - Strictly Sequential here!
                query = '''
                    INSERT OR IGNORE INTO documents (relative_path, filename, isbn, doi, keywords, is_hydrated)
                    VALUES (?, ?, ?, ?, ?, 0)
                '''
                
                try:
                    database.execute_atomic(query, (rel_path, f, isbn, doi, keywords))
                    docs_inserted += 1
                except Exception:
                    pass
            except Exception as e:
                if log_callback: log_callback(f"Extraction error: {e}")
            
    if log_callback: log_callback(f"Indexing finished. {docs_inserted} pending documents found.")
    return docs_inserted

def reindex_unsorted_files(log_callback=None, progress_callback=None, status_callback=None):
    """Specifically re-scans documents that are NOT YET SORTED to pick up missing identifiers."""
    if log_callback: log_callback("[*] Starte Tiefen-Reindexierung für unsortierte Werke...")
    
    try:
        import sqlite3
        conn = sqlite3.connect(database.get_db_path())
        cursor = conn.cursor()
        # Find docs that are not sorted
        cursor.execute("SELECT id, relative_path, filename FROM documents WHERE is_sorted = 0")
        docs = cursor.fetchall()
        conn.close()
    except Exception as e:
        if log_callback: log_callback(f"DB Error: {e}")
        return
        
    if not docs:
        if log_callback: log_callback("[*] Keine unsortierten Werke zur Nachbearbeitung gefunden.")
        return
        
    total = len(docs)
    found_any = 0
    
    for idx, doc in enumerate(docs):
        doc_id, rel_path, filename = doc
        if status_callback:
            status_callback(filename, True)
            
        try:
            full_path = os.path.join(database.get_base_path(), rel_path)
            
            if not os.path.exists(full_path):
                continue
                
            ext = filename.lower().split('.')[-1]
            isbn, doi, text = None, None, ""
            
            if ext == 'pdf':
                isbn, doi, text = extract_from_pdf(full_path)
            elif ext == 'epub':
                isbn, doi, text = extract_from_epub(full_path)
            
            keywords = extract_keywords(text)
    
            # Update DB with new IDs and keywords
            database.execute_atomic(
                "UPDATE documents SET isbn = COALESCE(?, isbn), doi = COALESCE(?, doi), keywords = ?, is_hydrated = 0 WHERE id = ?",
                (isbn, doi, keywords, doc_id)
            )
            if isbn or doi or keywords:
                found_any += 1
                if log_callback: log_callback(f"[+] Update für {filename}: Neue Schlagworte & Identifier gefunden.")
        finally:
            if status_callback:
                status_callback(filename, False)
                
        if progress_callback:
            progress_callback((idx + 1) / float(total), f"Re-Index: {idx+1}/{total}")

    if log_callback: log_callback(f"[*] Re-Index abgeschlossen. {found_any} neue Identifier gefunden.")
