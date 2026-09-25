"""
Pipeline CLI — Typer commands for all pipeline stages.
Stubs for future milestones; `status` and `migrate` fully implemented for M0.

References:
  FR-22  — CLI command list
  FR-23  — status prints counts per status, per source, DB size
  DR-4   — migrations versioned in /db/migrations
  DR-5   — pg_database_size exposed
  NFR-4  — warn if DB > 300 MB
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

# Ensure project root is on the path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from pipeline.config import get_time_cutoff, SOURCE_CAPS, APIFY_TOKEN, SERPAPI_KEY, YOUTUBE_API_KEY
from pipeline.sources.reddit import RedditSource
from pipeline.sources.playstore import PlayStoreSource
from pipeline.sources.appstore import AppStoreSource
from pipeline.sources.youtube import YouTubeSource
from pipeline.sources.csv_import import CSVSource
from pipeline.stages.dedup import run_dedup
from pipeline.stages.language import run_language_detection
from pipeline.db import engine
from sqlalchemy import text

def redact_secrets(msg: str) -> str:
    """Redact API keys from exception messages (NFR-5, NFR-6)."""
    if not msg:
        return msg
    from pipeline.config import GEMINI_API_KEYS
    secrets = [APIFY_TOKEN, SERPAPI_KEY, YOUTUBE_API_KEY] + GEMINI_API_KEYS
    for secret in secrets:
        if secret and len(secret) > 4:
            msg = msg.replace(secret, "***REDACTED***")
    return msg

app = typer.Typer(
    name="pipeline",
    help="Recall Gap Discovery Engine — data processing pipeline CLI",
)

# Configure structured logging (NFR-6)
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


# ============================================================
# T-0.6: migrate command
# ============================================================

@app.command()
def migrate() -> None:
    """Apply all SQL migrations in order against DATABASE_URL_DIRECT (DR-4)."""
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")

    db_url = os.environ.get("DATABASE_URL_DIRECT")
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        typer.echo("Error: DATABASE_URL_DIRECT or DATABASE_URL must be set", err=True)
        raise typer.Exit(1)

    import psycopg2

    migrations_dir = _project_root / "db" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        typer.echo("No migration files found.")
        return

    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        typer.echo(f"Error: Failed to connect to database ({type(e).__name__})", err=True)
        raise typer.Exit(1)

    try:
        # Create schema_migrations tracking table if it doesn't exist
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("SELECT version FROM schema_migrations;")
            applied_versions = {row[0] for row in cur.fetchall()}
        conn.commit()

        for mf in migration_files:
            if mf.name in applied_versions:
                typer.echo(f"  - {mf.name} already applied (skipping)")
                continue

            typer.echo(f"Applying {mf.name}...")
            sql = mf.read_text()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s);",
                        (mf.name,),
                    )
                conn.commit()
                typer.echo(f"  ✓ {mf.name} applied")
            except Exception as e:
                conn.rollback()
                typer.echo(f"  ✗ {mf.name} failed: {e}", err=True)
                conn.close()
                raise typer.Exit(1)

        conn.close()
        typer.echo("All migrations applied successfully.")
    except Exception as e:
        typer.echo(f"Error during migration execution ({type(e).__name__}): {e}", err=True)
        try:
            conn.close()
        except Exception:
            pass
        raise typer.Exit(1)


# ============================================================
# T-0.12: status command (fully implemented)
# ============================================================

@app.command()
def status() -> None:
    """
    Print pipeline status: counts per status, per source, and DB size (FR-23, DR-5).
    Warns if DB size > 300 MB (NFR-4).
    """
    from pipeline.db import execute_sql, get_db_size_bytes
    from shared.constants import STORAGE_LIMIT_BYTES, STORAGE_WARN_BYTES

    typer.echo("=" * 60)
    typer.echo("  Recall Gap Discovery Engine — Pipeline Status")
    typer.echo("=" * 60)

    try:
        # Counts per status
        typer.echo("\n📊 Records by status:")
        rows = execute_sql(
            "SELECT status, COUNT(*) as count FROM raw_records GROUP BY status ORDER BY status"
        )
        total_records = 0
        if rows:
            for row in rows:
                typer.echo(f"  {row['status']:20s} {row['count']:>8,d}")
                total_records += row["count"]
        else:
            typer.echo("  (no records)")
        typer.echo(f"  {'TOTAL':20s} {total_records:>8,d}")

        # Counts per source
        typer.echo("\n📡 Records by source:")
        rows = execute_sql(
            "SELECT source, COUNT(*) as count FROM raw_records GROUP BY source ORDER BY count DESC"
        )
        if rows:
            for row in rows:
                typer.echo(f"  {row['source']:20s} {row['count']:>8,d}")
        else:
            typer.echo("  (no records)")

        # Episode counts
        typer.echo("\n🎬 Episodes:")
        rows = execute_sql("SELECT COUNT(*) as count FROM episodes")
        episode_count = rows[0]["count"] if rows else 0
        typer.echo(f"  Total episodes: {episode_count:,d}")

        # Hypothesis status
        typer.echo("\n🔬 Hypotheses:")
        rows = execute_sql(
            "SELECT hypothesis_id, title, status, evidence_strength FROM hypotheses ORDER BY hypothesis_id"
        )
        if rows:
            for row in rows:
                typer.echo(
                    f"  {row['hypothesis_id']:4s} {row['title']:40s} "
                    f"[{row['status']}] ({row['evidence_strength']})"
                )
        else:
            typer.echo("  (no hypotheses seeded yet)")

        # Pipeline runs
        typer.echo("\n🔄 Recent pipeline runs:")
        rows = execute_sql(
            "SELECT stage, source, status, started_at, ended_at "
            "FROM pipeline_runs ORDER BY started_at DESC LIMIT 5"
        )
        if rows:
            for row in rows:
                source = row.get("source") or ""
                typer.echo(
                    f"  {row['stage']:12s} {source:12s} [{row['status']}] "
                    f"{row['started_at']}"
                )
        else:
            typer.echo("  (no runs yet)")

        # Database size
        typer.echo("\n💾 Database storage:")
        db_bytes = get_db_size_bytes()
        db_mb = db_bytes / (1024 * 1024)
        limit_mb = STORAGE_LIMIT_BYTES / (1024 * 1024)
        percent = (db_bytes / STORAGE_LIMIT_BYTES) * 100

        bar_width = 30
        filled = int(bar_width * percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        typer.echo(f"  [{bar}] {db_mb:.1f} MB / {limit_mb:.0f} MB ({percent:.1f}%)")

        if db_bytes > STORAGE_WARN_BYTES:
            typer.echo(
                f"  ⚠️  WARNING: Database exceeds {STORAGE_WARN_BYTES / (1024*1024):.0f} MB threshold!",
            )

        typer.echo()
    except Exception as e:
        typer.echo(f"Error fetching status from database ({type(e).__name__}): {e}", err=True)
        raise typer.Exit(1)


# ============================================================
# T-0.13: seed-hypotheses command
# ============================================================

@app.command(name="seed-hypotheses")
def seed_hypotheses() -> None:
    """Seed the 8 starting hypotheses into the hypotheses table (FR-71)."""
    from datetime import datetime, timezone

    from pipeline.db import engine
    from sqlalchemy import text

    hypotheses = [
        ("H1", "Relational anchoring", "Users remember photos relative to other life events more than by dates, and search can't use event anchors."),
        ("H2", "Provenance amnesia", "Photos received from others are the hardest to find because users remember the sender or conversation, which search doesn't index."),
        ("H3", "Vocabulary mismatch", "Users describe photos by meaning or purpose while the index uses visual labels."),
        ("H4", "Needle in a flood", "For recurring subjects, recall works but ranking fails and users scroll through near-duplicates."),
        ("H5", "Utility photos are a distinct segment", "Screenshots, receipts, documents and medicines are remembered by task and text, not visuals."),
        ("H6", "Time drift grows with age", "Date memory gets less precise for older photos while date filters assume precision."),
        ("H7", "Refinement dead end", "Users try a few queries, cannot narrow results, and fall back to scrolling."),
        ("H8", "Silent abandonment", "After repeated failures, users stop using search and rely on scrolling or asking others to resend."),
    ]

    now = datetime.now(timezone.utc)

    try:
        with engine.begin() as conn:
            for hid, title, statement in hypotheses:
                conn.execute(
                    text("""
                        INSERT INTO hypotheses (hypothesis_id, title, statement, status,
                                                support_count, contradict_count, relevant_count,
                                                evidence_strength, computed_at)
                        VALUES (:hid, :title, :statement, 'insufficient_data',
                                0, 0, 0, 'anecdotal', :now)
                        ON CONFLICT (hypothesis_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            statement = EXCLUDED.statement
                    """),
                    {"hid": hid, "title": title, "statement": statement, "now": now},
                )
        typer.echo(f"Seeded {len(hypotheses)} hypotheses.")
    except Exception as e:
        typer.echo(f"Error seeding hypotheses to database ({type(e).__name__}): {e}", err=True)
        raise typer.Exit(1)


# ============================================================
# T-0.14: seed-capabilities command
# ============================================================

@app.command(name="seed-capabilities")
def seed_capabilities() -> None:
    """Seed capability reference from YAML file (FR-86)."""
    import yaml
    from pipeline.db import engine
    from sqlalchemy import text

    yaml_path = _project_root / "db" / "seeds" / "capability_reference.yaml"
    if not yaml_path.exists():
        typer.echo(f"Error: {yaml_path} not found", err=True)
        raise typer.Exit(1)

    with open(yaml_path) as f:
        capabilities = yaml.safe_load(f)

    try:
        with engine.begin() as conn:
            for cap in capabilities:
                conn.execute(
                    text("""
                        INSERT INTO capability_reference (cue_type, searchable, note, verified_how, verified_at)
                        VALUES (:cue_type, :searchable, :note, :verified_how, :verified_at)
                        ON CONFLICT (cue_type) DO UPDATE SET
                            searchable = EXCLUDED.searchable,
                            note = EXCLUDED.note,
                            verified_how = EXCLUDED.verified_how,
                            verified_at = EXCLUDED.verified_at
                    """),
                    cap,
                )
        typer.echo(f"Seeded {len(capabilities)} capability reference entries.")
    except Exception as e:
        typer.echo(f"Error seeding capabilities to database ({type(e).__name__}): {e}", err=True)
        raise typer.Exit(1)


# ============================================================
# Helpers
# ============================================================

def _log_run(stage: str, source: str, started_at: datetime, ended_at: datetime, counts: dict, errors: list):
    status = 'failed' if errors else 'completed'
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_runs (run_id, stage, source, started_at, ended_at, counts, errors, status)
                VALUES (:run_id, :stage, :source, :started_at, :ended_at, :counts, :errors, :status)
            """),
            {
                "run_id": str(uuid.uuid4()),
                "stage": stage,
                "source": source,
                "started_at": started_at,
                "ended_at": ended_at,
                "counts": json.dumps(counts),
                "errors": json.dumps(errors),
                "status": status
            }
        )

