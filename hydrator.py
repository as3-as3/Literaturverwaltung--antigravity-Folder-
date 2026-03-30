import time
import requests
import database
import concurrent.futures

def fetch_crossref(doi=None, title=None):
    """Fetches from CrossRef via DOI or Title query."""
    try:
        url = f"https://api.crossref.org/works/{doi}" if doi else f"https://api.crossref.org/works?query.title={title}&rows=1"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            msg = res.json().get('message', {})
            data = msg if doi else msg.get('items', [None])[0]
            if not data: return None
            
            tags = {}
            if data.get('title'): tags['title'] = data.get('title')[0]
            authors = data.get('author', [])
            tags['author'] = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors])
            date_parts = data.get('issued', {}).get('date-parts', [[None]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                tags['year'] = str(date_parts[0][0])
            subj = data.get('subject', [])
            if subj: tags['keywords'] = ", ".join(subj)
            return tags
    except: pass
    return None

def fetch_google_books(isbn=None, title=None):
    """Fetches from Google Books via ISBN or Title query."""
    try:
        q = f"isbn:{isbn}" if isbn else title
        res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={q}", timeout=5)
        if res.status_code == 200:
            items = res.json().get('items', [])
            if items:
                info = items[0].get('volumeInfo', {})
                tags = {
                    'title': info.get('title'),
                    'author': ", ".join(info.get('authors', [])),
                    'year': info.get('publishedDate', '')[:4],
                    'keywords': ", ".join(info.get('categories', []))
                }
                return tags
    except: pass
    return None

def fetch_openlibrary(isbn):
    """Fetches from OpenLibrary via ISBN."""
    try:
        res = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data", timeout=5)
        if res.status_code == 200:
            data = res.json()
            key = f"ISBN:{isbn}"
            if key in data:
                book = data[key]
                tags = {
                    'title': book.get('title'),
                    'author': ", ".join([a.get('name', '') for a in book.get('authors', [])]),
                    'year': str(book.get('publish_date', ''))[:4],
                    'keywords': ", ".join([s.get('name', '') for s in book.get('subjects', [])])
                }
                return tags
    except: pass
    return None

def process_hydration_task(doc, log_callback=None):
    doc_id, filename, rel_path, isbn, doi = doc
    tags = {'title': None, 'author': None, 'year': None, 'keywords': None}
    
    if log_callback:
        if doi: log_callback(f"[*] Suche Metadata für DOI {doi}...")
        elif isbn: log_callback(f"[*] Suche Metadata für ISBN {isbn}...")
        else: log_callback(f"[*] Suche Metadata via Titel: {filename}...")

    # Strategy: Try high-quality sources first
    # 1. DOI -> CrossRef
    if doi:
        res = fetch_crossref(doi=doi)
        if res: tags.update(res)
    
    # 2. ISBN -> Google Books or OpenLibrary
    if (not tags['title'] or not tags['author']) and isbn:
        res = fetch_google_books(isbn=isbn)
        if res: tags.update(res)
        if not tags['title']:
            res = fetch_openlibrary(isbn)
            if res: tags.update(res)

    # 3. Fallback: Title Search (Filename-based)
    if not tags['title'] or not tags['keywords']:
        # Use filename as title hint
        search_title = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
        res = fetch_google_books(title=search_title)
        if res:
            # Merge: only overwrite if previous was empty
            for k, v in res.items():
                if not tags[k]: tags[k] = v
        
        if not tags['title']:
            res = fetch_crossref(title=search_title)
            if res and res.get('title'):
                for k, v in res.items():
                    if not tags[k]: tags[k] = v

    # Final logic: if title still missing, use filename
    if not tags['title']:
        tags['title'] = filename.rsplit('.', 1)[0]
    
    database.update_document_metadata(doc_id, tags, is_hydrated=1)
    if log_callback: log_callback(f"[OK] {filename} -> {tags['title']}")
    
    # Slight rate limit per worker behavior
    time.sleep(0.5)
    return True

def hydrate_documents(log_callback=None, progress_callback=None):
    unhydrated = database.get_unhydrated_documents()
    total = len(unhydrated)
    if not unhydrated:
        if log_callback: log_callback("Keine Dokumente zur Hydrierung gefunden.")
        return
        
    if log_callback: log_callback(f"Starte beschleunigte Hydrierung ({total} Dokumente)...")
    
    start_time = time.time()
    
    # Use 4 parallel workers to balance speed and rate limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_hydration_task, doc, log_callback): doc for doc in unhydrated}
        
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            completed = idx + 1
            if progress_callback:
                elapsed = time.time() - start_time
                avg_speed = elapsed / completed if completed > 0 else 0
                remaining = total - completed
                eta_sec = int(remaining * avg_speed)
                m, s = divmod(eta_sec, 60)
                progress_callback(completed / float(total), f"Restzeit (Web): {m}m {s}s")
                
            try:
                future.result()
            except Exception as e:
                if log_callback: log_callback(f"Hydration Error: {e}")

    if log_callback: log_callback(f"Hydrierung abgeschlossen.")
