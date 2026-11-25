"""
Audit a device inventory CSV and write a findings CSV plus an HTML report.

Usage:
  python3 audit.py sample_data/inventory.csv
  python3 audit.py inventory.csv --out reports --today 2026-11-25 --fail-on critical

Exit codes: 0 = ok, 1 = findings at or above --fail-on severity (useful in a scheduled task),
2 = input error.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from endpoint_audit.checks import CRITICAL, SEVERITY_ORDER, WARNING, audit_device
from endpoint_audit.report import write_csv, write_html

REQUIRED_COLUMNS = {"hostname", "assigned_user", "os_name", "os_version", "os_edition", "ram_gb",
                    "disk_total_gb", "disk_free_gb", "last_seen", "warranty_end"}


def load_inventory(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Inventory is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inventory", help="Path to inventory CSV")
    parser.add_argument("--config", default=Path(__file__).parent / "config" / "config.json")
    parser.add_argument("--out", default="reports", help="Output folder (default: reports)")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(),
                        help="Audit date as YYYY-MM-DD (default: today)")
    parser.add_argument("--fail-on", choices=["critical", "warning", "never"], default="never",
                        help="Exit with code 1 if any finding is at or above this severity")
    args = parser.parse_args()

    try:
        devices = load_inventory(args.inventory)
        with open(args.config) as f:
            config = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    findings = [finding for device in devices for finding in audit_device(device, config, args.today)]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = args.today.isoformat()
    csv_path = out / f"findings_{stamp}.csv"
    html_path = out / f"audit_report_{stamp}.html"
    write_csv(findings, csv_path)
    write_html(findings, len(devices), args.today, html_path)

    counts = Counter(f.severity for f in findings)
    print(f"Audited {len(devices)} devices on {stamp}")
    for severity in sorted(counts, key=SEVERITY_ORDER.get):
        print(f"  {severity:<9}{counts[severity]}")
    print(f"Wrote {csv_path} and {html_path}")

    threshold = {"critical": [CRITICAL], "warning": [CRITICAL, WARNING], "never": []}[args.fail_on]
    return 1 if any(f.severity in threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
