"""One-time administrator bootstrap against synthetic, isolated SQLite users."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sys
from threading import Barrier
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

# Import real models without loading .env, credentials, or any configured DB.
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
config = ModuleType("app.config")
config.settings = SimpleNamespace(database_url="sqlite:///:memory:", debug=False)
with patch.dict(sys.modules, {"app.config": config}):
    from app.models import User
    import app.database as database
    isolated_modules = {name: module for name, module in sys.modules.items()
                        if name == "app" or name.startswith("app.")}

spec = importlib.util.spec_from_file_location("bootstrap_administrator", BACKEND / "scripts/bootstrap_administrator.py")
utility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utility)


@pytest.fixture(autouse=True)
def isolated_application_imports():
    # The utility imports lazily. Keep the synthetic configuration in place for
    # those imports too, then restore the caller's modules after each test.
    with patch.dict(sys.modules, isolated_modules):
        yield


@pytest.fixture
def engine(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "synthetic.db"))
    User.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            User(id=1, email="owner@example.invalid", display_name="Synthetic owner",
                 password_hash="canary-hash-owner", session_version=4),
            User(id=2, email="other@example.invalid", display_name="Synthetic other",
                 password_hash="canary-hash-other", session_version=7),
        ])
        session.commit()
    yield engine
    engine.dispose()


def rows(engine):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(User.__table__).order_by(User.id)).mappings()]


def run(engine, user_id=1, dry_run=False):
    with Session(engine) as session:
        utility.bootstrap(session, user_id, dry_run=dry_run)


def test_apply_changes_only_target_flag(engine):
    before = rows(engine)
    run(engine)
    before[0]["is_admin"] = True
    assert rows(engine) == before


def test_dry_run_does_not_update_or_commit(engine):
    before = rows(engine)
    statements, commits = [], []
    event.listen(engine, "before_cursor_execute", lambda c, cur, sql, *args: statements.append(sql))
    event.listen(engine, "commit", lambda c: commits.append(True))
    run(engine, dry_run=True)
    assert not commits
    assert not any(sql.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")) for sql in statements)
    assert rows(engine) == before


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("condition", ["missing", "inactive", "active-admin", "inactive-admin", "repeated"])
def test_refuses_invalid_preconditions_without_changes(engine, dry_run, condition):
    with engine.begin() as connection:
        if condition == "inactive":
            connection.execute(text("UPDATE users SET is_active=false WHERE id=1"))
        elif condition in {"active-admin", "inactive-admin"}:
            connection.execute(text("UPDATE users SET is_admin=true, is_active=:active WHERE id=2"),
                               {"active": condition == "active-admin"})
        elif condition == "repeated":
            connection.execute(text("UPDATE users SET is_admin=true WHERE id=1"))
    before = rows(engine)
    with pytest.raises(utility.BootstrapRefused):
        run(engine, user_id=999 if condition == "missing" else 1, dry_run=dry_run)
    assert rows(engine) == before


def test_postcondition_failure_rolls_back(engine):
    # Simulate an unexpected database trigger promoting another user.
    with engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER extra_admin AFTER UPDATE OF is_admin ON users "
                                "WHEN NEW.id=1 BEGIN UPDATE users SET is_admin=true WHERE id=2; END"))
    before = rows(engine)
    with pytest.raises(utility.BootstrapRefused):
        run(engine)
    assert rows(engine) == before


def test_concurrent_bootstraps_create_only_one_admin(engine):
    barrier = Barrier(2)
    def promote(user_id):
        barrier.wait(timeout=5)
        try:
            run(engine, user_id=user_id)
            return "committed"
        except utility.BootstrapRefused:
            return "refused"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(promote, [1, 2]))
    assert sorted(results) == ["committed", "refused"]
    assert sum(row["is_admin"] for row in rows(engine)) == 1


@pytest.mark.parametrize("matches", [[1], [1, 1]])
def test_postgres_lock_and_ambiguous_match_refusal(matches):
    # Offline verification of the PostgreSQL path; no PostgreSQL connection.
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalars.return_value.all.return_value = matches
    session.scalar.return_value = 0
    if len(matches) != 1:
        with pytest.raises(utility.BootstrapRefused):
            utility.bootstrap(session, 1, dry_run=True)
    else:
        utility.bootstrap(session, 1, dry_run=True)
        session.rollback.assert_called_once()
    session.connection.assert_called_once_with(execution_options={"isolation_level": "READ COMMITTED"})
    sql = [str(call.args[0]) for call in session.execute.call_args_list]
    assert sql == ["SET LOCAL lock_timeout = '5s'", "SET LOCAL statement_timeout = '15s'",
                   "LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"]


@pytest.mark.parametrize("mode", ["--dry-run", "--apply"])
def test_cli_success_has_no_account_data(engine, monkeypatch, capsys, mode):
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    engine.echo = True  # Even configured SQL logging must not expose values.
    assert utility.main(["--user-id", "1", mode]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out == ("Preconditions satisfied; no changes made.\n" if mode == "--dry-run"
                          else "Administrator bootstrap committed.\n")


def test_cli_redacts_database_errors(monkeypatch, capsys):
    def fail():
        raise RuntimeError("postgresql://canary-user:canary-password@canary-host/canary-db")
    monkeypatch.setattr(database, "SessionLocal", fail)
    assert utility.main(["--user-id", "1", "--apply"]) == 1
    output = capsys.readouterr()
    assert "canary" not in output.out + output.err
    assert "outcome not confirmed" in output.err


@pytest.mark.parametrize("arguments", [[], ["--user-id", "1"], ["--user-id", "0", "--apply"],
                                      ["--user-id", "1", "--apply", "--dry-run"]])
def test_cli_requires_identifier_and_explicit_mode(monkeypatch, arguments):
    monkeypatch.setattr(database, "SessionLocal", lambda: pytest.fail("Must not connect"))
    with pytest.raises(SystemExit) as exc:
        utility.main(arguments)
    assert exc.value.code == 2
