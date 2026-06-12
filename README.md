# Ubuntu Auto Accept Operator

**Ubuntu Auto Accept Operator** is a [charm](https://juju.is/charms-architecture)
that runs the Ubuntu archive `auto-accept` job every hour.
It accepts safe uploads from the `$devel-proposed` unapproved queue,
skipping any source that is seeded or belongs to a tracked packageset.
Seed membership is checked with `seeded-in-ubuntu` from the `ubuntu-dev-tools`
package.

## Behavior

- Scheduled runs every hour via `auto-accept.timer` when enabled.
- Manual trigger action `accept-now`.

## Configuration

- `enabled` (boolean, default: `false`):
	Controls whether scheduled auto-accept runs are active. When set to `false`,
	the charm disables the timer and reports a paused status.
- `lpuser_secret_id` (secret):
	Juju secret ID containing the Launchpad OAuth token under key `lpoauthkey`.
	This token must belong to a Launchpad user with queue management access.

## Basic usage

```bash
juju deploy ubuntu-auto-accept
juju config ubuntu-auto-accept lpuser_secret_id=secret:<uuid>
juju config ubuntu-auto-accept enabled=true
```

Trigger a manual run:

```bash
juju run ubuntu-auto-accept/0 accept-now
```

Pause and resume scheduled runs:

```bash
# Pause
juju config ubuntu-auto-accept enabled=false

# Resume
juju config ubuntu-auto-accept enabled=true
```

## Service inspection

```bash
systemctl list-timers --all auto-accept.timer
systemctl status auto-accept.service
journalctl -u auto-accept.service
```

## Testing

For information on tests and development workflows, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Ubuntu Auto Accept Operator is released under the [GPL-3.0 license](LICENSE).