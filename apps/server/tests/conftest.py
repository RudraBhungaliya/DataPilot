"""
Shared pytest fixtures.

Keeps the test suite hermetic: the database dependency is overridden with an
in-memory fake session so no test requires (or accidentally opens) a live
PostgreSQL connection. Tests that need richer behaviour can still override
`get_db` locally.
"""

import sys
from pathlib import Path
import uuid

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.db.session import get_db


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, data):
        self._data = data

    def scalar_one_or_none(self):
        return self._data[0] if self._data else None

    def scalars(self):
        return _Scalars(self._data)


class MockAsyncSession:
    """Minimal in-memory AsyncSession stand-in supporting add/commit/execute."""

    def __init__(self, storage):
        self.storage = storage

    def add(self, obj):
        # Emulate SQLAlchemy Python-side column defaults (id) that would otherwise
        # be applied on flush, so endpoints can serialize the object immediately.
        if getattr(obj, "id", None) in (None, ""):
            try:
                obj.id = str(uuid.uuid4())
            except Exception:
                pass
        if hasattr(obj, "id"):
            self.storage[obj.id] = obj

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        pass

    async def close(self):
        pass

    async def get(self, model, pk):
        obj = self.storage.get(pk)
        if obj is not None and isinstance(obj, model):
            return obj
        return None

    async def execute(self, statement):
        target_id = None
        try:
            compiled = statement.compile()
            for key, value in compiled.params.items():
                if "id" in key.lower() and isinstance(value, str):
                    target_id = value
                    break
        except Exception:
            pass

        entity = None
        try:
            descriptions = getattr(statement, "column_descriptions", None) or []
            if descriptions:
                entity = descriptions[0].get("entity")
        except Exception:
            entity = None

        values = list(self.storage.values())
        if entity is not None:
            values = [v for v in values if isinstance(v, entity)]

        if target_id:
            matched = [v for v in values if getattr(v, "id", None) == target_id]
        else:
            matched = values
        return _Result(matched)


@pytest.fixture(autouse=True)
def _mock_db_dependency():
    """Overrides get_db with an in-memory fake for every test by default."""
    storage = {}

    async def override_get_db():
        yield MockAsyncSession(storage)

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
