# Pi Service Doctor

A small, dependency-free Raspberry Pi health checker with human-readable CLI output, atomic JSON reports and a responsive static dashboard.

It performs read-only checks for system resources, temperature and throttling, systemd services and timers, failed units, TCP ports, HTTP endpoints and file freshness. Checks are configured in JSON, so the project can monitor another Pi without source changes.

## Quick start

```bash
cp config.example.json config.json
python3 doctor.py
python3 doctor.py --output status.json --always-zero
```

Open `index.html` through a web server after producing `status.json`. The dashboard never executes system commands; it only reads the cached report.

## Exit codes

- `0`: all checks healthy
- `1`: warning or unknown check
- `2`: critical check or invalid configuration

Use `--always-zero` from a timer so a detected problem does not turn the collector itself into a failed systemd unit.

## Configuration

Copy `config.example.json` to `config.json`. Local configuration and generated status are ignored by Git. Every service, timer, port, URL and file target supports a user-facing `label`; network and service checks also support `required: false` to make failure a warning instead of critical.

`ignoreFailedUnits` accepts shell-style patterns. This is useful for transient `systemd-run` units which otherwise remain listed as failed after a one-off diagnostic command.

## systemd

Adjust paths in the included service if the project is installed somewhere other than `/var/www/html/intranet/pi-service-doctor`, then install:

```bash
sudo install -m 0644 pi-service-doctor.service /etc/systemd/system/
sudo install -m 0644 pi-service-doctor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-service-doctor.timer
```

The included service runs without root privileges and uses systemd filesystem and privilege restrictions.

## Privacy

Do not commit `config.json` or `status.json` if they contain private hostnames, addresses or paths. The provided `.gitignore` excludes both. The example configuration contains only generic loopback targets.

## Requirements

- Python 3.10 or newer
- Linux `/proc` for memory and uptime metrics
- systemd for service/timer checks
- `vcgencmd` is optional; standard thermal sysfs is tried first

Released under the MIT License.
