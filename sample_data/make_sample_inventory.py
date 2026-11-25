"""
Generate a fake 150-device inventory for demos and testing (no real company data).

Usage: python3 sample_data/make_sample_inventory.py [--devices 150] [--seed 7]
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

AUDIT_DATE = date(2026, 11, 25)
DEPARTMENTS = ["Finance", "Investments", "Legal", "HR", "Operations", "Data Science", "IT", "Asset Mgmt"]
FIRST = ["alex", "jordan", "sam", "taylor", "morgan", "casey", "riley", "jamie", "avery", "quinn",
         "drew", "parker", "reese", "rowan", "skyler", "devon", "emerson", "hayden"]
LAST = ["smith", "patel", "nguyen", "brown", "khan", "martin", "lee", "singh", "wilson", "tremblay"]

# (os_name, version, edition, model, weight)
FLEET = [
    ("Windows 11", "25H2", "Enterprise", "HP EliteBook 840 G11", 40),
    ("Windows 11", "24H2", "Enterprise", "HP EliteBook 840 G10", 30),
    ("Windows 11", "23H2", "Enterprise", "HP EliteBook 840 G9", 12),
    ("Windows 11", "24H2", "Professional", "HP ProBook 450 G10", 8),
    ("Windows 10", "22H2", "Enterprise", "HP EliteDesk 800 G6", 6),
    ("macOS", "26.1", "", "MacBookPro18,3", 6),
    ("macOS", "15.7", "", "MacBookAir10,1", 4),
    ("macOS", "13.7", "", "MacBookPro16,1", 2),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--devices", type=int, default=150)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    rows = []
    for i in range(1, args.devices + 1):
        os_name, version, edition, model, _ = rng.choices(FLEET, weights=[f[-1] for f in FLEET])[0]
        prefix = "MAC" if os_name == "macOS" else "WS"
        disk_total = rng.choice([256, 512, 512, 1024])
        used_pct = min(rng.betavariate(5, 3), 0.99)  # most drives 40-80% full, a few nearly full
        if rng.random() < 0.06:  # a few devices that stopped checking in
            last_seen = AUDIT_DATE - timedelta(days=rng.randint(35, 160))
        else:
            last_seen = AUDIT_DATE - timedelta(days=int(rng.expovariate(1 / 4)))
        purchased = AUDIT_DATE - timedelta(days=rng.randint(60, 4 * 365))
        user = "" if rng.random() < 0.04 else f"{rng.choice(FIRST)}.{rng.choice(LAST)}"
        rows.append({
            "hostname": f"TOR-{prefix}-{i:04d}",
            "assigned_user": user,
            "department": rng.choice(DEPARTMENTS),
            "model": model,
            "os_name": os_name,
            "os_version": version,
            "os_edition": edition,
            "ram_gb": rng.choices([8, 16, 32, 4], weights=[25, 55, 15, 5])[0],
            "disk_total_gb": disk_total,
            "disk_free_gb": round(disk_total * (1 - used_pct)),
            "last_seen": last_seen.isoformat(),
            "warranty_end": (purchased + timedelta(days=3 * 365)).isoformat() if rng.random() > 0.03 else "",
        })

    out = Path(__file__).parent / "inventory.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} devices to {out}")


if __name__ == "__main__":
    main()
