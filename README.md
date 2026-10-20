# Pi Service Doctor

A small, dependency-free Raspberry Pi health checker with a friendly CLI, atomic JSON reports and a responsive web dashboard.

It performs read-only checks for system resources, temperature and throttling, systemd services and timers, failed units, TCP ports, HTTP endpoints and file freshness. A five-minute systemd timer builds the report; the browser only reads that cache and cannot execute commands.

## Quick install from Git

```bash
git clone https://github.com/snuffsprojects/pi-service-doctor.git
cd pi-service-doctor
sudo ./install.sh
```

The installer:

- discovers common active services and timers;
- creates a safe starter configuration;
- installs a hardened, unprivileged systemd collector;
- enables five-minute reports;
- installs the static dashboard under `/var/www/html/pi-service-doctor`;
- preserves configuration when run again for an upgrade.

If `/var/www/html` is your web-server root, open:

```text
http://YOUR-PI/pi-service-doctor/
```

The installer does not install or reconfigure nginx, Apache or another web server. Use `--no-web` for a CLI-only installation, or `--web-root PATH` for a different document root.

## Requirements

- A Linux system using systemd
- Python 3.10 or newer
- Optional Raspberry Pi `vcgencmd`; standard thermal sysfs is checked first
- Optional existing web server for the dashboard

No Python packages, Node modules, database or cloud account are required.

## Configuration

The automatic configuration is intentionally conservative. Edit:

```text
/etc/pi-service-doctor/config.json
```

Add the services, timers, ports, URLs and freshness-sensitive files that matter on your Pi. `config.example.json` documents every section. Targets support a friendly `label`; network and service checks support `required: false` when failure should be a warning rather than critical.

To safely regenerate suggestions without modifying the live configuration:

```bash
python3 configure.py --output suggested-config.json --non-interactive
```

Restarting is unnecessary after configuration changes. The next timer run reads the new file.

## CLI

After installation:

```bash
pi-service-doctor
pi-service-doctor --json
pi-service-doctor --version
```

Exit codes are `0` for healthy, `1` for warning/unknown and `2` for critical or invalid configuration. `--always-zero` is intended for schedulers so detected problems do not mark the checker itself as failed.

## Upgrade

```bash
git pull --ff-only
sudo ./install.sh
```

The installer replaces application and web assets but preserves `/etc/pi-service-doctor/config.json` and existing reports.

## Uninstall

```bash
sudo ./uninstall.sh
```

Configuration and reports are preserved by default. Use `sudo ./uninstall.sh --purge` to remove those too.

## Installer options

```text
--user USER          unprivileged account used for checks
--app-dir PATH       application installation directory
--config-dir PATH    configuration directory
--state-dir PATH     generated-report directory
--web-root PATH      existing web-server document root
--no-web             CLI and scheduled reports only
--no-systemd         stage files without installing services (testing)
```

## Security and privacy

Use the dashboard only on a trusted LAN or behind an authenticated reverse proxy. Reports can reveal hostnames, service names, ports and local paths. Local configuration and generated status are excluded by `.gitignore`; do not add secrets to labels or monitored URLs. See [SECURITY.md](SECURITY.md).

## Development

```bash
python3 -m unittest -v
python3 -m py_compile doctor.py configure.py
sh -n install.sh uninstall.sh
```

The project is released under the MIT License. Bundled Barlow font files are distributed under the SIL Open Font License included in `fonts/OFL-Barlow.txt`.
