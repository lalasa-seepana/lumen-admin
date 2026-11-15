from __future__ import annotations

import os

import pytest

from app.services.postgres_store import appointment_conflict_from_db_error, is_undefined_table


class _FakeDiag:
    def __init__(self, sqlstate: str | None) -> None:
        self.sqlstate = sqlstate


class _FakeError(Exception):
    def __init__(self, sqlstate: str | None = None) -> None:
        self.sqlstate = sqlstate
        self.diag = _FakeDiag(sqlstate) if sqlstate else None


def test_appointment_conflict_from_exclusion_violation():
    assert appointment_conflict_from_db_error(_FakeError("23P01")) is True
    assert appointment_conflict_from_db_error(_FakeError("23505")) is False


def test_is_undefined_table():
    assert is_undefined_table(_FakeError("42P01")) is True
    assert is_undefined_table(_FakeError("23P01")) is False


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_postgres_store_connects():
    from app.services.postgres_store import PostgresClinicStore

    store = PostgresClinicStore(os.environ["DATABASE_URL"])
    assert store.clinics is not None