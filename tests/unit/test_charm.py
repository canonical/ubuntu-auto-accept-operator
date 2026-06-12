# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Unit tests for the charm."""

from subprocess import CalledProcessError
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import ops
import pytest
from charmlibs.apt import PackageError, PackageNotFoundError
from ops.testing import (
    ActiveStatus,
    BlockedStatus,
    Context,
    State,
)

from charm import UbuntuAutoAcceptCharm


@pytest.fixture
def ctx():
    return Context(UbuntuAutoAcceptCharm)


@pytest.fixture
def base_state():
    return State(leader=True)


@pytest.fixture
def enabled_state():
    return State(leader=True, config={"enabled": True})


@patch("charm.AutoAccept.install")
@patch("charm.AutoAccept.setup_systemd_units")
def test_install_event_sets_active_status_on_success(
    setup_units_mock, install_mock, ctx, base_state
):
    state_in = State(leader=True)

    out = ctx.run(ctx.on.install(), state_in)

    assert out.unit_status == ActiveStatus()
    install_mock.assert_called_once()
    setup_units_mock.assert_called_once()


@patch("charm.AutoAccept.install")
@pytest.mark.parametrize(
    "exception",
    [
        PackageError,
        PackageNotFoundError,
        CalledProcessError(1, "foo"),
    ],
)
def test_install_event_blocks_charm_on_environment_setup_failure(
    install_mock, exception, ctx, base_state
):
    install_mock.side_effect = exception

    out = ctx.run(ctx.on.install(), base_state)

    assert out.unit_status == BlockedStatus(
        "Failed to set up the environment. Check `juju debug-log` for details."
    )


@patch("charm.AutoAccept.start")
@patch("charm.AutoAccept.enable_schedule")
@patch("charm.AutoAccept.configure_schedule")
@patch("charm.AutoAccept.configure_lpoauthkey")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_start_event_sets_active_status_when_token_configured(
    lp_oauth_prop_mock,
    configure_lpoauth_mock,
    configure_schedule_mock,
    enable_schedule_mock,
    start_mock,
    ctx,
    enabled_state,
):
    lp_oauth_prop_mock.return_value = "fake-token"
    configure_lpoauth_mock.return_value = True

    out = ctx.run(ctx.on.start(), enabled_state)

    assert out.unit_status == ActiveStatus()
    configure_lpoauth_mock.assert_called_once_with("fake-token")
    configure_schedule_mock.assert_called_once_with()
    enable_schedule_mock.assert_called_once_with()
    start_mock.assert_called_once()


@patch("charm.AutoAccept.disable_schedule")
@patch("charm.AutoAccept.configure_lpoauthkey")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_start_event_sets_paused_status_when_disabled_and_credentials_present(
    lp_oauth_prop_mock, configure_lpoauth_mock, disable_schedule_mock, ctx, base_state
):
    lp_oauth_prop_mock.return_value = "fake-token"
    configure_lpoauth_mock.return_value = True

    out = ctx.run(ctx.on.start(), base_state)

    assert out.unit_status == ActiveStatus("Paused by configuration.")
    configure_lpoauth_mock.assert_called_once_with("fake-token")
    disable_schedule_mock.assert_called_once_with()


def test_start_event_blocks_charm_when_lp_secret_not_configured(ctx, base_state):
    out = ctx.run(ctx.on.start(), base_state)

    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


def test_start_event_blocks_charm_when_enabled_and_lp_secret_not_configured(ctx, enabled_state):
    out = ctx.run(ctx.on.start(), enabled_state)

    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


@patch("charm.AutoAccept.start")
@patch("charm.AutoAccept.enable_schedule")
@patch("charm.AutoAccept.configure_schedule")
@patch("charm.AutoAccept.configure_lpoauthkey")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_start_event_blocks_charm_when_service_start_fails(
    lp_oauth_prop_mock,
    configure_lpoauth_mock,
    configure_schedule_mock,
    enable_schedule_mock,
    start_mock,
    ctx,
    enabled_state,
):
    lp_oauth_prop_mock.return_value = "fake-token"
    configure_lpoauth_mock.return_value = True
    start_mock.side_effect = CalledProcessError(1, "foo")

    out = ctx.run(ctx.on.start(), enabled_state)

    assert out.unit_status == BlockedStatus(
        "Failed to start services. Check `juju debug-log` for details."
    )


@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
@patch("charm.AutoAccept.configure_lpoauthkey")
@patch("charm.AutoAccept.configure_schedule")
@patch("charm.AutoAccept.enable_schedule")
def test_config_changed_event_configures_oauth_and_schedule(
    enable_schedule_mock,
    configure_schedule_mock,
    configure_lpoauth_mock,
    lp_oauth_prop_mock,
    ctx,
    enabled_state,
):
    lp_oauth_prop_mock.return_value = "fake-token"
    configure_lpoauth_mock.return_value = True

    out = ctx.run(ctx.on.config_changed(), enabled_state)

    assert out.unit_status == ActiveStatus()
    configure_lpoauth_mock.assert_called_once_with("fake-token")
    configure_schedule_mock.assert_called_once_with()
    enable_schedule_mock.assert_called_once_with()


