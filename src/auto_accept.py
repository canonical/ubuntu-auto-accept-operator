# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Representation of a single Ubuntu auto-accept worker."""

import logging
import os
import shutil
from pathlib import Path

from charmlibs import apt, pathops, systemd
from charmlibs.apt import PackageError, PackageNotFoundError

logger = logging.getLogger(__name__)

PACKAGES = [
    "python3-launchpadlib",
    "ubuntu-dev-tools",
]

AUTO_ACCEPT_SERVICE = "auto-accept"
AUTO_ACCEPT_RUNNER_PATH = Path("/usr/bin/run-auto-accept")
LP_OAUTH_KEY_PATH = "/home/ubuntu/.config/lp-ubuntu-auto-accept-bot.oauth"


class AutoAccept:
    """Represent an instance running Ubuntu auto-accept."""

    def __init__(self):
        logger.debug("AutoAccept class init")
        self.env = os.environ.copy()
        self.proxies = {}
        juju_http_proxy = self.env.get("JUJU_CHARM_HTTP_PROXY")
        juju_https_proxy = self.env.get("JUJU_CHARM_HTTPS_PROXY")
        if juju_http_proxy:
            logger.debug("Setting HTTP_PROXY env to %s", juju_http_proxy)
            self.env["HTTP_PROXY"] = juju_http_proxy
            self.proxies["http"] = juju_http_proxy
        if juju_https_proxy:
            logger.debug("Setting HTTPS_PROXY env to %s", juju_https_proxy)
            self.env["HTTPS_PROXY"] = juju_https_proxy
            self.proxies["https"] = juju_https_proxy

    def _install_packages(self):
        """Install required apt packages."""
        apt.update()
        logger.debug("Apt index refreshed.")

        for package in PACKAGES:
            try:
                apt.add_package(package)
                logger.debug("Package %s installed", package)
            except PackageNotFoundError:
                logger.error("Failed to find package %s in package cache", package)
                raise
            except PackageError as e:
                logger.error("Failed to install %s: %s", package, e)
                raise

    def install(self):
        """Set up environment required for auto-accept."""
        self._install_packages()

        shutil.copy("src/script/auto-accept", "/usr/bin/auto-accept")
        shutil.copy("src/script/run-auto-accept", AUTO_ACCEPT_RUNNER_PATH)
        os.chmod("/usr/bin/auto-accept", 0o755)
        os.chmod(AUTO_ACCEPT_RUNNER_PATH, 0o755)

    def start(self):
        """Trigger auto-accept asynchronously once."""
        systemd.service_start(f"{AUTO_ACCEPT_SERVICE}.service", "--no-block")

    def configure_lpoauthkey(self, lp_key_data: str):
        """Create or refresh the credentials file for launchpad access."""
        lp_key_file = pathops.LocalPath(LP_OAUTH_KEY_PATH)
        parent_dir = lp_key_file.parent
        os.makedirs(parent_dir, exist_ok=True)

        key_success = False
        try:
            lp_key_file.write_text(
                lp_key_data,
                mode=0o600,
                user="ubuntu",
                group="ubuntu",
            )
            key_success = True
        except (FileNotFoundError, NotADirectoryError) as e:
            logger.error(
                "Failed to create lp credentials entry due to directory issues: %s",
                str(e),
            )
        except LookupError as e:
            logger.error(
                "Failed to create lp credentials entry due to issues with root user: %s",
                str(e),
            )
        except PermissionError as e:
            logger.error(
                "Failed to create lp credentials entry due to permission issues: %s",
                str(e),
            )
        if key_success:
            logger.debug(
                "configure_lpoauthkey: written lp oauth key (length %d) to %s",
                len(lp_key_data),
                lp_key_file,
            )
        return key_success

    def configure_schedule(self):
        """Write an hourly timer unit."""
        timer_content = Path(f"src/systemd/{AUTO_ACCEPT_SERVICE}.timer").read_text(
            encoding="utf-8"
        )

        timer_path = Path(f"/etc/systemd/system/{AUTO_ACCEPT_SERVICE}.timer")
        timer_path.write_text(timer_content, encoding="utf-8")
        systemd.daemon_reload()

    def enable_schedule(self):
        """Enable and start the auto-accept timer."""
        systemd.service_enable("--now", f"{AUTO_ACCEPT_SERVICE}.timer")

    def disable_schedule(self):
        """Disable and stop the auto-accept timer."""
        systemd.service_disable("--now", f"{AUTO_ACCEPT_SERVICE}.timer")

    def run_auto_accept(self):
        """Trigger a blocking execution of the auto-accept service."""
        systemd.service_start(f"{AUTO_ACCEPT_SERVICE}.service")

    def last_run_failed(self) -> bool:
        """Report whether the auto-accept service is currently marked as failed."""
        return systemd.service_failed(f"{AUTO_ACCEPT_SERVICE}.service")

    def setup_systemd_unit(self):
        """Set up auto-accept service and timer with proxy configuration."""
        systemd_unit_location = Path("/etc/systemd/system")
        systemd_unit_location.mkdir(parents=True, exist_ok=True)

        service_content = Path(f"src/systemd/{AUTO_ACCEPT_SERVICE}.service").read_text(
            encoding="utf-8"
        )
        timer_content = Path(f"src/systemd/{AUTO_ACCEPT_SERVICE}.timer").read_text(
            encoding="utf-8"
        )

        proxy_env_vars = ""
        if "http" in self.proxies:
            proxy_env_vars += "\nEnvironment=HTTP_PROXY=" + self.proxies["http"]
        if "https" in self.proxies:
            proxy_env_vars += "\nEnvironment=HTTPS_PROXY=" + self.proxies["https"]

        service_content += proxy_env_vars
        (systemd_unit_location / f"{AUTO_ACCEPT_SERVICE}.service").write_text(
            service_content, encoding="utf-8"
        )
        (systemd_unit_location / f"{AUTO_ACCEPT_SERVICE}.timer").write_text(
            timer_content, encoding="utf-8"
        )
        systemd.daemon_reload()

    def setup_systemd_units(self):
        """Set up the auto-accept service and timer."""
        self.setup_systemd_unit()
