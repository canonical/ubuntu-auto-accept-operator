# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""Shared fixtures for the unit tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_subprocess():
    """Fail loudly if a test reaches a real subprocess call.

    Unit tests must mock out the AutoAccept methods (and the charmlibs
    systemd/apt helpers they call) that touch the machine, rather than
    relying on an unmocked call to run against the real filesystem of
    whoever runs the tests.
    """
    with patch(
        "subprocess.run",
        side_effect=AssertionError(
            "unit test attempted to run a real subprocess; mock the AutoAccept method"
        ),
    ):
        yield