def _upsert_records(records: list):
    if not records:
        return
    with engine.begin() as conn:
        for r in records:
            extra = json.dumps(r.extra) if r.extra else None
            conn.execute(
                text("""
                    INSERT INTO raw_records (record_id, source, item_type, product, url, author_hash, created_at, text, extra, status)
                    VALUES (:id, :source, :type, :prod, :url, :hash, :dt, :txt, :ext, 'raw')
                    ON CONFLICT (record_id) DO UPDATE SET
                        text = CASE WHEN raw_records.status = 'raw' THEN EXCLUDED.text ELSE raw_records.text END,
                        extra = EXCLUDED.extra
                """),
                {
                    "id": r.record_id, "source": r.source.value, "type": r.item_type.value,
                    "prod": r.product.value, "url": r.url, "hash": r.author_hash,
                    "dt": r.created_at, "txt": r.text, "ext": extra
                }
            )


# ============================================================
# M1: Ingest commands
# ============================================================

@app.command()
def ingest(source: str = typer.Option("all", help="Source name or 'all'")) -> None:
    """Ingest records from sources (M1)."""
    sources_to_run = []
    if source == "all" or source == "reddit":
        sources_to_run.append(("reddit", RedditSource(APIFY_TOKEN)))
    if source == "all" or source == "playstore":
        sources_to_run.append(("playstore", PlayStoreSource()))
    if source == "all" or source == "appstore":
        sources_to_run.append(("appstore", AppStoreSource(SERPAPI_KEY)))
    if source == "all" or source == "youtube":
        sources_to_run.append(("youtube", YouTubeSource(YOUTUBE_API_KEY)))

    for name, src in sources_to_run:
        typer.echo(f"Ingesting from {name}...")
        started_at = datetime.now(timezone.utc)
        cap = SOURCE_CAPS.get(name, 1000)
        try:
            records = src.fetch(get_time_cutoff(), cap)
            if hasattr(src, 'errors') and src.errors:
                errors = [redact_secrets(e) for e in src.errors]
            else:
                errors = []
                
            _upsert_records(records)
            ended_at = datetime.now(timezone.utc)
            counts = {"fetched": len(records), "stored": len(records)}
            
            _log_run("ingest", name, started_at, ended_at, counts, errors)
            typer.echo(f"  ✓ {name} ingested {len(records)} records")
        except Exception as e:
            err_msg = redact_secrets(str(e))
            typer.echo(f"  ✗ Error ingesting {name}: {err_msg}", err=True)
            _log_run("ingest", name, started_at, datetime.now(timezone.utc), {"fetched": 0, "stored": 0}, [err_msg])


