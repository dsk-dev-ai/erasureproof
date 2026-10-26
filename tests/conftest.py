"""Test configuration.

Environment is set before the package is imported so settings and the default
database point at a disposable directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

BASE = Path(tempfile.mkdtemp(prefix="erasureproof-tests-"))
REPO = Path(__file__).resolve().parents[1]

os.environ["ERASUREPROOF_DATA_DIR"] = str(BASE)
os.environ["ERASUREPROOF_DATABASE_URL"] = f"sqlite:///{BASE / 'test.db'}"
os.environ["ERASUREPROOF_ATTESTATION_KEY"] = "test-key"
os.environ["ERASUREPROOF_POLICY_DIR"] = str(REPO / "policies")
os.environ["ERASUREPROOF_DEFAULT_JURISDICTION"] = "gdpr"

from erasureproof.models.db import get_database  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    database = get_database()
    database.drop_all()
    database.create_all()
    yield
