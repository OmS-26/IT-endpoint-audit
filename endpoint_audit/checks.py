"""
Audit checks. Each check takes one device (a dict from the inventory CSV), the config, and
today's date, and returns a list of Finding objects (empty if the device passes).
"""

from dataclasses import dataclass
from datetime import date, timedelta

CRITICAL, WARNING, INFO = "Critical", "Warning", "Info"
SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}


@dataclass
class Finding:
    hostname: str
    assigned_user: str
    severity: str
    check: str
    detail: str
    action: str


def _finding(device, severity, check, detail, action):
    return Finding(device["hostname"], device.get("assigned_user") or "", severity, check, detail, action)


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def edition_group(edition):
    edition = (edition or "").lower()
    return "Enterprise/Education" if ("enterprise" in edition or "education" in edition) else "Home/Pro"


def check_os_support(device, config, today):
    os_name = device.get("os_name", "")
    version = device.get("os_version", "")
    warn_days = config["thresholds"]["os_eos_warning_days"]

    if os_name.startswith("macOS"):
        try:
            major = int(version.split(".")[0])
        except ValueError:
            return [_finding(device, WARNING, "OS support", f"Unrecognized macOS version '{version}'",
                             "Verify OS version manually")]
        minimum = config["macos_min_supported_major"]
        if major < minimum:
            return [_finding(device, CRITICAL, "OS support",
                             f"macOS {version} no longer receives security updates (minimum {minimum})",
                             "Upgrade macOS or replace hardware if it can't upgrade")]
        return []

    lifecycle = config["os_end_of_servicing"].get(os_name)
    if lifecycle is None:
        return [_finding(device, INFO, "OS support", f"No lifecycle data for '{os_name}'",
                         "Add this OS to config.json")]
    dates = lifecycle.get(version)
    if dates is None:
        return [_finding(device, WARNING, "OS support", f"{os_name} {version} not in lifecycle table",
                         "Verify version; add it to config.json if valid")]

    group = edition_group(device.get("os_edition"))
    eos = _parse_date(dates[group])
    if eos < today:
        return [_finding(device, CRITICAL, "OS support",
                         f"{os_name} {version} ({group}) end of servicing was {eos}",
                         "Upgrade to a supported Windows 11 version")]
    if eos - today <= timedelta(days=warn_days):
        return [_finding(device, WARNING, "OS support",
                         f"{os_name} {version} ({group}) end of servicing on {eos} "
                         f"({(eos - today).days} days)",
                         "Schedule feature update")]
    return []


def check_disk_space(device, config, today):
    total = float(device["disk_total_gb"])
    free = float(device["disk_free_gb"])
    if total <= 0:
        return [_finding(device, WARNING, "Disk space", "Disk size reported as 0", "Re-run inventory collection")]
    pct = 100 * free / total
    t = config["thresholds"]
    if pct < t["disk_free_pct_critical"]:
        return [_finding(device, CRITICAL, "Disk space", f"{free:.0f} GB free of {total:.0f} GB ({pct:.0f}%)",
                         "Clear temp files / user data or replace drive; updates may fail")]
    if pct < t["disk_free_pct_warning"]:
        return [_finding(device, WARNING, "Disk space", f"{free:.0f} GB free of {total:.0f} GB ({pct:.0f}%)",
                         "Run disk cleanup")]
    return []


def check_ram(device, config, today):
    ram = float(device["ram_gb"])
    minimum = config["thresholds"]["min_ram_gb"]
    if ram < minimum:
        return [_finding(device, INFO, "Memory", f"{ram:.0f} GB RAM (standard is {minimum} GB+)",
                         "Consider for upgrade or next hardware refresh")]
    return []


def check_last_seen(device, config, today):
    last_seen = _parse_date(device.get("last_seen"))
    days = config["thresholds"]["stale_after_days"]
    if last_seen is None:
        return [_finding(device, WARNING, "Check-in", "Device has never checked in",
                         "Confirm device exists and inventory agent is installed")]
    age = (today - last_seen).days
    if age > days:
        return [_finding(device, WARNING, "Check-in", f"Last seen {age} days ago ({last_seen})",
                         "Contact assigned user; device may be lost, unused or missing updates")]
    return []


def check_warranty(device, config, today):
    end = _parse_date(device.get("warranty_end"))
    if end is None:
        return [_finding(device, INFO, "Warranty", "No warranty date recorded", "Look up warranty by serial")]
    if end < today:
        return [_finding(device, WARNING, "Warranty", f"Warranty expired {end}",
                         "Add to hardware refresh list")]
    if (end - today).days <= config["thresholds"]["warranty_warning_days"]:
        return [_finding(device, INFO, "Warranty", f"Warranty expires {end} ({(end - today).days} days)",
                         "Plan replacement or extend warranty")]
    return []


def check_assignment(device, config, today):
    if not (device.get("assigned_user") or "").strip():
        return [_finding(device, INFO, "Assignment", "No user assigned", "Assign device or move to spare pool")]
    return []


ALL_CHECKS = [check_os_support, check_disk_space, check_ram, check_last_seen, check_warranty,
              check_assignment]


def audit_device(device, config, today):
    findings = []
    for check in ALL_CHECKS:
        try:
            findings.extend(check(device, config, today))
        except (KeyError, ValueError) as e:
            findings.append(_finding(device, WARNING, "Data quality",
                                     f"{check.__name__} couldn't run: bad or missing field ({e})",
                                     "Fix the inventory record"))
    return findings
