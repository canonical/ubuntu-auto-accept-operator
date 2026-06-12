# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import jubilant

from . import APPNAME


def test_service_state_after_deploy(juju: jubilant.Juju, ubuntu_auto_accept_charm, lpuser_secret):
    """Deploy the charm via jubilant and wait until application is active."""
    juju.deploy(ubuntu_auto_accept_charm, app=APPNAME)

    if lpuser_secret:
        juju.config(APPNAME, {"lpuser_secret_id": lpuser_secret})

    juju.wait(jubilant.all_active, timeout=1200)
