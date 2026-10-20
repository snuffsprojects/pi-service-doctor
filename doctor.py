#!/usr/bin/env python3
"""Read-only Raspberry Pi health checks with CLI and JSON output."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
VERSION = "1.0.0"
SYSTEM_CONFIG = Path("/etc/pi-service-doctor/config.json")
SYSTEM_OUTPUT = Path("/var/lib/pi-service-doctor/status.json")
DEFAULT_CONFIG = Path(os.environ.get("PI_SERVICE_DOCTOR_CONFIG", SYSTEM_CONFIG if SYSTEM_CONFIG.exists() else ROOT / "config.json"))
DEFAULT_OUTPUT = Path(os.environ.get("PI_SERVICE_DOCTOR_OUTPUT", SYSTEM_OUTPUT if SYSTEM_OUTPUT.parent.exists() else ROOT / "status.json"))
LEVELS = {"healthy": 0, "warning": 1, "critical": 2, "unknown": 1}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(command: list[str], timeout: float = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return result.returncode, (result.stdout or result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, type(exc).__name__


def bytes_label(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TiB"


def duration_label(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def threshold_status(value: float, warning: float, critical: float) -> str:
    return "critical" if value >= critical else "warning" if value >= warning else "healthy"


def check_item(kind: str, label: str, status: str, detail: str, **extra) -> dict:
    return {"kind": kind, "label": label, "status": status, "detail": detail, **extra}


def read_memory() -> dict:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, raw = line.split(":", 1)
            values[name] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return {"total": 0, "available": 0, "used": 0, "percent": 0}
    total, available = values.get("MemTotal", 0), values.get("MemAvailable", 0)
    used = max(0, total - available)
    return {"total": total, "available": available, "used": used, "percent": round(used / total * 100, 1) if total else 0}


def read_temperature() -> float | None:
    for path in (Path("/sys/class/thermal/thermal_zone0/temp"), Path("/sys/devices/virtual/thermal/thermal_zone0/temp")):
        try:
            return round(float(path.read_text().strip()) / 1000, 1)
        except (OSError, ValueError):
            pass
    code, output = run(["vcgencmd", "measure_temp"])
    if code == 0 and "=" in output:
        try:
            return round(float(output.split("=", 1)[1].split("'", 1)[0]), 1)
        except ValueError:
            pass
    return None


def read_throttling() -> dict:
    code, output = run(["vcgencmd", "get_throttled"])
    if code or "0x" not in output:
        return {"available": False, "value": None, "status": "unknown"}
    try:
        value = int(output.rsplit("0x", 1)[1], 16)
    except ValueError:
        return {"available": False, "value": None, "status": "unknown"}
    return {"available": True, "value": f"0x{value:x}", "status": "healthy" if value == 0 else "warning"}


def system_metrics(config: dict) -> tuple[dict, list[dict]]:
    thresholds = config.get("thresholds", {})
    path = config.get("diskPath", "/")
    disk = shutil.disk_usage(path)
    disk_percent = round(disk.used / disk.total * 100, 1)
    memory = read_memory()
    temperature = read_temperature()
    throttling = read_throttling()
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        uptime = 0
    load = os.getloadavg()
    metrics = {
        "hostname": socket.gethostname(), "uptimeSeconds": int(uptime), "uptime": duration_label(uptime),
        "load": [round(value, 2) for value in load],
        "disk": {"path": path, "total": disk.total, "used": disk.used, "free": disk.free, "percent": disk_percent,
                 "totalLabel": bytes_label(disk.total), "usedLabel": bytes_label(disk.used), "freeLabel": bytes_label(disk.free)},
        "memory": {**memory, "totalLabel": bytes_label(memory["total"]), "usedLabel": bytes_label(memory["used"]), "availableLabel": bytes_label(memory["available"])},
        "temperatureC": temperature, "throttling": throttling,
    }
    checks = [
        check_item("system", "Storage", threshold_status(disk_percent, thresholds.get("diskWarningPercent", 80), thresholds.get("diskCriticalPercent", 92)), f"{disk_percent}% used · {bytes_label(disk.free)} free", value=disk_percent, unit="%"),
        check_item("system", "Memory", threshold_status(memory["percent"], thresholds.get("memoryWarningPercent", 85), thresholds.get("memoryCriticalPercent", 95)), f'{memory["percent"]}% used · {bytes_label(memory["available"])} available', value=memory["percent"], unit="%"),
    ]
    if temperature is None:
        checks.append(check_item("system", "CPU temperature", "unknown", "Temperature unavailable"))
    else:
        checks.append(check_item("system", "CPU temperature", threshold_status(temperature, thresholds.get("temperatureWarningC", 72), thresholds.get("temperatureCriticalC", 80)), f"{temperature:.1f}°C", value=temperature, unit="°C"))
    checks.append(check_item("system", "Power and throttling", throttling["status"], "No throttling detected" if throttling.get("value") == "0x0" else f'Throttle flags: {throttling.get("value") or "unavailable"}'))
    return metrics, checks


def service_checks(config: dict) -> list[dict]:
    checks = []
    for item in config.get("services", []):
        code, output = run(["systemctl", "is-active", item["name"]])
        active = code == 0 and output == "active"
        status = "healthy" if active else "critical" if item.get("required", True) else "warning"
        checks.append(check_item("service", item.get("label", item["name"]), status, output or "unknown", target=item["name"]))
    for item in config.get("timers", []):
        code, output = run(["systemctl", "is-active", item["name"]])
        active = code == 0 and output == "active"
        status = "healthy" if active else "critical" if item.get("required", True) else "warning"
        checks.append(check_item("timer", item.get("label", item["name"]), status, "Scheduled and waiting" if active else output or "inactive", target=item["name"]))
    return checks


def failed_unit_check(config: dict) -> dict:
    code, output = run(["systemctl", "--no-legend", "--plain", "--failed"])
    if code not in (0, 1):
        return check_item("system", "Failed units", "unknown", "Could not query systemd")
    ignored = config.get("ignoreFailedUnits", [])
    units = []
    for line in output.splitlines():
        unit = line.split()[0] if line.split() else ""
        if unit and not any(fnmatch.fnmatch(unit, pattern) for pattern in ignored):
            units.append(unit)
    return check_item("system", "Failed units", "healthy" if not units else "critical", "None" if not units else ", ".join(units), count=len(units), units=units)


def port_checks(config: dict) -> list[dict]:
    checks = []
    for item in config.get("ports", []):
        started = time.monotonic()
        try:
            with socket.create_connection((item.get("host", "127.0.0.1"), int(item["port"])), timeout=float(item.get("timeout", 2))):
                pass
            latency = round((time.monotonic() - started) * 1000)
            checks.append(check_item("port", item.get("label", str(item["port"])), "healthy", f"TCP {item['port']} · {latency} ms", latencyMs=latency, port=item["port"]))
        except OSError as exc:
            status = "critical" if item.get("required", True) else "warning"
            checks.append(check_item("port", item.get("label", str(item["port"])), status, f"TCP {item['port']} · {type(exc).__name__}", latencyMs=None, port=item["port"]))
    return checks


def url_checks(config: dict) -> list[dict]:
    checks = []
    for item in config.get("urls", []):
        started, status_code, error = time.monotonic(), None, None
        try:
            request = Request(item["url"], headers={"User-Agent": "PiServiceDoctor/1.0"})
            with urlopen(request, timeout=float(item.get("timeout", 5))) as response:
                status_code = response.status
                response.read(1)
        except HTTPError as exc:
            status_code, error = exc.code, f"HTTP {exc.code}"
        except (URLError, TimeoutError, OSError) as exc:
            error = type(exc).__name__
        latency = round((time.monotonic() - started) * 1000)
        expected = item.get("expected", [200])
        healthy = status_code in expected
        status = "healthy" if healthy else "critical" if item.get("required", True) else "warning"
        detail = f"HTTP {status_code} · {latency} ms" if status_code is not None else f"{error or 'unavailable'} · {latency} ms"
        checks.append(check_item("url", item.get("label", item["url"]), status, detail, latencyMs=latency, statusCode=status_code, target=item["url"]))
    return checks


def file_checks(config: dict, now: float) -> list[dict]:
    checks = []
    default_age = config.get("thresholds", {}).get("fileWarningHours", 24)
    for item in config.get("files", []):
        path = Path(item["path"])
        try:
            stat = path.stat()
            age_hours = (now - stat.st_mtime) / 3600
            stale = age_hours > item.get("maxAgeHours", default_age)
            status = "warning" if stale else "healthy"
            if stale and item.get("required", True):
                status = "critical"
            detail = f"{duration_label(age_hours * 3600)} old · {bytes_label(stat.st_size)}"
            checks.append(check_item("file", item.get("label", path.name), status, detail, ageHours=round(age_hours, 1), target=str(path)))
        except OSError:
            status = "critical" if item.get("required", True) else "warning"
            checks.append(check_item("file", item.get("label", path.name), status, "File not found", ageHours=None, target=str(path)))
    return checks


def build_report(config: dict) -> dict:
    started = time.monotonic()
    metrics, checks = system_metrics(config)
    checks.extend(service_checks(config))
    checks.append(failed_unit_check(config))
    checks.extend(port_checks(config))
    checks.extend(url_checks(config))
    checks.extend(file_checks(config, time.time()))
    overall = max((item["status"] for item in checks), key=lambda value: LEVELS.get(value, 1), default="unknown")
    counts = {level: sum(item["status"] == level for item in checks) for level in LEVELS}
    return {"schemaVersion": 1, "name": config.get("name") or metrics["hostname"], "generatedAt": utc_now(),
            "durationMs": round((time.monotonic() - started) * 1000), "overall": overall, "counts": counts,
            "metrics": metrics, "checks": checks}


def atomic_write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(report, target, indent=2)
            target.write("\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def print_report(report: dict) -> None:
    icon = {"healthy": "OK", "warning": "!!", "critical": "XX", "unknown": "??"}
    print(f'{report["name"]} · {report["overall"].upper()} · {report["generatedAt"]}')
    print(f'Uptime {report["metrics"]["uptime"]} · load {report["metrics"]["load"][0]} · checked in {report["durationMs"]} ms')
    for item in report["checks"]:
        print(f'{icon.get(item["status"], "??")}  {item["label"]:<26} {item["detail"]}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"Pi Service Doctor {VERSION}")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, help="Write the complete report atomically as JSON")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the human report")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--always-zero", action="store_true", help="Do not fail a scheduler when checks need attention")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read configuration: {exc}", file=sys.stderr)
        return 2
    report = build_report(config)
    if args.output:
        atomic_write(args.output, report)
    if not args.quiet:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
    return 0 if args.always_zero else LEVELS.get(report["overall"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
