import time
import requests
import database

def hydrate_documents(log_callback=None, progress_callback=None):
    unhydrated = database.get_unhydrated_documents()
    total = len(unhydrated)
    if log_callback: log_callback(f"Found {total} documents pending hydration.")
    
    for idx, doc in enumerate(unhydrated):
        if progress_callback: progress_callback(idx / float(max(1, total)))
        doc_id, filename, rel_path, isbn, doi = doc
        tags = {'title': None, 'author': None, 'year': None, 'keywords': None}
        
        try:
            # 1. CrossRef for DOI
            if doi:
                res = requests.get(f"https://api.crossref.org/works/{doi}", timeout=5)
                if res.status_code == 200:
                    data = res.json().get('message', {})
                    if data.get('title'): tags['title'] = data.get('title')[0]
                    
                    authors = data.get('author', [])
                    tags['author'] = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors])
                    
                    date_parts = data.get('issued', {}).get('date-parts', [[None]])
                    if date_parts and date_parts[0] and date_parts[0][0]:
                        tags['year'] = str(date_parts[0][0])
                    
                    # Some keywords based on subjects
                    subj = data.get('subject', [])
                    if subj: tags['keywords'] = ", ".join(subj)
                    
            # 2. OpenLibrary for ISBN
            if isbn and not tags.get('title'):
                res = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data", timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    key = f"ISBN:{isbn}"
                    if key in data:
                        book = data[key]
                        tags['title'] = book.get('title')
                        tags['author'] = ", ".join([a.get('name', '') for a in book.get('authors', [])])
                        tags['year'] = book.get('publish_date')
                        tags['keywords'] = ", ".join([s.get('name', '') for s in book.get('subjects', [])])
            
            # Atomically commit and freeze hydration to prevent API hammering
            database.update_document_metadata(doc_id, tags, is_hydrated=1)
            
            if log_callback: log_callback(f"[Hydrated] {filename} -> {tags.get('title')}")
            
            # Rate limiting as required
            time.sleep(1.5)
            
        except Exception as e:
            if log_callback: log_callback(f"Error hydrating '{filename}': {e}")
            database.update_document_metadata(doc_id, {}, is_hydrated=1) # Mark checked even if failed to stop loops
            time.sleep(1.5)
            
    if log_callback: log_callback(f"Hydration complete.")
