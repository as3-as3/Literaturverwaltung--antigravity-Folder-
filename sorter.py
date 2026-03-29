import shutil
import sqlite3
import csv
import time
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
            best_subj_idx = int(np.argmax(scores))
            best_score = scores[best_subj_idx]
            
            # Extract secondary defining keyword
            doc_dense = doc_vec.toarray()[0]
            top_word_idx = np.argsort(doc_dense)[::-1]
            top_word = "Allgemein"
            
            # Find the best keyword exclusively for this file
            for wi in top_word_idx:
                if doc_dense[wi] == 0:
                    break
                w = words[wi].capitalize()
                if len(w) > 3 and w.lower() not in LIBRARY_SUBJECTS[subject_keys[best_subj_idx]].split():
                    top_word = w
                    break
            
            # Sub-Subject mapping mechanism
            if best_score > 0.05:
                ebene1 = subject_keys[best_subj_idx]
            else:
                ebene1 = "Verschiedenes"
                
            assignments[doc_id] = [ebene1, top_word]
            
        return assignments
    except Exception as e:
        if log_callback: log_callback(f"Top-Clustering error: {e}")
        return {d[0]: ["_Manuelle_Pruefung"] for d in docs}

def run_sorter(log_callback=None, progress_callback=None):
    if log_callback: log_callback("Starting NLP Sorter...")
    
    conn = sqlite3.connect(database.get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT id, relative_path, filename, title, keywords FROM documents WHERE is_hydrated = 1")
    docs = cursor.fetchall()
    total_docs = len(docs)
    
    # Load CSV overrides
    overrides = []
    csv_path = os.path.join(database.get_base_path(), "folder_config.csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                for row in reader:
                    if len(row) >= 3:
                        overrides.append({
                            "target": row[0].strip(),
                            "include": [x.strip().lower() for x in row[1].split(",") if x.strip()],
                            "exclude": [x.strip().lower() for x in row[2].split(",") if x.strip()]
                        })
        except Exception as e:
            if log_callback: log_callback(f"CSV Parse Error: {e}")
            
    # Prepare documents for corpus clustering
    corpus_input = []
    for doc in docs:
        doc_id, rel_path, filename, title, keywords = doc
        text = f"{title or ''} {keywords or ''}".strip()
        corpus_input.append((doc_id, text, filename))
        
    doc_assignments = assign_thematic_path_corpus(corpus_input, log_callback)
    
    sorted_count = 0
    start_time = time.time()
    
    for idx, doc in enumerate(docs):
        completed = idx + 1
        if progress_callback:
            elapsed = time.time() - start_time
            avg_speed = elapsed / completed if completed > 0 else 0
            remaining = total_docs - completed
            eta_sec = int(remaining * avg_speed)
            m, s = divmod(eta_sec, 60)
            h, m = divmod(m, 60)
            eta_str = f"Restzeit (Sort): {h}h {m}m {s}s" if h > 0 else f"Restzeit (Sort): {m}m {s}s"
            progress_callback(completed / float(max(1, total_docs)), eta_str)
            
        doc_id, rel_path, filename, title, keywords = doc
        source_path = os.path.join(database.get_base_path(), rel_path)
        
        if not os.path.exists(source_path):
            continue
            
        text_content = f"{title or ''} {keywords or ''}".lower()
        
        # Override Matching
        matched_overrides = []
        for ov in overrides:
            has_inc = any(inc in text_content for inc in ov["include"]) if ov["include"] else False
            has_exc = any(exc in text_content for exc in ov["exclude"]) if ov["exclude"] else False
            if has_inc and not has_exc:
                matched_overrides.append(ov["target"])
                
        if matched_overrides:
            # Copy to ALL matching folders
            last_dest = None
            for targ in matched_overrides:
                t_dir = os.path.join(database.get_base_path(), targ)
                os.makedirs(t_dir, exist_ok=True)
                d_path = os.path.join(t_dir, filename)
                if source_path != d_path:
                    shutil.copy2(source_path, d_path)
                last_dest = d_path
                
            if source_path != last_dest:
                try: os.remove(source_path)
                except: pass
                
            sorted_count += 1
            final_rel = os.path.relpath(last_dest, database.get_base_path())
            cursor.execute("UPDATE documents SET relative_path = ? WHERE id = ?", (final_rel, doc_id))
            
        else:
            # Semantic Library Subject Classifier
            folders = doc_assignments.get(doc_id, ["_Manuelle_Pruefung"])
            t_dir = os.path.join(database.get_base_path(), *folders)
            os.makedirs(t_dir, exist_ok=True)
            d_path = os.path.join(t_dir, filename)
            
            if source_path != d_path:
                shutil.move(source_path, d_path)
                
            sorted_count += 1
            final_rel = os.path.relpath(d_path, database.get_base_path())
            cursor.execute("UPDATE documents SET relative_path = ? WHERE id = ?", (final_rel, doc_id))
            
    conn.commit()
    conn.close()
    
    if log_callback: log_callback(f"Sorting logic completed. Sorted {sorted_count} files/copies.")
    return sorted_count
