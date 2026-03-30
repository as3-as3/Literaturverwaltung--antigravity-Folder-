import shutil
import sqlite3
import csv
import time
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import database

def get_stop_words():
    # Multi-language minimal stopword set
    return ["und", "die", "der", "das", "in", "zu", "mit", "von", "für", "ist", "nicht", "auch", "auf", 
            "ein", "eine", "einer", "sich", "als", "es", "wie", "bei", "im", "dem", "aus", "oder", "aber", 
            "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", "are"]

LIBRARY_SUBJECTS = {
    "Medizin & Anatomie": "medizin anatomie gesundheit körper krankheit arzt pflege chirurgie patient heilkunde therapie",
    "Soziologie & Gesellschaft": "soziologie gesellschaft sozial soziales menschen verhalten population interaktion",
    "Informatik & IT": "informatik it software programmierung rechner computer daten ki netzwerk algorithmus befehle",
    "Wirtschaft & Finanzen": "wirtschaft finanzen unternehmen management geld markt handel bwl vwl ökonomie",
    "Naturwissenschaften": "physik chemie biologie astronomie materie natur molekül atom wissenschaft reaktion",
    "Geschichte & Archäologie": "geschichte archäologie historisch antike mittelalter vergangenheit epoche krieg",
    "Recht & Jura": "recht jura gesetz anwalt gericht vertrag strafrecht verfassung richter legal",
    "Pädagogik & Bildung": "pädagogik bildung schule lernen unterricht erziehung lehrer didaktik wissen",
    "Kunst & Kultur": "kunst kultur architektur malerei musik film design werk kreatives",
    "Psychologie": "psychologie psyche geist verhalten seele kognition gefühl trauma emotion",
    "Mathematik & Statistik": "mathematik statistik algebra analysis geometrie wahrscheinlichkeitsrechnung zahlen formel",
    "Technik & Ingenieurwesen": "technik ingenieurwesen maschinenbau elektrik elektronik bauwesen mechanik",
    "Literatur & Sprachwissenschaft": "literatur sprache linguistik grammatik buch autor publizistik roman poesie",
    "Politik & Gesellschaft": "politik staat regierung demokratie wahl macht gesetzgebung partei",
    "Philosophie & Theologie": "philosophie theologie religion gott ethik moral glaube existenz religionen",
}

def assign_thematic_path_corpus(docs, log_callback=None):
    if not docs:
        return {}
        
    subject_keys = list(LIBRARY_SUBJECTS.keys())
    subject_texts = list(LIBRARY_SUBJECTS.values())
    
    # Text aggregation: doc_id, text, filename
    all_texts = subject_texts + [d[1] for d in docs]
    
    assignments = {}
    try:
        vec = TfidfVectorizer(stop_words=get_stop_words(), max_features=1000)
        tfidf_matrix = vec.fit_transform(all_texts)
        
        subject_vectors = tfidf_matrix[:len(subject_keys)]
        doc_vectors = tfidf_matrix[len(subject_keys):]
        
        similarities = cosine_similarity(doc_vectors, subject_vectors)
        words = vec.get_feature_names_out()
        
        for i, doc_vec in enumerate(doc_vectors):
            doc_id = docs[i][0]
            scores = similarities[i]
            
            # Get Top 5 matches
            top_indices = np.argsort(scores)[::-1][:5]
            matches = []
            for idx in top_indices:
                score = float(scores[idx])
                if score > 0.05: # Threshold for "good" match
                    matches.append((subject_keys[idx], score))
            
            # Default to Verschiedenes if no match
            if not matches:
                matches = [("Verschiedenes", 0.0)]
                
            # Extract secondary defining keyword
            doc_dense = doc_vec.toarray()[0]
            top_word_idx = np.argsort(doc_dense)[::-1]
            top_word = "Allgemein"
            
            # Find the best keyword exclusively for this file
            primary_cat = matches[0][0]
            primary_keywords = LIBRARY_SUBJECTS.get(primary_cat, "").lower().split()
            
            for wi in top_word_idx:
                if doc_dense[wi] == 0:
                    break
                w = words[wi].capitalize()
                if len(w) > 3 and w.lower() not in primary_keywords:
                    top_word = w
                    break
            
            assignments[doc_id] = {
                "matches": matches,
                "top_word": top_word,
                "filename": docs[i][2]
            }
            
        return assignments
    except Exception as e:
        if log_callback: log_callback(f"Top-Clustering error: {e}")
        return {d[0]: {"matches": [("_Manuelle_Pruefung", 0.0)], "top_word": "Fehler", "filename": d[2]} for d in docs}

