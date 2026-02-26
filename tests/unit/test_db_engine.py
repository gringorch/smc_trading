from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_engine_module_initialization_uses_settings(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_engine = object()

    def fake_create_engine(dsn: str, **kwargs):
        captured["dsn"] = dsn
        captured["engine_kwargs"] = kwargs
        return fake_engine

    def fake_sessionmaker(**kwargs):
        captured["session_kwargs"] = kwargs
        return "SESSION_FACTORY"

    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(
            mysql_dsn="sqlite+pysqlite:///:memory:",
            db_pool_size=3,
            db_max_overflow=4,
            db_echo=False,
        ),
    )
    monkeypatch.setattr("sqlalchemy.create_engine", fake_create_engine)
    monkeypatch.setattr("sqlalchemy.orm.sessionmaker", fake_sessionmaker)

    import db.engine as engine_module

    reloaded = importlib.reload(engine_module)
    assert reloaded.engine is fake_engine
    assert reloaded.SessionLocal == "SESSION_FACTORY"
    assert captured["dsn"] == "sqlite+pysqlite:///:memory:"
    assert captured["session_kwargs"]["bind"] is fake_engine


def test_session_scope_commits_on_success(monkeypatch) -> None:
    import db.engine as engine_module

    session = Mock()
    monkeypatch.setattr(engine_module, "SessionLocal", lambda: session)

    with engine_module.session_scope() as yielded:
        assert yielded is session

    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.close.assert_called_once()


def test_session_scope_rolls_back_on_error(monkeypatch) -> None:
    import db.engine as engine_module

    session = Mock()
    monkeypatch.setattr(engine_module, "SessionLocal", lambda: session)

    with pytest.raises(RuntimeError):
        with engine_module.session_scope():
            raise RuntimeError("boom")

    session.commit.assert_not_called()
    session.rollback.assert_called_once()
    session.close.assert_called_once()

