"""
Unit tests for database URL normalization, runtime cutoff, migration transactions, and error handling.

References:
  FR-2   — 24-month cutoff computed at runtime
  DR-4   — migrations versioned in db/migrations and applied safely
  DR-5   — db storage tracking
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
import typer

from pipeline.config import get_time_cutoff
from pipeline.db import _normalize_db_url
from backend.db import _normalize_async_db_url


class TestConfigRuntimeCutoff:
    """Test FR-2: 24-month cutoff is computed at runtime."""

    def test_get_time_cutoff_computes_at_runtime(self):
        t1 = get_time_cutoff()
        now = datetime.now(timezone.utc)
        expected = now - timedelta(days=730)
        assert abs((t1 - expected).total_seconds()) < 5


class TestDbUrlNormalization:
    """Test database URL scheme normalization."""

    def test_pipeline_normalizes_postgres_scheme(self):
        url = "postgres://user:secret@ep-host.neon.tech/neondb?sslmode=require"
        normalized = _normalize_db_url(url)
        assert normalized.startswith("postgresql://")

    def test_backend_normalizes_postgres_and_postgresql_scheme(self):
        url1 = "postgres://user:secret@ep-host.neon.tech/neondb?sslmode=require"
        assert _normalize_async_db_url(url1).startswith("postgresql+asyncpg://")

        url2 = "postgresql://user:secret@ep-host.neon.tech/neondb?sslmode=require"
        assert _normalize_async_db_url(url2).startswith("postgresql+asyncpg://")

    def test_backend_handles_empty_url_gracefully(self):
        assert _normalize_async_db_url("") == ""


class TestMigrationRunnerTransactions:
    """Test DR-4: migrations run with rollback and schema_migrations tracking."""

    def test_migration_runner_tracks_applied_and_skips(self):
        from pipeline.cli import migrate

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Simulate 001_initial_schema.sql already applied
        mock_cur.fetchall.return_value = [("001_initial_schema.sql",)]

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("os.environ.get", return_value="postgresql://dummy@host/db"):
                migrate()

        # Should not execute the sql if already in applied_versions
        executed_sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
        assert any("schema_migrations" in sql for sql in executed_sqls)
        # Should not insert 001_initial_schema.sql again
        assert not any("INSERT INTO schema_migrations" in sql for sql in executed_sqls)

    def test_migration_runner_rolls_back_on_failure(self):
        from pipeline.cli import migrate

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # No migrations applied yet
        mock_cur.fetchall.return_value = []
        # Error during execution of migration SQL
        mock_cur.execute.side_effect = [None, None, Exception("Syntax error in migration")]

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("os.environ.get", return_value="postgresql://dummy@host/db"):
                with pytest.raises(typer.Exit):
                    migrate()

        mock_conn.rollback.assert_called_once()

    def test_migration_runner_handles_connection_error_cleanly(self):
        from pipeline.cli import migrate

        with patch("psycopg2.connect", side_effect=Exception("Neon unreachable")):
            with patch("os.environ.get", return_value="postgresql://dummy@host/db"):
                with pytest.raises(typer.Exit):
                    migrate()