@app.command()
def dedup() -> None:
    """Deduplicate raw records (M1)."""
    started_at = datetime.now(timezone.utc)
    counts = run_dedup()
    lang_counts = run_language_detection()
    ended_at = datetime.now(timezone.utc)
    
    counts.update({"language_" + k: v for k, v in lang_counts.items()})
    _log_run("dedup", "all", started_at, ended_at, counts, [])
    typer.echo(f"Dedup and language detection complete: {counts}")


# ============================================================
# M2: Filter command (T-2.1, T-2.3)
# ============================================================

@app.command(name="filter")
def filter_cmd(
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Process at most N records"),
) -> None:
    """Run Stage 1 relevance filter (M2). Keyword prefilter + Gemini classification."""
    from pipeline.stages.filter import run_filter

    typer.echo("Running Stage 1: Relevance filter...")
    if limit:
        typer.echo(f"  (limited to {limit} records)")

    counts = run_filter(limit=limit)

    typer.echo("\n📊 Filter results:")
    typer.echo(f"  Records processed:       {counts.get('processed', 0):>6,d}")
    typer.echo(f"  Keyword hits:            {counts.get('keyword_hit', 0):>6,d}")
    typer.echo(f"  EN no-keyword excluded:  {counts.get('keyword_miss_en_excluded', 0):>6,d}")
    typer.echo(f"  Sent to LLM:             {counts.get('sent_to_llm', 0):>6,d}")
    typer.echo(f"  Classified relevant:     {counts.get('classified_relevant', 0):>6,d}")
    typer.echo(f"  Classified excluded:     {counts.get('classified_excluded', 0):>6,d}")
    typer.echo(f"  LLM errors:              {counts.get('llm_errors', 0):>6,d}")

    # Show relevance class counts
    typer.echo("\n📈 Relevance class distribution:")
    from pipeline.db import execute_sql
    try:
        rows = execute_sql("""
            SELECT relevance_class, COUNT(*) as count
            FROM raw_records
            WHERE relevance_class IS NOT NULL
            GROUP BY relevance_class
            ORDER BY count DESC
        """)
        if rows:
            for row in rows:
                cls = row.get("relevance_class", "unknown") or "unknown"
                cnt = row.get("count", 0)
                typer.echo(f"  {cls:30s} {cnt:>6,d}")
        else:
            typer.echo("  (no classified records)")
    except Exception:
        pass


