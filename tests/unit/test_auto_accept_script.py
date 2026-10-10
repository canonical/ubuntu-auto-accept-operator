# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Unit tests for `src/script/auto-accept` and its systemd service unit."""

import runpy
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = "src/script/auto-accept"


@pytest.fixture
def launchpad(monkeypatch):
    pkg = MagicMock(package_name="hello", package_version="1.0")
    lp = MagicMock()
    lp.distributions["ubuntu"].getSeries.return_value.status = "Active Development"
    lp.distributions["ubuntu"].getSeries.return_value.getPackageUploads.return_value = [pkg]
    lp.packagesets.setsIncludingSource.return_value = []

    fake_launchpad = MagicMock()
    fake_launchpad.login_with.return_value = lp
    module = types.ModuleType("launchpadlib.launchpad")
    module.Launchpad = fake_launchpad
    monkeypatch.setitem(sys.modules, "launchpadlib", types.ModuleType("launchpadlib"))
    monkeypatch.setitem(sys.modules, "launchpadlib.launchpad", module)
    monkeypatch.setattr(sys, "argv", [SCRIPT])
    return types.SimpleNamespace(login_with=fake_launchpad.login_with, pkg=pkg)


def _seeded_in_ubuntu(monkeypatch, stdout="", stderr="", returncode=0):
    run = MagicMock(
        return_value=subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)
    )
    monkeypatch.setattr(subprocess, "run", run)
    return run


def test_service_unit_sets_start_timeout():
    content = Path("src/systemd/auto-accept.service").read_text()

    assert "TimeoutStartSec=45min" in content


def test_script_logs_in_to_launchpad_with_timeout(monkeypatch, launchpad):
    _seeded_in_ubuntu(monkeypatch)

    runpy.run_path(SCRIPT)

    assert launchpad.login_with.call_args.kwargs["timeout"] == 60


def test_script_runs_seeded_in_ubuntu_with_timeout(monkeypatch, launchpad):
    run = _seeded_in_ubuntu(monkeypatch)

    runpy.run_path(SCRIPT)

    assert run.call_args.kwargs["timeout"] == 300
    assert run.call_args.kwargs["capture_output"] is True


def test_script_skips_package_when_seeded_in_ubuntu_times_out(monkeypatch, launchpad, capsys):
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.TimeoutExpired("seeded-in-ubuntu", 300)),
    )

    runpy.run_path(SCRIPT)

    launchpad.pkg.acceptFromQueue.assert_not_called()
    assert "seeded-in-ubuntu timed out" in capsys.readouterr().out


def test_script_skips_package_when_seeded_in_ubuntu_fails(monkeypatch, launchpad):
    _seeded_in_ubuntu(monkeypatch, stderr="boom", returncode=1)

    runpy.run_path(SCRIPT)

    launchpad.pkg.acceptFromQueue.assert_not_called()


def test_script_skips_package_when_seeded_in_non_whitelisted_seed(monkeypatch, launchpad):
    _seeded_in_ubuntu(monkeypatch, stdout="hello 1.0 is seeded in:\n  ubuntu: desktop\n")

    runpy.run_path(SCRIPT)

    launchpad.pkg.acceptFromQueue.assert_not_called()


def test_script_accepts_unseeded_package(monkeypatch, launchpad):
    _seeded_in_ubuntu(monkeypatch, stdout="hello 1.0 is not seeded\n")

    runpy.run_path(SCRIPT)

    launchpad.pkg.acceptFromQueue.assert_called_once()
