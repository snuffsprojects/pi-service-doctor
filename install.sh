#!/bin/sh
set -eu
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_DIR=/opt/pi-service-doctor
CONFIG_DIR=/etc/pi-service-doctor
STATE_DIR=/var/lib/pi-service-doctor
WEB_ROOT=/var/www/html
SERVICE_USER=${SUDO_USER:-}
INSTALL_SYSTEMD=1
INSTALL_WEB=1

if [ -z "$SERVICE_USER" ] && [ "$(id -u)" -ne 0 ]; then
  SERVICE_USER=$(id -un)
elif [ -z "$SERVICE_USER" ] && id pi >/dev/null 2>&1; then
  SERVICE_USER=pi
fi

usage() {
  echo "Usage: sudo ./install.sh [--user USER] [--app-dir PATH] [--config-dir PATH]"
  echo "       [--state-dir PATH] [--web-root PATH] [--no-web] [--no-systemd]"
  echo "Safe to run again for upgrades; an existing config.json is preserved."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --user) SERVICE_USER=$2; shift 2 ;;
    --app-dir) APP_DIR=$2; shift 2 ;;
    --config-dir) CONFIG_DIR=$2; shift 2 ;;
    --state-dir) STATE_DIR=$2; shift 2 ;;
    --web-root) WEB_ROOT=$2; shift 2 ;;
    --no-web) INSTALL_WEB=0; shift ;;
    --no-systemd) INSTALL_SYSTEMD=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$INSTALL_SYSTEMD" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo, or use --no-systemd for a staged test." >&2
  exit 1
fi
[ -n "$SERVICE_USER" ] || { echo "Could not choose an unprivileged account; rerun with --user USER." >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "User does not exist: $SERVICE_USER" >&2; exit 1; }
[ "$(id -u "$SERVICE_USER")" -ne 0 ] || { echo "Refusing to run scheduled checks as root; choose an unprivileged account with --user." >&2; exit 1; }
SERVICE_GROUP=$(id -gn "$SERVICE_USER")

install -d -m 0755 "$APP_DIR" "$CONFIG_DIR"
install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$STATE_DIR"
install -m 0755 "$SOURCE_DIR/doctor.py" "$SOURCE_DIR/configure.py" "$APP_DIR/"
install -m 0644 "$SOURCE_DIR/config.example.json" "$APP_DIR/"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  /usr/bin/python3 "$APP_DIR/configure.py" --output "$CONFIG_DIR/config.json" --non-interactive
  chmod 0644 "$CONFIG_DIR/config.json"
else
  echo "Keeping existing configuration: $CONFIG_DIR/config.json"
fi

if [ "$INSTALL_WEB" -eq 1 ]; then
  WEB_DIR="$WEB_ROOT/pi-service-doctor"
  install -d -m 0755 "$WEB_DIR/fonts"
  install -m 0644 "$SOURCE_DIR/index.html" "$SOURCE_DIR/doctor.css" "$SOURCE_DIR/doctor.js" "$WEB_DIR/"
  install -m 0644 "$SOURCE_DIR/fonts/barlow-regular.woff2" "$SOURCE_DIR/fonts/barlow-bold.woff2" "$WEB_DIR/fonts/"
  ln -sfn "$STATE_DIR/status.json" "$WEB_DIR/status.json"
fi

if [ "$INSTALL_SYSTEMD" -eq 1 ]; then
  sed -e "s|@SERVICE_USER@|$SERVICE_USER|g" \
      -e "s|@SERVICE_GROUP@|$SERVICE_GROUP|g" \
      -e "s|@APP_DIR@|$APP_DIR|g" \
      -e "s|@CONFIG_FILE@|$CONFIG_DIR/config.json|g" \
      -e "s|@STATE_DIR@|$STATE_DIR|g" \
      -e "s|@STATUS_FILE@|$STATE_DIR/status.json|g" \
      "$SOURCE_DIR/systemd/pi-service-doctor.service.in" > /etc/systemd/system/pi-service-doctor.service
  chmod 0644 /etc/systemd/system/pi-service-doctor.service
  install -m 0644 "$SOURCE_DIR/systemd/pi-service-doctor.timer" /etc/systemd/system/pi-service-doctor.timer
  ln -sfn "$APP_DIR/doctor.py" /usr/local/bin/pi-service-doctor
  systemctl daemon-reload
  systemctl enable --now pi-service-doctor.timer
  systemctl start pi-service-doctor.service
fi

echo
echo "Pi Service Doctor installed."
echo "Configuration: $CONFIG_DIR/config.json"
echo "Report:        $STATE_DIR/status.json"
[ "$INSTALL_WEB" -eq 0 ] || echo "Dashboard:     $WEB_ROOT/pi-service-doctor/index.html"
[ "$INSTALL_SYSTEMD" -eq 0 ] || echo "Run checks:    pi-service-doctor"
