"""Startup diagnostics must not disclose connection values or exception details."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PARTS = ("canary_user_728", "canary_password_439", "canary_host_651",
         "canary_database_892", "canary_token_317")
URL = f"postgresql://{PARTS[0]}:{PARTS[1]}@{PARTS[2]}/{PARTS[3]}?token={PARTS[4]}"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helper(monkeypatch):
    module = load_script("wait_for_db")
    # Never load application settings, environment files, or a real database.
    monkeypatch.setattr(module, "get_db_url", lambda: URL)
    monkeypatch.setattr(module, "parse_args", lambda: (
        SimpleNamespace(timeout=2, interval=1, max_interval=10, quiet=False), []))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return module


def safe_output(capsys):
    captured = capsys.readouterr()
    output = captured.out + captured.err
    for value in (URL, *PARTS):
        assert value not in output
    return output


@pytest.mark.parametrize("outcomes, ticks, expected, diagnostic", [
    ([True], [0], 0, "Database is ready (attempt 1)"),
    ([False, True], [0, 1], 0, "Database is ready (attempt 2)"),
    ([False, False], [0, 1, 2], 1, "Timed out after 2s"),
])
def test_readiness_diagnostics(helper, monkeypatch, capsys, outcomes, ticks, expected, diagnostic):
    results, clock = iter(outcomes), iter(ticks)
    monkeypatch.setattr(helper, "db_ready", lambda url: next(results))
    monkeypatch.setattr(helper.time, "time", lambda: next(clock))
    assert helper.main() == expected
    output = safe_output(capsys)
    assert "Checking database readiness" in output
    assert diagnostic in output
    if len(outcomes) > 1:
        assert "Not ready yet; retrying in 1.0s (attempt 1)" in output


@pytest.mark.parametrize("failure_at", ["engine", "connect", "execute"])
def test_database_exceptions_are_not_logged(helper, monkeypatch, capsys, failure_at):
    error = RuntimeError(f"Connection failed: {URL}")
    engine = MagicMock()
    factory = MagicMock(return_value=engine)
    if failure_at == "engine":
        factory.side_effect = error
    elif failure_at == "connect":
        engine.connect.side_effect = error
    else:
        engine.connect.return_value.__enter__.return_value.execute.side_effect = error
    monkeypatch.setattr(helper, "make_engine", factory)
    clock = iter([0, 2])
    monkeypatch.setattr(helper.time, "time", lambda: next(clock))
    assert helper.main() == 1
    factory.assert_called_once_with(URL)
    assert "Timed out after 2s" in safe_output(capsys)


def test_followup_arguments_are_not_logged(helper, monkeypatch, capsys):
    monkeypatch.setattr(helper, "parse_args", lambda: (
        SimpleNamespace(timeout=2, interval=1, max_interval=10, quiet=False),
        ["synthetic-command", URL]))
    monkeypatch.setattr(helper, "db_ready", lambda _: True)
    call = MagicMock(return_value=7)
    monkeypatch.setattr(helper.subprocess, "call", call)
    assert helper.main() == 7
    assert URL in call.call_args.args[0]
    assert "Executing follow-up command" in safe_output(capsys)


@pytest.mark.parametrize("in_container", [True, False])
@pytest.mark.parametrize("returncode", [0, 1])
def test_docker_start_helper_invocation(monkeypatch, capsys, in_container, returncode):
    startup = load_script("docker_start")
    monkeypatch.setattr(startup.os.path, "exists", lambda _: in_container)
    call = MagicMock(return_value=returncode)
    monkeypatch.setattr(startup.subprocess, "call", call)
    if returncode:
        with pytest.raises(SystemExit) as exc:
            startup.wait_for_db(URL, timeout=120)
        assert exc.value.code == returncode
    else:
        startup.wait_for_db(URL, timeout=120)
    script = "scripts/wait_for_db.py" if in_container else "backend/scripts/wait_for_db.py"
    call.assert_called_once_with([startup.sys.executable, script, "--timeout", "120"])
    safe_output(capsys)
