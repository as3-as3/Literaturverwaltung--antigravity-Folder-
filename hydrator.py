import time
import requests
import database
import concurrent.futures
import re

class SourceManager:
    """Manages API availability and circuit-breaker logic."""
    def __init__(self):
        self.paused_until = {}
        self.failure_counts = {}

    def is_available(self, name):
        until = self.paused_until.get(name, 0)
        return time.time() > until

    def report_success(self, name):
        self.failure_counts[name] = 0

    def report_failure(self, name, status_code):
        self.failure_counts[name] = self.failure_counts.get(name, 0) + 1
        # If rate limited (429) or multiple failures, pause for 60 seconds
        if status_code == 429 or self.failure_counts[name] >= 3:
            self.paused_until[name] = time.time() + 60
            return True # Just got paused
        return False

# Global manager instance
source_manager = SourceManager()

def fetch_crossref(doi=None, title=None):
    """Fetches from CrossRef via DOI or Title query. Returns (tags, status)."""
    if not source_manager.is_available("CrossRef"): return None, None
    try:
        url = f"https://api.crossref.org/works/{doi}" if doi else f"https://api.crossref.org/works?query.title={title}&rows=1"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            source_manager.report_success("CrossRef")
            msg = res.json().get('message', {})
            data = msg if doi else msg.get('items', [None])[0]
            if not data: return None, 200
            
            tags = {}
            if data.get('title'): tags['title'] = data.get('title')[0]
            authors = data.get('author', [])
            tags['author'] = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors])
            date_parts = data.get('issued', {}).get('date-parts', [[None]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                tags['year'] = str(date_parts[0][0])
            subj = data.get('subject', [])
            if subj: tags['keywords'] = ", ".join(subj)
            return tags, 200
        else:
            source_manager.report_failure("CrossRef", res.status_code)
            return None, res.status_code
    except: pass
    return None, None

def fetch_google_books(isbn=None, title=None):
    """Fetches from Google Books via ISBN or Title query. Returns (tags, status)."""
    if not source_manager.is_available("GoogleBooks"): return None, None
    try:
        q = f"isbn:{isbn}" if isbn else f'intitle:"{title}"'
        res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={q}", timeout=5)
        if res.status_code == 200:
            source_manager.report_success("GoogleBooks")
            items = res.json().get('items', [])
            if items:
                info = items[0].get('volumeInfo', {})
                tags = {
                    'title': info.get('title'),
                    'author': ", ".join(info.get('authors', [])),
                    'year': info.get('publishedDate', '')[:4],
                    'keywords': ", ".join(info.get('categories', []))
                }
                return tags, 200
            return None, 200
        else:
            source_manager.report_failure("GoogleBooks", res.status_code)
            return None, res.status_code
    except: pass
    return None, None

def fetch_openlibrary(isbn):
    """Fetches from OpenLibrary via ISBN."""
    if not source_manager.is_available("OpenLibrary"): return None, None
    try:
        res = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data", timeout=5)
        if res.status_code == 200:
            source_manager.report_success("OpenLibrary")
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
                return tags, 200
            return None, 200
        else:
            source_manager.report_failure("OpenLibrary", res.status_code)
            return None, res.status_code
    except: pass
    return None, None

def fetch_google_search_scrape(query):
    """Last resort: Scraping Google search results for identifiers or snippets."""
    if not source_manager.is_available("GoogleScrape"): return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x44) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        res = requests.get(f"https://www.google.com/search?q={query}", headers=headers, timeout=5)
        if res.status_code == 200:
            source_manager.report_success("GoogleScrape")
            html = res.text
            
            # Simple patterns to find identifiers in HTML or AI snippets
            isbn_match = re.search(r"97[89][- ]?[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9xX]", html)
            doi_match = re.search(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+", html)
            
            found = {}
            if isbn_match: found['isbn'] = isbn_match.group().replace("-", "").replace(" ", "")
            if doi_match: found['doi'] = doi_match.group()
            
            # If no identifiers but searching for title, we might pick up title from meta tags or H3s
            # This is fragile but better than nothing
            title_match = re.search(r"<title>(.*?) - Google Suche</title>", html)
            if title_match: found['title_hint'] = title_match.group(1)
            
            return found if found else None
        else:
            source_manager.report_failure("GoogleScrape", res.status_code)
    except: pass
    return None

def process_hydration_task(doc, log_callback=None, status_callback=None):
    doc_id, filename, rel_path, isbn, doi, existing_keywords = doc
    
    if status_callback:
        status_callback(filename, True)
    
    try:
        tags = {'title': None, 'author': None, 'year': None, 'keywords': None}
        
        if log_callback:
            if doi: log_callback(f"[*] Suche Metadata für DOI {doi}...")
            elif isbn: log_callback(f"[*] Suche Metadata für ISBN {isbn}...")
            else: log_callback(f"[*] Suche Metadata via Titel: {filename}...")

        # 1. Strategy: API Trials
        # DOI -> CrossRef
        if doi:
            res, status = fetch_crossref(doi=doi)
            if res: tags.update(res)
            elif status == 429:
                if log_callback: log_callback("[!] CrossRef pausiert (Rate-Limit).")
        
        # ISBN -> Google Books or OpenLibrary
        if (not tags['title'] or not tags['author']) and isbn:
            res, status = fetch_google_books(isbn=isbn)
            if res: tags.update(res)
            elif status == 429:
                if log_callback: log_callback("[!] GoogleBooks pausiert (Rate-Limit).")
                
            if not tags['title']:
                res, status = fetch_openlibrary(isbn)
                if res: tags.update(res)

        # 2. Strategy: Google Search Fallback (if APIs didn't deliver or are paused)
        if not tags['title'] or not tags['keywords']:
            search_query = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
            if doi: search_query += f" DOI {doi}"
            if isbn: search_query += f" ISBN {isbn}"
            
            fallback_data = fetch_google_search_scrape(search_query)
            if fallback_data:
                # If we found a NEW identifier in the fallback, try APIs one last time
                new_doi = fallback_data.get('doi')
                new_isbn = fallback_data.get('isbn')
                
                if new_doi and not doi:
                    res, _ = fetch_crossref(doi=new_doi)
                    if res: tags.update(res)
                if new_isbn and not isbn:
                    res, _ = fetch_google_books(isbn=new_isbn)
                    if res: tags.update(res)
                
                # If still no title, use the snippet hint
                if not tags['title'] and fallback_data.get('title_hint'):
                    tags['title'] = fallback_data['title_hint']

        # 3. Final Fallback: Title Search (Filename-based) directly via APIs
        if not tags['title']:
            search_title = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
            res, _ = fetch_google_books(title=search_title)
            if res:
                for k, v in res.items():
                    if not tags[k]: tags[k] = v
            
            if not tags['title']:
                res, _ = fetch_crossref(title=search_title)
                if res and res.get('title'):
                    for k, v in res.items():
                        if not tags[k]: tags[k] = v

        # Final logic: if title still missing, use initial filename
        if not tags['title']:
            tags['title'] = filename.rsplit('.', 1)[0]
        
        # Merge keywords: API + Extracted
        all_k = set()
        if existing_keywords:
            for k in existing_keywords.split(", "): all_k.add(k.strip())
        if tags['keywords']:
            for k in tags['keywords'].split(", "): all_k.add(k.strip())
        
        tags['keywords'] = ", ".join(sorted(list(all_k)))
        
        database.update_document_metadata(doc_id, tags, is_hydrated=1)
        if log_callback: log_callback(f"[OK] {filename} -> {tags['title']}")
        
    except Exception as e:
        if log_callback: log_callback(f"Error processing {filename}: {e}")
    finally:
        if status_callback:
            status_callback(filename, False)
            
    # Slight rate limit per worker behavior
    time.sleep(0.5)
    return True

def hydrate_documents(log_callback=None, progress_callback=None, status_callback=None):
    unhydrated = database.get_unhydrated_documents()
    total = len(unhydrated)
    if not unhydrated:
        if log_callback: log_callback("Keine Dokumente zur Hydrierung gefunden.")
        return
        
    if log_callback: log_callback(f"Starte beschleunigte Hydrierung ({total} Dokumente)...")
    
    start_time = time.time()
    
    # Use 4 parallel workers to balance speed and rate limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_hydration_task, doc, log_callback, status_callback): doc for doc in unhydrated}
        
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
