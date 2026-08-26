"""Guards on the things that only break outside this machine.

Both cases here passed every behavioural test while being unable to start on a
clean deployment: the venv already had an undeclared dependency installed, and
the only database Alembic had ever been pointed at was an empty one.
"""

import os
import pathlib
import re
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.database import Base

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_requirements_declares_email_validator():
    """pydantic declares email-validator only under its optional `email` extra, so
    nothing pulls it in transitively — yet app/schemas.py imports EmailStr, which
    needs it at import time. Leave it out and a clean
    `pip install -r requirements.txt` yields a server that cannot boot; it works
    locally only because the package is already sitting in the venv.
    """
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^email-validator==", requirements, re.M), (
        "email-validator must be declared explicitly — pydantic will not bring it in"
    )


def _alembic(command: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command.split()],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def legacy_database(tmp_path):
    """A database in the state every existing deployment is in: tables built by
    the `Base.metadata.create_all()` that this work removed, and therefore no
    alembic_version row to say which revision it is at.
    """
    url = f"sqlite:///{tmp_path.as_posix()}/legacy.db"
    Base.metadata.create_all(bind=create_engine(url))
    return url


def test_baseline_migration_adopts_a_database_that_predates_alembic(legacy_database):
    """`alembic upgrade head` runs on every boot, chained to uvicorn with `&&` in
    render.yaml. An unconditional CREATE TABLE in the baseline therefore does not
    merely fail the migration — it stops the service from starting at all, on
    exactly the databases that already hold real data.
    """
    result = _alembic("upgrade head", legacy_database)

    assert result.returncode == 0, result.stderr
    assert "already exists" not in result.stderr

    tables = inspect(create_engine(legacy_database)).get_table_names()
    assert {"users", "jobs", "alembic_version"} <= set(tables)


def test_the_adopted_schema_matches_the_models(legacy_database):
    """Skipping existing tables is only safe if what was already there is what the
    migration would have built. `alembic check` compares the models against the
    live database and fails if they have drifted.
    """
    assert _alembic("upgrade head", legacy_database).returncode == 0

    result = _alembic("check", legacy_database)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_baseline_still_builds_a_database_from_nothing(tmp_path):
    """The guard must not turn the migration into a no-op for fresh deployments."""
    url = f"sqlite:///{tmp_path.as_posix()}/fresh.db"

    assert _alembic("upgrade head", url).returncode == 0

    tables = inspect(create_engine(url)).get_table_names()
    assert {"users", "jobs", "alembic_version"} <= set(tables)


def test_the_migration_round_trips(tmp_path):
    """A baseline that cannot be undone cannot be tested against a real reset."""
    url = f"sqlite:///{tmp_path.as_posix()}/roundtrip.db"

    assert _alembic("upgrade head", url).returncode == 0
    assert _alembic("downgrade base", url).returncode == 0

    tables = inspect(create_engine(url)).get_table_names()
    assert "users" not in tables and "jobs" not in tables
