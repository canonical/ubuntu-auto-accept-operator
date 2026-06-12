#!/usr/bin/env python3
# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Charmed Operator for Ubuntu Auto Accept."""

import logging
import shutil
from subprocess import CalledProcessError, SubprocessError

import ops
from charmlibs.apt import PackageError, PackageNotFoundError

from auto_accept import AutoAccept

logger = logging.getLogger(__name__)


class UbuntuAutoAcceptCharm(ops.CharmBase):
    """Charmed Operator for Ubuntu Auto Accept."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.upgrade_charm, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.accept_now_action, self._on_accept_now)

        self._auto_accept = AutoAccept()

    @property
    def _enabled(self) -> bool:
        try:
            return bool(self.config["enabled"])
        except KeyError:
            logger.warning("enabled config not available, defaulting to paused state.")
            return False

    def _pause(self) -> bool:
        try:
            self._auto_accept.disable_schedule()
        except CalledProcessError as e:
            logger.warning("Failed to disable auto-accept schedule: %s", e)
            self.unit.status = ops.BlockedStatus(
                "Failed to pause auto-accept schedule. Check `juju debug-log` for details."
            )
            return False

        self.unit.status = ops.ActiveStatus("Paused by configuration.")
        return True

    @property
    def _lpuser_secret(self) -> ops.model.Secret | None:
        secret_id: str = ""

        try:
            secret_id = str(self.config["lpuser_secret_id"])
        except KeyError:
            logger.warning("lpuser_secret_id config not available, unable to extract keys.")
            return None

        try:
            return self.model.get_secret(id=secret_id)
        except (ops.SecretNotFoundError, ops.model.ModelError):
            logger.warning("Failed to get lpuser secret with id %s", secret_id)

        return None

    @property
    def _lpuser_lp_oauthkey(self) -> str | None:
        secret = self._lpuser_secret

        if secret is not None:
            logger.debug("config - got secret id %s, returning key lpoauthkey", secret)
            try:
                return secret.get_content(refresh=True)["lpoauthkey"]
            except KeyError:
                logger.warning("lpoauthkey not found in lpuser secret.")

        return None

    def _on_install(self, event: ops.EventBase):
        """Handle install and upgrade events."""
        self.unit.status = ops.MaintenanceStatus("Setting up environment")
        try:
            self._auto_accept.install()
            self._auto_accept.setup_systemd_units()
        except (
            CalledProcessError,
            SubprocessError,
            PackageError,
            PackageNotFoundError,
            ValueError,
            IOError,
            OSError,
            shutil.Error,
        ) as e:
            logger.warning("Failed to set up the environment: %s", e)
            self.unit.status = ops.BlockedStatus(
                "Failed to set up the environment. Check `juju debug-log` for details."
            )
            return
        self.unit.status = ops.ActiveStatus()

    def _on_start(self, event: ops.StartEvent):
        """Trigger an initial auto-accept run."""
        lp_key_data = self._lpuser_lp_oauthkey
        if lp_key_data is None:
            logger.warning("Launchpad credentials unavailable, unable to run auto-accept.")
            self.unit.status = ops.BlockedStatus("Launchpad oauth token config missing.")
            return

        self.unit.status = ops.MaintenanceStatus("Starting auto-accept")
        try:
            if not self._auto_accept.configure_lpoauthkey(lp_key_data):
                self.unit.status = ops.BlockedStatus("Failed to update Launchpad oauth token.")
                return
            if not self._enabled:
                self._pause()
                return
            self._auto_accept.configure_schedule()
            self._auto_accept.enable_schedule()
            self._auto_accept.start()
        except (CalledProcessError, OSError) as e:
            logger.warning("Failed to start services: %s", e)
            self.unit.status = ops.BlockedStatus(
                "Failed to start services. Check `juju debug-log` for details."
            )
            return
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event):
        """Update configuration."""
        logger.debug("config changed event")
        self.unit.status = ops.MaintenanceStatus("Updating configuration")

        lp_key_data = self._lpuser_lp_oauthkey
        if lp_key_data is None:
            logger.warning("Launchpad credentials unavailable, unable to run auto-accept.")
            self.unit.status = ops.BlockedStatus("Launchpad oauth token config missing.")
            return
        logger.debug("config - got lpoauthkey (length %d)", len(lp_key_data))
        if not self._auto_accept.configure_lpoauthkey(lp_key_data):
            self.unit.status = ops.BlockedStatus("Failed to update Launchpad oauth token.")
            return
        logger.debug("config change done - lp oauth key set")

        if not self._enabled:
            self._pause()
            return

        try:
            self._auto_accept.configure_schedule()
            self._auto_accept.enable_schedule()
        except (CalledProcessError, OSError) as e:
            logger.warning("Failed to write auto-accept configuration: %s", e)
            self.unit.status = ops.BlockedStatus(
                "Failed to write auto-accept configuration. Check `juju debug-log` for details."
            )
            return

        self.unit.status = ops.ActiveStatus()

    def _on_accept_now(self, event: ops.ActionEvent):
        """Trigger an immediate auto-accept execution."""
        if self._lpuser_lp_oauthkey is None:
            event.log("Launchpad oauth token config missing.")
            self.unit.status = ops.BlockedStatus("Launchpad oauth token config missing.")
            return

        self.unit.status = ops.MaintenanceStatus("Running auto-accept")

        try:
            event.log("Running auto-accept")
            self._auto_accept.run_auto_accept()
        except (CalledProcessError, IOError):
            event.log("auto-accept run failed")
            self.unit.status = ops.ActiveStatus(
                "Failed to run auto-accept. Check `juju debug-log` for details."
            )
            return
        self.unit.status = ops.ActiveStatus()

    def _on_update_status(self, event: ops.EventBase):
        """Reflect auto-accept health in Juju status."""
        if not self._enabled:
            self.unit.status = ops.ActiveStatus("Paused by configuration.")
            return

        if self._lpuser_lp_oauthkey is None:
            self.unit.status = ops.BlockedStatus("Launchpad oauth token config missing.")
            return

        if self._auto_accept.last_run_failed():
            self.unit.status = ops.BlockedStatus(
                "auto-accept service failed. Check `juju debug-log` for details."
            )
            return

        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuAutoAcceptCharm)
