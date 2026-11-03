"""Synthetic recovery tests: private disposable PostgreSQL, never the local service/RDS."""

import builtins
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import warnings
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import recovery_database as recovery
from bootstrap_administrator import BootstrapRefused

CANARY = "synthetic-secret-do-not-print"


@pytest.fixture(scope="module")
def isolated_pg(tmp_path_factory):
    root = tmp_path_factory.mktemp("recovery_pg")
    data, socket = root / "data", root / "socket"
    socket.mkdir(mode=0o700)
    binary = Path("/usr/lib/postgresql/16/bin")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    subprocess.run([str(binary / "initdb"), "-D", str(data), "-A", "trust",
                    "-U", "synthetic_owner", "--no-locale"],
                   env=env, check=True, capture_output=True)
    subprocess.run([str(binary / "pg_ctl"), "-D", str(data), "-l", str(root / "server.log"),
                    "-o", f"-F -h '' -k {socket} -p 55439", "-w", "start"],
                   env=env, check=True, capture_output=True)
    try:
        engine = create_engine("postgresql+psycopg2://", poolclass=NullPool, connect_args={
            "host": str(socket), "port": 55439, "dbname": "postgres",
            "user": "synthetic_owner", "password": CANARY,
        })
        yield engine
        engine.dispose()
    finally:
        subprocess.run([str(binary / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
                       env=env, check=True, capture_output=True)


@pytest.fixture
def engine(isolated_pg, monkeypatch):
    monkeypatch.setattr(recovery, "DATABASE", "postgres")
    monkeypatch.setattr(recovery, "ROLE", "synthetic_owner")
    with isolated_pg.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS public.users, public.alembic_version"))
        c.execute(text("CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY)"))
        c.execute(text("INSERT INTO public.alembic_version VALUES (:rev)"), {"rev": recovery.BASE})
        c.execute(text("CREATE TABLE public.users (id integer PRIMARY KEY, is_active boolean NOT NULL, "
                       "marker text NOT NULL)"))
        c.execute(text("INSERT INTO public.users VALUES (1, true, 'synthetic-owner'), "
                       "(2, true, 'synthetic-other')"))
    return isolated_pg


def snapshot(engine):
    with engine.connect() as c:
        return (c.execute(text("SELECT * FROM public.users ORDER BY id")).all(),
                c.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all())


def test_migrate_dry_run_apply_and_repeat(engine):
    recovery.perform(engine, "migrate")
    migrated = snapshot(engine)
    assert migrated == ([(1, True, "synthetic-owner", False, 0),
                         (2, True, "synthetic-other", False, 0)], [recovery.TARGET])
    recovery.perform(engine, "bootstrap-dry-run")
    assert snapshot(engine) == migrated
    recovery.perform(engine, "bootstrap-apply")
    after = snapshot(engine)
    assert after[0] == [(1, True, "synthetic-owner", True, 0),
                        (2, True, "synthetic-other", False, 0)]
    for operation in ("migrate", "bootstrap-dry-run", "bootstrap-apply"):
        with pytest.raises(Exception):
            recovery.perform(engine, operation)
        assert snapshot(engine) == after


@pytest.mark.parametrize("problem", ["database", "role", "revision", "missing", "inactive"])
def test_preflight_refusal_leaves_database_unchanged(engine, monkeypatch, problem):
    if problem in {"database", "role"}:
        monkeypatch.setattr(recovery, problem.upper(), "unexpected")
    else:
        with engine.begin() as c:
            c.execute(text({
                "revision": "UPDATE public.alembic_version SET version_num='unexpected'",
                "missing": "DELETE FROM public.users WHERE id=1",
                "inactive": "UPDATE public.users SET is_active=false WHERE id=1",
            }[problem]))
    before = snapshot(engine)
    with pytest.raises(recovery.RecoveryRefused):
        recovery.perform(engine, "migrate")
    assert snapshot(engine) == before


def test_second_migration_failure_rolls_back_first_ddl_and_revision(engine, monkeypatch):
    original = recovery.Operations.add_column
    def fail_second(self, table, column, **kw):
        if column.name == "session_version":
            raise RuntimeError(CANARY)
        return original(self, table, column, **kw)
    monkeypatch.setattr(recovery.Operations, "add_column", fail_second)
    before = snapshot(engine)
    with pytest.raises(RuntimeError):
        recovery.perform(engine, "migrate")
    assert snapshot(engine) == before


def test_postcondition_failure_rolls_back_stamp_and_both_columns(engine, monkeypatch):
    original = recovery.preflight
    def fail_final(c, rev):
        if rev == recovery.TARGET:
            raise recovery.RecoveryRefused()
        original(c, rev)
    monkeypatch.setattr(recovery, "preflight", fail_final)
    before = snapshot(engine)
    with pytest.raises(recovery.RecoveryRefused):
        recovery.perform(engine, "migrate")
    assert snapshot(engine) == before


def test_concurrent_postgres_bootstrap_has_one_winner(engine):
    recovery.perform(engine, "migrate")
    barrier = Barrier(2)
    def attempt(_):
        barrier.wait(timeout=5)
        try:
            recovery.perform(engine, "bootstrap-apply")
            return "committed"
        except BootstrapRefused:
            return "refused"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [1, 2])) == ["committed", "refused"]
    assert [row[3] for row in snapshot(engine)[0]] == [True, False]


def test_migration_lock_timeout_leaves_state_unchanged(engine):
    before = snapshot(engine)
    with engine.connect() as holder, holder.begin():
        holder.execute(text("LOCK TABLE public.users IN ROW EXCLUSIVE MODE"))
        with engine.connect() as contender:
            contender.execute(text("SET lock_timeout='100ms'"))
            contender.commit()
            with pytest.raises(Exception):
                recovery.migrate(contender)
    assert snapshot(engine) == before


