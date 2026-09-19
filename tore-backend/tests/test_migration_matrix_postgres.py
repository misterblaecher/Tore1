from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from db import Base
import models  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL.startswith(("postgresql://", "postgres://")),
    reason="PostgreSQL migration matrix",
)


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@contextmanager
def _temporary_database(label: str):
    source = make_url(DATABASE_URL.replace("postgres://", "postgresql://", 1))
    name = f"tore_matrix_{label}_{uuid.uuid4().hex[:10]}"
    admin_url = source.set(database="postgres")
    target_url = source.set(database=name)

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    target_url_text = target_url.render_as_string(hide_password=False)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = target_url_text
    try:
        yield target_url_text
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        cleanup.dispose()


def _version(url: str) -> str:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()


def _assert_orm_parity(url: str) -> None:
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        missing_tables = sorted(set(Base.metadata.tables) - existing_tables)
        assert missing_tables == []

        missing_columns: dict[str, list[str]] = {}
        for table_name, table in Base.metadata.tables.items():
            actual = {column["name"] for column in inspector.get_columns(table_name)}
            missing = sorted({column.name for column in table.columns} - actual)
            if missing:
                missing_columns[table_name] = missing
        assert missing_columns == {}
    finally:
        engine.dispose()


def _upgrade(url: str, target: str) -> Config:
    config = _config(url)
    command.upgrade(config, target)
    return config


def test_postgres_fresh_database_upgrades_to_head():
    with _temporary_database("fresh") as url:
        config = _upgrade(url, "head")
        head = ScriptDirectory.from_config(config).get_current_head()
        assert _version(url) == head == "0030_distributed_rate_limits"
        _assert_orm_parity(url)


def test_postgres_retired_public_event_lineage_upgrades_to_head():
    with _temporary_database("public") as url:
        config = _upgrade(url, "0013_public_event_recap")
        assert _version(url) == "0013_public_event_recap"

        command.upgrade(config, "head")

        assert _version(url) == ScriptDirectory.from_config(config).get_current_head()
        inspector = inspect(create_engine(url))
        assert "forum_event_pages" in inspector.get_table_names()
        assert "structure_discussion_reactions" in inspector.get_table_names()
        assert "structure_notifications" in inspector.get_table_names()
        assert {"parent_id", "document_ids"}.issubset(
            {column["name"] for column in inspector.get_columns("structure_discussion_posts")}
        )
        _assert_orm_parity(url)


def test_postgres_n_minus_one_upgrade_preserves_schema_parity():
    with _temporary_database("nminus1") as url:
        config = _upgrade(url, "0029_legacy_workspace_parity")
        assert _version(url) == "0029_legacy_workspace_parity"

        engine = create_engine(url)
        with engine.begin() as connection:
            # Synthetic production-like data only; never use a production dump.
            connection.execute(
                text(
                    "INSERT INTO rate_limit_buckets(bucket_key, window_started_at_ms, request_count, updated_at_ms) "
                    "VALUES ('matrix:sentinel', 1, 1, 1)"
                )
            ) if "rate_limit_buckets" in inspect(engine).get_table_names() else None
        engine.dispose()

        command.upgrade(config, "head")

        assert _version(url) == "0030_distributed_rate_limits"
        _assert_orm_parity(url)
