import os
import re
import concurrent.futures
from pypdf import PdfReader
from ebooklib import epub
import ebooklib
import database

ISBN_REGEX = re.compile(r"(?i)ISBN(?:-1[03])?:?\s*(?=[-0-9xX ]{13,17})(?:97[89][- ]?)?[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9xX]")
DOI_REGEX = re.compile(r"(?i)\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b")

def clean_identifier(text):
    return re.sub(r'[^0-9X]', '', text.upper()) if text else None

def extract_from_filename(filename):
    isbn = ISBN_REGEX.search(filename)
    doi = DOI_REGEX.search(filename)
    return (clean_identifier(isbn.group()) if isbn else None, doi.group(1) if doi else None)

def extract_from_pdf(filepath):
    isbn_val, doi_val = None, None
    try:
        reader = PdfReader(filepath)
        text = ""
        for page_num in range(min(10, len(reader.pages))):
            extracted = reader.pages[page_num].extract_text()
            if extracted: text += extracted + "\n"
        
        isbn = ISBN_REGEX.search(text)
        doi = DOI_REGEX.search(text)
        
        if isbn: isbn_val = clean_identifier(isbn.group())
        if doi: doi_val = doi.group(1)
            
    except Exception as e:
        print(f"PDF Error {filepath}: {e}")
    return isbn_val, doi_val

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
    return isbn_val, doi_val

def process_file_task(f, full_path, ext):
    """Isolated task for Thread-Pool without DB lock risks."""
    isbn, doi = extract_from_filename(f)
    
    # Deep extraction
    if not isbn or not doi:
        if ext == 'pdf':
            p_isbn, p_doi = extract_from_pdf(full_path)
        else:
            p_isbn, p_doi = extract_from_epub(full_path)
        
        if not isbn: isbn = p_isbn
        if not doi: doi = p_doi
            
    return f, full_path, isbn, doi

def run_indexer(root_path, log_callback=None, progress_callback=None):
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
    
    # Use max CPU threads * 2 for efficient IO/CPU overlapping
    workers = min(32, (os.cpu_count() or 1) * 2)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for dirpath, f, ext in target_files:
            full_path = os.path.join(dirpath, f)
            futures.append(executor.submit(process_file_task, f, full_path, ext))
            
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            if progress_callback: progress_callback((idx + 1) / float(total))
            
            try:
                f, full_path, isbn, doi = future.result()
                rel_path = os.path.relpath(full_path, start=database.get_base_path())
                
                # DB Sync - Strictly Sequential here!
                query = '''
                    INSERT OR IGNORE INTO documents (relative_path, filename, isbn, doi, is_hydrated)
                    VALUES (?, ?, ?, ?, 0)
                '''
                
                try:
                    database.execute_atomic(query, (rel_path, f, isbn, doi))
                    docs_inserted += 1
                except Exception:
                    pass
            except Exception as e:
                if log_callback: log_callback(f"Extraction error: {e}")
            
    if log_callback: log_callback(f"Indexing finished. {docs_inserted} pending documents found.")
    return docs_inserted
