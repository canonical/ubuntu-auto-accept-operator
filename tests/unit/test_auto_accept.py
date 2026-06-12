# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Unit tests for `src/auto_accept.py`."""

from subprocess import CalledProcessError
from unittest.mock import Mock

import pytest

import auto_accept
from auto_accept import AutoAccept


def test_install_packages_calls_apt_update_before_adding_packages(monkeypatch):
    called = []

    monkeypatch.setattr(auto_accept.apt, "update", lambda: called.append("update"))
    monkeypatch.setattr(auto_accept.apt, "add_package", lambda pkg: called.append(pkg))
    worker = AutoAccept()

    worker._install_packages()

    assert called[0] == "update"
    assert set(called[1:]) == set(auto_accept.PACKAGES)


def test_install_copies_scripts(monkeypatch):
    monkeypatch.setattr(AutoAccept, "_install_packages", lambda self: None)

    ops = []
    monkeypatch.setattr(
        auto_accept.shutil, "copy", lambda src, dst: ops.append(("copy", src, dst))
    )
    monkeypatch.setattr(
        auto_accept.os, "chmod", lambda path, mode: ops.append(("chmod", str(path)))
    )

    worker = AutoAccept()
    worker.install()

    assert ("copy", "src/script/auto-accept", "/usr/bin/auto-accept") in ops


def test_start_starts_auto_accept_service(monkeypatch):
    calls = []
    monkeypatch.setattr(auto_accept.systemd, "service_start", lambda *args: calls.append(args))

    worker = AutoAccept()
    worker.start()

    assert ("auto-accept.service", "--no-block") in calls


def test_run_auto_accept_starts_service(monkeypatch):
    starts = []
    monkeypatch.setattr(auto_accept.systemd, "service_start", lambda *args: starts.append(args))

    worker = AutoAccept()
    worker.run_auto_accept()

    assert ("auto-accept.service",) in starts


def test_last_run_failed_uses_systemd_failed_state(monkeypatch):
    monkeypatch.setattr(
        auto_accept.systemd,
        "service_failed",
        lambda service: service == "auto-accept.service",
    )

    worker = AutoAccept()

    assert worker.last_run_failed() is True


def test_setup_systemd_unit_writes_service_and_timer_with_proxy_environment(monkeypatch):
    monkeypatch.setenv("JUJU_CHARM_HTTP_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("JUJU_CHARM_HTTPS_PROXY", "https://secure.example:8443")

    worker = AutoAccept()

    def fake_read_text(self, encoding=None):
        return "[Service]\nExecStart=/bin/true" if self.suffix == ".service" else "[Timer]"

    written = {}

    def fake_write_text(self, text, encoding=None):
        written[str(self)] = text

    monkeypatch.setattr(auto_accept.Path, "read_text", fake_read_text)
    monkeypatch.setattr(auto_accept.Path, "write_text", fake_write_text)
    monkeypatch.setattr(
        auto_accept.Path, "mkdir", lambda self, parents=False, exist_ok=False: None
    )
    monkeypatch.setattr(auto_accept.systemd, "daemon_reload", lambda *args, **kwargs: None)

    worker.setup_systemd_unit()

    svc_path = "/etc/systemd/system/auto-accept.service"
    assert svc_path in written
    assert "Environment=HTTP_PROXY=http://proxy.example:8080" in written[svc_path]
    assert "Environment=HTTPS_PROXY=https://secure.example:8443" in written[svc_path]


def test_configure_schedule_writes_timer_and_reloads_systemd(monkeypatch):
    written = {}
    calls = []

    def fake_write_text(self, text, encoding=None):
        written[str(self)] = text

    monkeypatch.setattr(auto_accept.Path, "write_text", fake_write_text)
    monkeypatch.setattr(
        auto_accept.systemd,
        "daemon_reload",
        lambda *args: calls.append(("reload",) + args),
    )
    worker = AutoAccept()
    worker.configure_schedule()

    timer_path = "/etc/systemd/system/auto-accept.timer"
    assert timer_path in written
    assert "OnCalendar=hourly" in written[timer_path]
    assert ("reload",) in calls


def test_enable_schedule_enables_and_starts_timer(monkeypatch):
    calls = []
    monkeypatch.setattr(auto_accept.systemd, "service_enable", lambda *args: calls.append(args))

    worker = AutoAccept()
    worker.enable_schedule()

    assert ("--now", "auto-accept.timer") in calls


def test_disable_schedule_disables_and_stops_timer(monkeypatch):
    calls = []
    monkeypatch.setattr(auto_accept.systemd, "service_disable", lambda *args: calls.append(args))

    worker = AutoAccept()
    worker.disable_schedule()

    assert ("--now", "auto-accept.timer") in calls


def test_setup_systemd_units_only_sets_up_unit(monkeypatch):
    called = []
    monkeypatch.setattr(AutoAccept, "setup_systemd_unit", lambda self: called.append("setup"))
    monkeypatch.setattr(AutoAccept, "configure_schedule", lambda self: called.append("schedule"))

    worker = AutoAccept()
    worker.setup_systemd_units()

    assert called == ["setup"]


def test_enable_schedule_raises_when_enable_fails(monkeypatch):
    monkeypatch.setattr(auto_accept.Path, "read_text", lambda self, encoding=None: "[Service]")
    monkeypatch.setattr(auto_accept.Path, "write_text", lambda self, t, encoding=None: None)
    monkeypatch.setattr(auto_accept.Path, "mkdir", lambda self, parents=True, exist_ok=True: None)

    def bad_enable(*args, **kwargs):
        raise CalledProcessError(3, "systemctl")

    monkeypatch.setattr(auto_accept.systemd, "service_enable", bad_enable)
    worker = AutoAccept()

    with pytest.raises(CalledProcessError):
        worker.enable_schedule()


def test_install_packages_raises_when_package_not_found(monkeypatch):
    monkeypatch.setattr(auto_accept.apt, "update", lambda: None)

    def bad_add(_):
        raise auto_accept.PackageNotFoundError("missing")

    monkeypatch.setattr(auto_accept.apt, "add_package", bad_add)
    worker = AutoAccept()

    with pytest.raises(auto_accept.PackageNotFoundError):
        worker._install_packages()


def test_install_packages_raises_when_package_installation_fails(monkeypatch):
    monkeypatch.setattr(auto_accept.apt, "update", lambda: None)

    def bad_add(_):
        raise auto_accept.PackageError("install failed")

    monkeypatch.setattr(auto_accept.apt, "add_package", bad_add)
    worker = AutoAccept()

    with pytest.raises(auto_accept.PackageError):
        worker._install_packages()


def test_start_raises_when_systemd_start_fails(monkeypatch):
    monkeypatch.setattr(
        auto_accept.systemd,
        "service_start",
        Mock(side_effect=CalledProcessError(1, "systemctl")),
    )

    worker = AutoAccept()

    with pytest.raises(CalledProcessError):
        worker.start()
