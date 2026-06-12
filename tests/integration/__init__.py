# Copyright 2025 Canonical
# See LICENSE file for licensing details.
import functools
import logging
import sys
import time

import jubilant

APPNAME = "ubuntu-auto-accept"


def retry(retry_num, retry_sleep_sec):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retry_num):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if i >= retry_num - 1:
                        raise Exception(f"Exceeded {retry_num} retries") from exc
                    logging.error(
                        "func %s failure %d/%d: %s", func.__name__, i + 1, retry_num, exc
                    )
                    time.sleep(retry_sleep_sec)

        return wrapper

    return decorator


def address(juju: jubilant.Juju, app: str = APPNAME):
    """Report the IP address of the application."""
    return juju.status().apps[app].units[f"{app}/0"].public_address


@retry(retry_num=80, retry_sleep_sec=120)
def wait_oneshot_finished(juju: jubilant.Juju, unit: str, service: str):
    """Wait on service to complete after it has started."""
    state = juju.ssh(unit, "systemctl show -p ActiveState -p SubState --value " + service)
    ready = state == "inactive\ndead\n"
    logging.debug(f"{sys._getframe().f_code.co_name} - state: {state}")
    logging.debug(f"{sys._getframe().f_code.co_name} - ready: {ready}")
    assert ready, f"State is {state}, expected finish is 'inactive\ndead\n'"
