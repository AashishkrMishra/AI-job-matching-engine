"""Guards on the environment configuration.

The `_require` helper is the whole of the fail-fast behaviour, so it is tested
directly. Reloading `app.config` in-process is not a viable alternative: other
modules bind its values with `from app.config import ...`, and a reload that
raises part-way through would leave the module dict in a torn state for every
test that ran afterwards.
"""

import pathlib

import pytest

from app.config import _require

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_require_rejects_a_missing_variable(monkeypatch):
    monkeypatch.delenv("A_VARIABLE_NOBODY_SETS", raising=False)
    with pytest.raises(RuntimeError, match="A_VARIABLE_NOBODY_SETS is not set"):
        _require("A_VARIABLE_NOBODY_SETS")


def test_require_rejects_an_empty_variable(monkeypatch):
    """An exported-but-blank variable is a misconfiguration, not a value."""
    monkeypatch.setenv("A_BLANK_VARIABLE", "")
    with pytest.raises(RuntimeError, match="A_BLANK_VARIABLE is not set"):
        _require("A_BLANK_VARIABLE")


def test_require_names_the_variable_and_points_at_the_template(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_THING", raising=False)
    with pytest.raises(RuntimeError, match=r"\.env\.example"):
        _require("SOME_MISSING_THING")


def test_require_returns_the_value_when_set(monkeypatch):
    monkeypatch.setenv("A_SET_VARIABLE", "hello")
    assert _require("A_SET_VARIABLE") == "hello"


def test_secret_key_has_no_hardcoded_fallback():
    """Regression guard. A default signing key would be identical in every clone
    of this repository, so anyone who read it could mint a token for any account.
    """
    source = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    assert "dev-secret" not in source
    assert 'getenv("SECRET_KEY"' not in source
    assert '_require("SECRET_KEY")' in source
