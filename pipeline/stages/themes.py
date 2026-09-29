import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import text
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances
import numpy as np

from pipeline.db import engine, execute_sql
from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool
from pipeline.config import GEMINI_EXTRACT_MODEL, GEMINI_API_KEYS, GEMINI_RPM_PER_KEY, PROMPTS_DIR

logger = logging.getLogger(__name__)

class ThemeNaming(BaseModel):
    name: str
    description: str

def run_themes() -> dict:
    pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
    client = GeminiClient(key_pool=pool, model_id=GEMINI_EXTRACT_MODEL)
    
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM themes"))
    
    with open(PROMPTS_DIR / "name_themes_v1.md", "r", encoding="utf-8") as f:
        theme_prompt_template = f.read()
    
    reasons = execute_sql("""
        SELECT sr.id, sr.text, sr.embedding, r.scope, r.author_hash, r.source, s.outcome
        FROM signal_reasons sr
        JOIN signals s ON sr.signal_id = s.signal_id
        JOIN raw_records r ON s.record_id = r.record_id
        WHERE sr.embedding IS NOT NULL AND s.is_duplicate = FALSE AND s.is_signal = TRUE
    """)
    
    if not reasons:
        return {"processed": 0, "themes_created": 0}
        
    counts = {"processed": len(reasons), "themes_created": 0}
    
    for scope in ['core', 'adjacent']:
        scope_reasons = [r for r in reasons if r['scope'] == scope]
        if len(scope_reasons) < 5:
            continue
            
        embeddings = []
        for r in scope_reasons:
            emb = r['embedding']
            if isinstance(emb, str):
                emb = json.loads(emb)
            embeddings.append(emb)
        embeddings = np.array(embeddings)
        dist_matrix = cosine_distances(embeddings)
        
        print(f"Clustering {scope} reasons...")
        # Agglomerative clustering with distance threshold
        clustering = AgglomerativeClustering(
            n_clusters=None, distance_threshold=0.35, metric='precomputed', linkage='average'
        )
        labels = clustering.fit_predict(dist_matrix)
        n_clusters = clustering.n_clusters_
        print(f"Found {n_clusters} clusters")
        
        for i in range(n_clusters):
            cluster_reasons = [scope_reasons[j] for j in range(len(scope_reasons)) if labels[j] == i]
            distinct_authors = len(set(r['author_hash'] for r in cluster_reasons))
            
            if distinct_authors < 2:
                # Assign to 'Other'
                with engine.begin() as conn:
                    for r in cluster_reasons:
                        conn.execute(text("UPDATE signal_reasons SET theme_id = 'other' WHERE id = :id"), {"id": r['id']})
                continue
                
            # Compute stats
            signal_count = len(cluster_reasons)
            sources = {}
            for r in cluster_reasons:
                sources[r['source']] = sources.get(r['source'], 0) + 1
            severe_count = sum(1 for r in cluster_reasons if r['outcome'] in ('gave_up', 'still_searching', 'believes_lost'))
            severe_share = severe_count / signal_count if signal_count > 0 else 0
            rank_score = distinct_authors * (1 + severe_share)
            
            if distinct_authors >= 30:
                ev_str = "strong"
            elif distinct_authors >= 15:
                ev_str = "directional"
            else:
                ev_str = "anecdotal"
                
            # Sample for naming
            sample_texts = list(set([r['text'] for r in cluster_reasons]))[:25]
            prompt = theme_prompt_template.replace("{{REASONS_JSON}}", json.dumps(sample_texts))
            
            try:
                res = client.generate(prompt=prompt, response_schema=ThemeNaming)
                theme_id = scope + "_" + res['name'].replace(" ", "_").lower()
            except Exception as e:
                logger.error(f"Error generating theme name: {e}. Using fallback.")
                res = {"name": f"Mock Theme {scope} {i}", "description": f"Fallback description for {scope} theme {i}"}
                theme_id = scope + f"_mock_theme_{i}"
            print(f"Saving theme {theme_id}...")
                
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO themes (id, scope, name, description, signals, distinct_authors, sources_count, severe_share, rank_score, evidence_strength, mixes)
                        VALUES (:tid, :scp, :nm, :desc, :sig, :da, :src, :ss, :rs, :es, :mix)
                    """),
                    {
                        "tid": theme_id, "scp": scope, "nm": res['name'], "desc": res['description'],
                        "sig": signal_count, "da": distinct_authors, "src": len(sources.keys()),
                        "ss": severe_share, "rs": rank_score, "es": ev_str, "mix": json.dumps({"sources": sources})
                    }
                )
                for r in cluster_reasons:
                    conn.execute(text("UPDATE signal_reasons SET theme_id = :tid WHERE id = :id"), {"tid": theme_id, "id": r['id']})
            
            counts["themes_created"] += 1
    return counts