@patch("charm.AutoAccept.disable_schedule")
@patch("charm.AutoAccept.configure_lpoauthkey")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_config_changed_event_sets_paused_status_when_disabled_and_credentials_present(
    lp_oauth_prop_mock, configure_lpoauth_mock, disable_schedule_mock, ctx, base_state
):
    lp_oauth_prop_mock.return_value = "fake-token"
    configure_lpoauth_mock.return_value = True

    out = ctx.run(ctx.on.config_changed(), base_state)

    assert out.unit_status == ActiveStatus("Paused by configuration.")
    configure_lpoauth_mock.assert_called_once_with("fake-token")
    disable_schedule_mock.assert_called_once_with()


def test_config_changed_event_blocks_charm_when_lp_secret_not_configured(ctx, base_state):
    out = ctx.run(ctx.on.config_changed(), base_state)

    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


def test_config_changed_event_blocks_charm_when_enabled_and_lp_secret_not_configured(
    ctx, enabled_state
):
    out = ctx.run(ctx.on.config_changed(), enabled_state)

    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


@patch("charm.AutoAccept.run_auto_accept")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_accept_now_action_triggers_auto_accept_and_logs_message(
    lp_oauth_prop_mock, run_auto_accept_mock, ctx, base_state
):
    lp_oauth_prop_mock.return_value = "fake-token"

    out = ctx.run(ctx.on.action("accept-now"), base_state)

    assert ctx.action_logs == ["Running auto-accept"]
    assert out.unit_status == ActiveStatus()
    run_auto_accept_mock.assert_called_once()


@patch("charm.AutoAccept.run_auto_accept")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_accept_now_action_sets_status_message_when_run_fails(
    lp_oauth_prop_mock, run_auto_accept_mock, ctx, base_state
):
    lp_oauth_prop_mock.return_value = "fake-token"
    run_auto_accept_mock.side_effect = CalledProcessError(1, "sync")

    out = ctx.run(ctx.on.action("accept-now"), base_state)

    assert out.unit_status == ActiveStatus(
        "Failed to run auto-accept. Check `juju debug-log` for details."
    )


def test_accept_now_action_blocks_when_lp_secret_not_configured(ctx, base_state):
    out = ctx.run(ctx.on.action("accept-now"), base_state)

    assert ctx.action_logs == ["Launchpad oauth token config missing."]
    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


def test_update_status_sets_paused_when_disabled(ctx, base_state):
    out = ctx.run(ctx.on.update_status(), base_state)

    assert out.unit_status == ActiveStatus("Paused by configuration.")


def test_update_status_blocks_when_enabled_and_lp_secret_not_configured(ctx, enabled_state):
    out = ctx.run(ctx.on.update_status(), enabled_state)

    assert out.unit_status == BlockedStatus("Launchpad oauth token config missing.")


def test_update_status_sets_paused_when_disabled_regardless_of_credentials(ctx, base_state):
    out = ctx.run(ctx.on.update_status(), base_state)

    assert out.unit_status == ActiveStatus("Paused by configuration.")


@patch("charm.AutoAccept.last_run_failed")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_update_status_blocks_when_auto_accept_failed(
    lp_oauth_prop_mock, last_run_failed_mock, ctx, enabled_state
):
    lp_oauth_prop_mock.return_value = "fake-token"
    last_run_failed_mock.return_value = True

    out = ctx.run(ctx.on.update_status(), enabled_state)

    assert out.unit_status == BlockedStatus(
        "auto-accept service failed. Check `juju debug-log` for details."
    )


@patch("charm.AutoAccept.last_run_failed")
@patch(
    "charm.UbuntuAutoAcceptCharm._lpuser_lp_oauthkey",
    new_callable=PropertyMock,
)
def test_update_status_sets_active_when_healthy(
    lp_oauth_prop_mock, last_run_failed_mock, ctx, enabled_state
):
    lp_oauth_prop_mock.return_value = "fake-token"
    last_run_failed_mock.return_value = False

    out = ctx.run(ctx.on.update_status(), enabled_state)

    assert out.unit_status == ActiveStatus()


def test_lpuser_secret_property_returns_none_when_secret_not_found():
    dummy = SimpleNamespace()
    dummy.config = {"lpuser_secret_id": "missing"}
    dummy.model = MagicMock()
    dummy.model.get_secret.side_effect = ops.SecretNotFoundError

    result = UbuntuAutoAcceptCharm._lpuser_secret.fget(dummy)

    assert result is None


def test_lpuser_lp_oauthkey_property_returns_none_when_key_missing_from_secret():
    dummy = SimpleNamespace()
    fake_secret = MagicMock()
    fake_secret.get_content.return_value = {}
    dummy._lpuser_secret = fake_secret

    result = UbuntuAutoAcceptCharm._lpuser_lp_oauthkey.fget(dummy)

    assert result is None