# ============================================================
# M2: Extract command (T-2.5a-d)
# ============================================================

@app.command()
def extract(
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Process at most N records"),
) -> None:
    """Run Stage 2 episode extraction (M2). Gemini structured extraction."""
    from pipeline.stages.extract import run_extract

    typer.echo("Running Stage 2: Episode extraction...")
    if limit:
        typer.echo(f"  (limited to {limit} records)")

    counts = run_extract(limit=limit)

    typer.echo("\n📊 Extraction results:")
    typer.echo(f"  Records processed:       {counts.get('records_processed', 0):>6,d}")
    typer.echo(f"  Records extracted:       {counts.get('records_extracted', 0):>6,d}")
    typer.echo(f"  Episodes created:        {counts.get('episodes_created', 0):>6,d}")
    typer.echo(f"  Records failed:          {counts.get('records_failed', 0):>6,d}")
    typer.echo(f"  Validation retries:      {counts.get('validation_retries', 0):>6,d}")
    typer.echo(f"  General complaints:      {counts.get('general_complaints', 0):>6,d}")


# ============================================================
# M2: Trim command (T-2.7)
# ============================================================

@app.command()
def trim() -> None:
    """Null text of excluded records to save storage (FR-32, DR-3)."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE raw_records
                    SET text = NULL
                    WHERE status = 'excluded' AND text IS NOT NULL
                    RETURNING record_id
                """)
            )
            trimmed = result.fetchall()
            typer.echo(f"Trimmed text from {len(trimmed)} excluded records.")
    except Exception as e:
        typer.echo(f"Error trimming records: {e}", err=True)
        raise typer.Exit(1)