def get_sorting_preview(log_callback=None):
    """Calculates assigned categories but does not move files."""
    if log_callback: log_callback("Scanning library for sorting preview...")
    
    try:
        conn = sqlite3.connect(database.get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT id, relative_path, filename, title, keywords FROM documents WHERE is_hydrated = 1")
        docs = cursor.fetchall()
        conn.close()
    except Exception as e:
        if log_callback: log_callback(f"DB Error: {e}")
        return {}, {}
    
    if not docs:
        return {}, {}
        
    corpus_input = []
    for doc in docs:
        doc_id, rel_path, filename, title, keywords = doc
        text = f"{title or ''} {keywords or ''} {filename}".strip()
        corpus_input.append((doc_id, text, filename))
        
    assignments = assign_thematic_path_corpus(corpus_input, log_callback)
    
    # Calculate counts for Summary by taking the FIRST match
    category_counts = {}
    for aid, data in assignments.items():
        main_cat = data["matches"][0][0]
        category_counts[main_cat] = category_counts.get(main_cat, 0) + 1
        
    return category_counts, assignments

def apply_sorting(final_map, log_callback=None, progress_callback=None):
    """final_map: {doc_id: {'cat': 'X', 'subcat': 'Y'}}"""
    if log_callback: log_callback(f"Starting physical sorting process for {len(final_map)} files...")
    
    try:
        conn = sqlite3.connect(database.get_db_path())
        cursor = conn.cursor()
        
        sorted_count = 0
        total = len(final_map)
        start_time = time.time()
        
        for idx, (doc_id, target) in enumerate(final_map.items()):
            completed = idx + 1
            if progress_callback:
                elapsed = time.time() - start_time
                avg_speed = elapsed / completed if completed > 0 else 0
                eta_sec = int((total - completed) * avg_speed)
                m, s = divmod(eta_sec, 60)
                progress_callback(completed / float(max(1, total)), f"Dauer: {m}m {s}s")
                
            cursor.execute("SELECT relative_path, filename FROM documents WHERE id = ?", (doc_id,))
            res = cursor.fetchone()
            if not res: continue
            rel_path, filename = res
            
            source_path = os.path.join(database.get_base_path(), rel_path)
            if not os.path.exists(source_path):
                continue
                
            t_cat = target['cat']
            t_sub = target.get('subcat', 'Allgemein')
            
            t_dir = os.path.join(database.get_base_path(), t_cat, t_sub)
            os.makedirs(t_dir, exist_ok=True)
            d_path = os.path.join(t_dir, filename)
            
            try:
                if source_path != d_path:
                    shutil.move(source_path, d_path)
                    
                final_rel = os.path.relpath(d_path, database.get_base_path())
                cursor.execute("UPDATE documents SET relative_path = ? WHERE id = ?", (final_rel, doc_id))
                sorted_count += 1
            except Exception as e:
                if log_callback: log_callback(f"Error moving {filename}: {e}")
                
        conn.commit()
        conn.close()
        if log_callback: log_callback(f"Sorting finished. {sorted_count} files moved/updated.")
        return sorted_count
    except Exception as e:
        if log_callback: log_callback(f"Critical Sort Error: {e}")
        return 0

def run_sorter(log_callback=None, progress_callback=None):
    """Legacy wrapper for auto-pipeline."""
    counts, assignments = get_sorting_preview(log_callback)
    if not assignments: return 0
    final_map = {doc_id: {'cat': data["matches"][0][0], 'subcat': data["top_word"]} 
                 for doc_id, data in assignments.items()}
    return apply_sorting(final_map, log_callback, progress_callback)
