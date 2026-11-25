"""
Collect inventory details from THIS machine and add/update its row in an inventory CSV.

Run it on each device (manually, from a login script, or as a scheduled task) pointing at a
shared CSV, then run audit.py on the result.

Usage:
  python3 collect.py --inventory inventory.csv [--department Finance] [--warranty-end 2027-03-31]
  python3 collect.py --print        # just show what would be collected

Works on Windows, macOS and Linux. Requires psutil (pip install -r requirements.txt).
"""

import argparse
import csv
import getpass
import platform
import shutil
import socket
import subprocess
from datetime import date
from pathlib import Path

import psutil

COLUMNS = ["hostname", "assigned_user", "department", "model", "os_name", "os_version", "os_edition",
           "ram_gb", "disk_total_gb", "disk_free_gb", "last_seen", "warranty_end"]


def windows_details():
    """platform.release() can report Windows 11 as '10', so use the build number and registry."""
    import winreg

    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")

    def reg(name, default=""):
        try:
            return str(winreg.QueryValueEx(key, name)[0])
        except OSError:
            return default

    build = int(reg("CurrentBuildNumber", "0"))
    os_name = "Windows 11" if build >= 22000 else "Windows 10"
    version = reg("DisplayVersion") or reg("ReleaseId")      # e.g. 24H2
    edition = reg("EditionID")                                 # e.g. Enterprise, Professional

    try:
        bios = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
        model = winreg.QueryValueEx(bios, "SystemProductName")[0]
    except OSError:
        model = ""
    return os_name, version, edition, model


def macos_details():
    try:
        model = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True).stdout.strip()
    except OSError:
        model = ""
    return "macOS", platform.mac_ver()[0], "", model


def linux_details():
    info = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k] = v.strip('"')
    except OSError:
        pass
    try:
        model = Path("/sys/class/dmi/id/product_name").read_text().strip()
    except OSError:
        model = ""
    return info.get("NAME", "Linux"), info.get("VERSION_ID", platform.release()), "", model


def collect(department="", warranty_end=""):
    system = platform.system()
    if system == "Windows":
        os_name, version, edition, model = windows_details()
        root = Path.home().anchor or "C:\\"
    elif system == "Darwin":
        os_name, version, edition, model = macos_details()
        root = "/"
    else:
        os_name, version, edition, model = linux_details()
        root = "/"

    disk = shutil.disk_usage(root)
    gb = 1024 ** 3
    return {
        "hostname": socket.gethostname(),
        "assigned_user": getpass.getuser(),
        "department": department,
        "model": model,
        "os_name": os_name,
        "os_version": version,
        "os_edition": edition,
        "ram_gb": round(psutil.virtual_memory().total / gb),
        "disk_total_gb": round(disk.total / gb),
        "disk_free_gb": round(disk.free / gb),
        "last_seen": date.today().isoformat(),
        "warranty_end": warranty_end,
    }


def upsert(inventory_path, record):
    """Replace this host's row if it exists, otherwise append it. Keeps existing warranty/department."""
    path = Path(inventory_path)
    rows = []
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

    for row in rows:
        if row["hostname"].lower() == record["hostname"].lower():
            for keep in ("department", "warranty_end"):
                if not record[keep]:
                    record[keep] = row.get(keep, "")
            row.update(record)
            action = "Updated"
            break
    else:
        rows.append(record)
        action = "Added"

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return action


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inventory", default="inventory.csv")
    parser.add_argument("--department", default="")
    parser.add_argument("--warranty-end", default="", help="YYYY-MM-DD, if known")
    parser.add_argument("--print", action="store_true", help="Print details without writing")
    args = parser.parse_args()

    record = collect(args.department, args.warranty_end)
    if args.print:
        for k in COLUMNS:
            print(f"{k:>14}: {record[k]}")
        return
    action = upsert(args.inventory, record)
    print(f"{action} {record['hostname']} in {args.inventory}")


if __name__ == "__main__":
    main()
