"""Owner-supplied fixed-account reset using synthetic, isolated PostgreSQL users."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import event, text

from test_recovery_database import engine, isolated_pg, recovery

PASSWORDS = {user_id: f"synthetic-saved-password-{user_id}-canary" for user_id in (1, 13, 17)}
DB_PASSWORD = "synthetic-database-password"


@pytest.fixture
def reset_db(engine):
    recovery.perform(engine, "migrate")
    with engine.begin() as c:
        c.execute(text("ALTER TABLE public.users ADD COLUMN password_hash text NOT NULL DEFAULT 'synthetic-old-hash'"))
        c.execute(text("ALTER TABLE public.users ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()"))
        c.execute(text("UPDATE public.users SET is_admin=true WHERE id=1"))
        c.execute(text("INSERT INTO public.users (id,is_active,marker) VALUES "
                       "(13,true,'synthetic-13'), (17,true,'synthetic-17')"))
    return engine


def records(engine):
    with engine.connect() as c:
        return {row["id"]: dict(row) for row in c.execute(text(
            "SELECT * FROM public.users ORDER BY id"
        )).mappings()}


def apply(engine, passwords=None):
    recovery.perform(engine, "reset-passwords", passwords=PASSWORDS if passwords is None else passwords)


def answers(passwords=PASSWORDS):
    return [value for user_id in recovery.RESET_IDS for value in (passwords[user_id], passwords[user_id])]


def test_only_three_hashes_and_versions_change_and_repeat_refused(reset_db):
    from app.auth.passwords import verify_password
    before = records(reset_db)
    apply(reset_db)
    committed = records(reset_db)
    after = records(reset_db)
    for user_id in recovery.RESET_IDS:
        assert verify_password(PASSWORDS[user_id], after[user_id]["password_hash"])
        assert after[user_id]["session_version"] == 1
        after[user_id]["password_hash"] = before[user_id]["password_hash"]
        after[user_id]["session_version"] = before[user_id]["session_version"]
    assert after == before
    with pytest.raises(recovery.RecoveryRefused):
        apply(reset_db)
    assert records(reset_db) == committed


@pytest.mark.parametrize("problem", ["missing", "inactive", "wrong-admin", "no-admin", "extra-admin", "inactive-admin", "version"])
def test_invalid_account_state_leaves_all_records_unchanged(reset_db, problem):
    with reset_db.begin() as c:
        c.execute(text({
            "missing": "DELETE FROM public.users WHERE id=17",
            "inactive": "UPDATE public.users SET is_active=false WHERE id=13",
            "wrong-admin": "UPDATE public.users SET is_admin=true WHERE id=13",
            "no-admin": "UPDATE public.users SET is_admin=false WHERE id=1",
            "extra-admin": "UPDATE public.users SET is_admin=true WHERE id=2",
            "inactive-admin": "UPDATE public.users SET is_admin=true, is_active=false WHERE id=2",
            "version": "UPDATE public.users SET session_version=1 WHERE id=17",
        }[problem]))
    before = records(reset_db)
    with pytest.raises(recovery.RecoveryRefused):
        apply(reset_db)
    assert records(reset_db) == before


def test_partial_update_failure_rolls_back(reset_db):
    def fail_second(conn, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE public.users SET password_hash") and parameters["id"] == 13:
            raise RuntimeError("synthetic failure")
    before = records(reset_db)
    event.listen(reset_db, "before_cursor_execute", fail_second)
    try:
        with pytest.raises(RuntimeError):
            apply(reset_db)
    finally:
        event.remove(reset_db, "before_cursor_execute", fail_second)
    assert records(reset_db) == before


def test_old_cookies_rejected_unrelated_cookie_preserved(reset_db):
    auth = Path(recovery.__file__).resolve().parents[1] / "app" / "auth"
    config = ModuleType("app.config")
    config.settings = SimpleNamespace(auth_secret_key="synthetic-cookie-key", session_ttl_seconds=3600,
                                     session_cookie_name="clerk_session")
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    with patch.dict("sys.modules", {"app.config": config}):
        cookies = load("reset_cookies", auth / "cookies.py")
    models = ModuleType("app.models")
    models.User = object
    database = ModuleType("app.database")
    database.get_db = lambda: None
    with patch.dict("sys.modules", {"app.config": config, "app.models": models,
                                    "app.database": database, "app.auth.cookies": cookies}):
        dependencies = load("reset_dependencies", auth / "dependencies.py")
    tokens = {user_id: cookies.create_session_cookie_value(user_id, session_version=0)
              for user_id in (*recovery.RESET_IDS, 2)}
    def authenticated(user_id):
        row = SimpleNamespace(**records(reset_db)[user_id])
        return dependencies.get_current_user(
            SimpleNamespace(cookies={"clerk_session": tokens[user_id]}),
            SimpleNamespace(get=lambda model, identity: row),
        )
    assert all(authenticated(user_id) is not None for user_id in tokens)
    apply(reset_db)
    assert all(authenticated(user_id) is None for user_id in recovery.RESET_IDS)
    assert authenticated(2) is not None


def test_cli_requires_owner_confirmation_before_prompt(monkeypatch):
    monkeypatch.setattr(recovery, "prompt_password", lambda *a: pytest.fail("Unexpected prompt"))
    with pytest.raises(SystemExit) as error:
        recovery.main(["reset-passwords"])
    assert error.value.code == 2


@pytest.mark.parametrize("problem", ["empty", "short", "mismatch", "duplicate", "control", "whitespace", "too-long", "cancel", "database-password"])
def test_invalid_input_never_connects_or_changes_records(reset_db, monkeypatch, capsys, problem):
    inputs = answers() + [DB_PASSWORD]
    if problem == "mismatch":
        inputs[5] = "mismatched-synthetic-confirmation"
    elif problem == "duplicate":
        inputs[2:4] = inputs[:2]
    elif problem == "database-password":
        inputs[6] = PASSWORDS[17]
    elif problem != "cancel":
        invalid = {"empty": "", "short": "short", "control": "synthetic\npassword",
                   "whitespace": " " * 12, "too-long": "x" * 1025}[problem]
        inputs[4:6] = [invalid, invalid]
    iterator = iter(inputs)
    def prompt(*args):
        if problem == "cancel":
            raise KeyboardInterrupt()
        return next(iterator)
    monkeypatch.setattr(recovery, "prompt_password", prompt)
    connect = Mock()
    monkeypatch.setattr(recovery, "recovery_engine", connect)
    before = records(reset_db)
    assert recovery.main(["reset-passwords", "--confirm-passwords-saved"]) == 1
    connect.assert_not_called()
    assert records(reset_db) == before
    output = capsys.readouterr()
    assert not output.out
    assert all(value not in output.err for value in PASSWORDS.values())


def test_cli_prompts_for_each_saved_password_and_redacts_success(reset_db, monkeypatch, capsys):
    from app.auth.passwords import verify_password
    iterator = iter(answers() + [DB_PASSWORD])
    prompts = []
    def prompt(label="Database password: "):
        prompts.append(label)
        return next(iterator)
    monkeypatch.setattr(recovery, "prompt_password", prompt)
    monkeypatch.setattr(recovery, "recovery_engine", lambda password: reset_db)
    assert recovery.main(["reset-passwords", "--confirm-passwords-saved"]) == 0
    assert prompts == [label for user_id in recovery.RESET_IDS for label in (
        f"Saved replacement password for user ID {user_id}: ",
        f"Confirm replacement password for user ID {user_id}: ",
    )] + ["Database password: "]
    rows = records(reset_db)
    assert all(verify_password(PASSWORDS[user_id], rows[user_id]["password_hash"]) for user_id in recovery.RESET_IDS)
    output = capsys.readouterr()
    assert output.out == "reset-passwords committed; perform read-only verification.\n"
    assert not output.err


def test_cli_redacts_passwords_and_hashes_on_partial_failure(reset_db, monkeypatch, capsys):
    iterator = iter(answers() + [DB_PASSWORD])
    monkeypatch.setattr(recovery, "prompt_password", lambda *a: next(iterator))
    monkeypatch.setattr(recovery, "recovery_engine", lambda password: reset_db)
    def fail_second(conn, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE public.users SET password_hash") and parameters["id"] == 13:
            raise RuntimeError(parameters["password_hash"] + PASSWORDS[13] + DB_PASSWORD)
    before = records(reset_db)
    event.listen(reset_db, "before_cursor_execute", fail_second)
    try:
        assert recovery.main(["reset-passwords", "--confirm-passwords-saved"]) == 1
    finally:
        event.remove(reset_db, "before_cursor_execute", fail_second)
    assert records(reset_db) == before
    output = capsys.readouterr()
    assert not output.out
    assert output.err == ("Recovery stopped during reset-passwords; outcome unconfirmed. "
                          "Verify state read-only before any retry.\n")


def test_concurrent_resets_commit_only_once(reset_db):
    barrier = Barrier(2)
    def attempt(_):
        barrier.wait(timeout=5)
        try:
            apply(reset_db)
            return "committed"
        except recovery.RecoveryRefused:
            return "refused"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [1, 2])) == ["committed", "refused"]
    assert all(records(reset_db)[user_id]["session_version"] == 1 for user_id in recovery.RESET_IDS)


@pytest.mark.parametrize("passwords", [None, {}, {1: "synthetic-password"}, {**PASSWORDS, 2: "unexpected-password"}])
def test_invalid_password_mapping_refused_before_connection(passwords):
    engine = Mock()
    with pytest.raises(recovery.RecoveryRefused):
        recovery.perform(engine, "reset-passwords", passwords=passwords)
    engine.connect.assert_not_called()
