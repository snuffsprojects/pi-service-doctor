#!/bin/sh
set -eu
APP_DIR=/opt/pi-service-doctor
CONFIG_DIR=/etc/pi-service-doctor
STATE_DIR=/var/lib/pi-service-doctor
WEB_ROOT=/var/www/html
PURGE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --app-dir) APP_DIR=$2; shift 2 ;;
    --config-dir) CONFIG_DIR=$2; shift 2 ;;
    --state-dir) STATE_DIR=$2; shift 2 ;;
    --web-root) WEB_ROOT=$2; shift 2 ;;
    --purge) PURGE=1; shift ;;
    -h|--help) echo "Usage: sudo ./uninstall.sh [--purge]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "Run the uninstaller with sudo." >&2; exit 1; }
safe_remove_path() {
  case "$1" in
    ""|/|/etc|/var|/var/www|/opt|/usr|/usr/local) echo "Refusing unsafe removal path: $1" >&2; exit 1 ;;
  esac
}
safe_remove_path "$APP_DIR"
safe_remove_path "$WEB_ROOT/pi-service-doctor"
safe_remove_path "$CONFIG_DIR"
safe_remove_path "$STATE_DIR"
systemctl disable --now pi-service-doctor.timer 2>/dev/null || true
rm -f /etc/systemd/system/pi-service-doctor.service /etc/systemd/system/pi-service-doctor.timer /usr/local/bin/pi-service-doctor
systemctl daemon-reload
rm -rf -- "$APP_DIR" "$WEB_ROOT/pi-service-doctor"
if [ "$PURGE" -eq 1 ]; then
  rm -rf -- "$CONFIG_DIR" "$STATE_DIR"
  echo "Removed, including configuration and reports."
else
  echo "Removed; configuration and reports preserved. Use --purge to remove them."
fi