@pytest.mark.parametrize("operation", ["bootstrap-dry-run", "bootstrap-apply"])
def test_bootstrap_refuses_wrong_database(engine, monkeypatch, operation):
    recovery.perform(engine, "migrate")
    before = snapshot(engine)
    monkeypatch.setattr(recovery, "DATABASE", "unexpected")
    with pytest.raises(recovery.RecoveryRefused):
        recovery.perform(engine, operation)
    assert snapshot(engine) == before


def test_no_configuration_imports_or_dotenv_reads(engine, monkeypatch):
    original_import, original_open = builtins.__import__, builtins.open
    def guarded_import(name, *args, **kw):
        if name == "app" or name.startswith("app.") or name == "dotenv":
            pytest.fail("Application/configuration import")
        return original_import(name, *args, **kw)
    def guarded_open(path, *args, **kw):
        if isinstance(path, (str, os.PathLike)) and Path(path).name in {".env", "alembic.ini"}:
            pytest.fail("Configuration file read")
        return original_open(path, *args, **kw)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unintended-localhost")
    for operation in ("migrate", "bootstrap-dry-run", "bootstrap-apply"):
        recovery.perform(engine, operation)


def test_connection_parameters_are_explicit_and_password_not_in_url(tmp_path, monkeypatch):
    ca = tmp_path / "synthetic-ca.pem"
    ca.write_text("synthetic certificate placeholder; driver is mocked")
    monkeypatch.setattr(recovery, "CA", ca)
    for key in list(os.environ):
        if key.startswith("PG"):
            monkeypatch.delenv(key)
    driver = Mock(side_effect=RuntimeError("synthetic connection refusal"))
    monkeypatch.setattr(recovery.psycopg2, "connect", driver)
    engine = recovery.recovery_engine(CANARY)
    assert CANARY not in str(engine.url)
    assert CANARY not in os.environ.values()
    with pytest.raises(Exception):
        engine.connect()
    kwargs = driver.call_args.kwargs
    assert kwargs["host"] == recovery.HOST
    assert kwargs["port"] == 5432
    assert kwargs["dbname"] == recovery.DATABASE
    assert kwargs["user"] == recovery.ROLE
    assert kwargs["sslmode"] == "verify-full"
    assert kwargs["sslrootcert"] == str(ca)
    assert kwargs["passfile"] == "/dev/null"
    assert kwargs["password"] == CANARY
    engine.dispose()


@pytest.mark.parametrize("problem", ["missing-ca", "empty-password", "pg-environment"])
def test_connection_setup_refuses_unsafe_inputs(tmp_path, monkeypatch, problem):
    ca = tmp_path / "ca.pem"
    if problem != "missing-ca":
        ca.write_text("synthetic")
    monkeypatch.setattr(recovery, "CA", ca)
    if problem == "pg-environment":
        monkeypatch.setenv("PGSERVICE", "unintended-service")
    driver = Mock()
    monkeypatch.setattr(recovery.psycopg2, "connect", driver)
    with pytest.raises(recovery.RecoveryRefused):
        recovery.recovery_engine("" if problem == "empty-password" else CANARY)
    driver.assert_not_called()


@pytest.mark.parametrize("operation", ["migrate", "bootstrap-dry-run", "bootstrap-apply"])
def test_cli_failure_redacts_errors(monkeypatch, capsys, operation):
    engine = Mock()
    monkeypatch.setattr(recovery, "prompt_password", lambda: CANARY)
    monkeypatch.setattr(recovery, "recovery_engine", lambda password: engine)
    monkeypatch.setattr(recovery, "perform", Mock(side_effect=RuntimeError(CANARY)))
    assert recovery.main([operation]) == 1
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err
    assert "outcome unconfirmed" in output.err
    assert "committed" not in output.out
    engine.dispose.assert_called_once()


def test_help_does_not_prompt_or_connect(monkeypatch):
    monkeypatch.setattr(recovery, "prompt_password", lambda: pytest.fail("Prompted"))
    with pytest.raises(SystemExit) as exc:
        recovery.main(["--help"])
    assert exc.value.code == 0


def test_missing_terminal_refuses_before_password_or_connection(monkeypatch, capsys):
    def no_terminal(*args, **kw):
        raise OSError(CANARY)
    monkeypatch.setattr(builtins, "open", no_terminal)
    monkeypatch.setattr(recovery.getpass, "getpass", lambda *a: pytest.fail("Prompt fallback"))
    assert recovery.main(["migrate"]) == 1
    assert CANARY not in capsys.readouterr().err


def test_getpass_warning_is_an_error(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(builtins, "open", lambda *a: nullcontext())
    def fallback(*args):
        warnings.warn("synthetic fallback", recovery.getpass.GetPassWarning)
        pytest.fail("Must not accept echoed input")
    monkeypatch.setattr(recovery.getpass, "getpass", fallback)
    with pytest.raises(recovery.getpass.GetPassWarning):
        recovery.prompt_password()


def test_cli_success_is_sanitized(engine, monkeypatch, capsys):
    monkeypatch.setattr(recovery, "prompt_password", lambda: CANARY)
    monkeypatch.setattr(recovery, "recovery_engine", lambda password: engine)
    for operation in ("migrate", "bootstrap-dry-run", "bootstrap-apply"):
        assert recovery.main([operation]) == 0
        output = capsys.readouterr()
        assert not output.err
        assert CANARY not in output.out
        assert "synthetic-owner" not in output.out
        expected = "no changes" if operation == "bootstrap-dry-run" else "committed"
        assert expected in output.out
