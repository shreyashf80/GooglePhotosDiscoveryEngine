import logging
import re
from pathlib import Path
from pipeline.db import engine
from sqlalchemy import text
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Re-use model instance
_model = None

def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("Loading fastembed model BAAI/bge-small-en-v1.5...")
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model

def import_literature(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Literature file not found: {file_path}")

    content = path.read_text()
    
    # Split by '## '
    sections = re.split(r'^##\s+', content, flags=re.MULTILINE)
    if len(sections) > 1:
        sections = sections[1:] # Skip the intro before first ##
    else:
        sections = []

    sources = []
    for section in sections:
        lines = section.strip().split('\n')
        title = lines[0].strip()
        
        if title in ["How to read the eras", "Coverage map"]:
            continue

        source_text = "## " + section.strip()
        
        citation = ""
        link = ""
        era = ""
        tags = []
        
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("- **Citation:**"):
                citation = line_str.replace("- **Citation:**", "").strip()
            elif line_str.startswith("- **Link:**"):
                link = line_str.replace("- **Link:**", "").strip()
            elif line_str.startswith("- **era:**"):
                # E.g. "current (2024 to 2026)" -> era could be just "current" or full. Let's take the first word for grouping as requested "list of all sources grouped by era" but wait, the prompt says "show the era label everywhere a source appears". Taking the full string as era is safer or taking just the first word. Let's take the first word since "current (2024)" is grouped into "current".
                era_full = line_str.replace("- **era:**", "").strip()
                era = era_full.split()[0] if era_full else ""
            elif line_str.startswith("- **tags:**"):
                tags_str = line_str.replace("- **tags:**", "").strip()
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        source_id = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        
        sources.append({
            "id": source_id,
            "title": title,
            "citation": citation,
            "link": link,
            "era": era,
            "tags": tags,
            "text": source_text
        })
        
    if not sources:
        logger.info("No valid literature sections found.")
        return {"processed": 0}

    logger.info(f"Parsed {len(sources)} sources. Embedding...")
    model = _get_model()
    
    # Embed in batch
    texts = [s["text"] for s in sources]
    embeddings = list(model.embed(texts))
    
    logger.info("Inserting into database...")
    with engine.begin() as conn:
        # Clear existing
        conn.execute(text("DELETE FROM literature_chunks"))
        conn.execute(text("DELETE FROM literature_sources"))
        
        for source, emb in zip(sources, embeddings):
            conn.execute(
                text("""
                    INSERT INTO literature_sources (id, title, citation, link, era, tags)
                    VALUES (:id, :title, :citation, :link, :era, :tags)
                """),
                {
                    "id": source["id"],
                    "title": source["title"],
                    "citation": source["citation"],
                    "link": source["link"],
                    "era": source["era"],
                    "tags": source["tags"]
                }
            )
            
            vec_str = "[" + ",".join(str(float(v)) for v in emb) + "]"
            conn.execute(
                text("""
                    INSERT INTO literature_chunks (source_id, text, embedding)
                    VALUES (:source_id, :text, :emb)
                """),
                {
                    "source_id": source["id"],
                    "text": source["text"],
                    "emb": vec_str
                }
            )
            
    logger.info("Literature import complete.")
    return {"processed": len(sources)}