# ============================================================
# M2: export-sample command
# ============================================================

@app.command(name="export-sample")
def export_sample(
    output: str = typer.Option("data/review_sample.csv", "--output", "-o", help="Output CSV path"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Limit number of episodes"),
) -> None:
    """Export extracted episodes with original text to CSV for review."""
    from pipeline.db import execute_sql

    typer.echo("Exporting review sample...")

    query = """
        SELECT
            e.episode_id,
            e.record_id,
            r.source,
            r.lang,
            r.relevance_class,
            r.created_at as record_created_at,
            e.target_description,
            e.photo_category,
            e.photo_origin,
            e.photo_age_bucket,
            e.outcome,
            e.stakes,
            e.archetype_primary,
            e.archetype_secondary,
            e.emergent_label,
            e.summary_en,
            e.quote_original,
            e.quote_en,
            e.extraction_confidence,
            e.prompt_version,
            e.model_id,
            e.failure_modes,
            e.workarounds,
            r.text as original_text
        FROM episodes e
        JOIN raw_records r ON e.record_id = r.record_id
        ORDER BY e.created_at DESC NULLS LAST
    """
    if limit:
        query += f" LIMIT {int(limit)}"

    try:
        rows = execute_sql(query)
        if not rows:
            typer.echo("No episodes found to export.")
            return

        # Ensure output directory exists
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = _project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write CSV
        fieldnames = list(rows[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                # Convert any list fields to JSON strings for CSV
                clean_row = {}
                for k, v in row.items():
                    if isinstance(v, (list, dict)):
                        clean_row[k] = json.dumps(v)
                    elif isinstance(v, datetime):
                        clean_row[k] = v.isoformat()
                    else:
                        clean_row[k] = v
                writer.writerow(clean_row)

        typer.echo(f"✓ Exported {len(rows)} episodes to {output_path}")

    except Exception as e:
        typer.echo(f"Error exporting sample: {e}", err=True)
        raise typer.Exit(1)


# ============================================================
# Stub commands for future milestones
# ============================================================

@app.command()
def embed() -> None:
    """Embed episode summaries (M3)."""
    typer.echo("[STUB] embed")


@app.command()
def analyze() -> None:
    """Compute analysis aggregates (M3)."""
    typer.echo("[STUB] analyze")


@app.command()
def handoff() -> None:
    """Generate research handoff drafts (P1)."""
    typer.echo("[STUB] handoff")


@app.command(name="eval")
def eval_cmd(labels: str = typer.Option(..., help="Path to golden set CSV")) -> None:
    """Evaluate pipeline against golden set (P1)."""
    typer.echo(f"[STUB] eval --labels {labels}")


@app.command(name="import-csv")
def import_csv(path: str = typer.Argument(..., help="Path to CSV file")) -> None:
    """Import records from CSV (FR-15)."""
    started_at = datetime.now(timezone.utc)
    src = CSVSource(path)
    try:
        records = src.fetch(get_time_cutoff(), 100000)
        
        errors = [redact_secrets(e) for e in src.errors] if hasattr(src, 'errors') and src.errors else []
        rejected = src.rejected_count if hasattr(src, 'rejected_count') else 0
        
        _upsert_records(records)
        ended_at = datetime.now(timezone.utc)
        counts = {"fetched": len(records), "stored": len(records), "rejected": rejected}
        _log_run("ingest", "csv", started_at, ended_at, counts, errors)
        typer.echo(f"Imported {len(records)} records from {path} ({rejected} rejected)")
    except Exception as e:
        err_msg = redact_secrets(str(e))
        typer.echo(f"  ✗ Error importing CSV: {err_msg}", err=True)
        _log_run("ingest", "csv", started_at, datetime.now(timezone.utc), {"fetched": 0, "stored": 0}, [err_msg])


@app.command(name="import-literature")
def import_literature(path: str = typer.Argument(..., help="Path to literature file")) -> None:
    """Import literature for RAG (P1)."""
    typer.echo(f"[STUB] import-literature {path}")


@app.command(name="run-all")
def run_all() -> None:
    """Run all pipeline stages in order."""
    typer.echo("[STUB] run-all")


# ============================================================
# Entry point
# ============================================================

def main() -> None:
    app()


if __name__ == "__main__":
    main()
