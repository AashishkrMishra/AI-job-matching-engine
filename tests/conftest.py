"""Test bootstrap.

`app.database` builds its engine at import time from `config.DATABASE_URL`, so
the environment has to be pointed at a throwaway SQLite file *before* anything
under `app.` is imported. `load_dotenv()` does not override variables that are
already set, so this wins over any local .env.
"""

import os
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

_TMP_DB = pathlib.Path(tempfile.gettempdir()) / "ai_job_tracker_tests.db"
_TMP_DB.unlink(missing_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("HF_API_TOKEN", "")

import pytest  # noqa: E402  — must follow the env setup above


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema with Alembic, so every run also exercises the migration."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    yield

    # Release the pooled SQLite connections before unlinking; Windows refuses
    # to delete a file that still has an open handle.
    from app.database import engine

    engine.dispose()
    try:
        _TMP_DB.unlink(missing_ok=True)
    except PermissionError:
        pass  # It lives in the temp dir, and the next run recreates it.
