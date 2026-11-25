"""Write audit findings to CSV and a self-contained HTML report."""

import csv
from collections import Counter
from dataclasses import asdict, fields
from html import escape

from .checks import CRITICAL, INFO, SEVERITY_ORDER, WARNING, Finding


def sort_findings(findings):
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.check, f.hostname))


def write_csv(findings, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[fld.name for fld in fields(Finding)])
        writer.writeheader()
        for finding in sort_findings(findings):
            writer.writerow(asdict(finding))


def write_html(findings, device_count, today, path):
    by_severity = Counter(f.severity for f in findings)
    by_check = Counter((f.check, f.severity) for f in findings)
    devices_with_critical = len({f.hostname for f in findings if f.severity == CRITICAL})
    clean = device_count - len({f.hostname for f in findings if f.severity in (CRITICAL, WARNING)})

    check_rows = "".join(
        f"<tr><td>{escape(check)}</td><td><span class='sev {sev.lower()}'>{sev}</span></td><td>{n}</td></tr>"
        for (check, sev), n in sorted(by_check.items(), key=lambda kv: (SEVERITY_ORDER[kv[0][1]], -kv[1]))
    )
    finding_rows = "".join(
        f"<tr><td><span class='sev {f.severity.lower()}'>{f.severity}</span></td>"
        f"<td class='nowrap'>{escape(f.hostname)}</td><td>{escape(f.assigned_user)}</td><td>{escape(f.check)}</td>"
        f"<td>{escape(f.detail)}</td><td>{escape(f.action)}</td></tr>"
        for f in sort_findings(findings)
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Endpoint Audit Report - {today}</title>
<style>
  body {{ font-family: Segoe UI, Helvetica, Arial, sans-serif; margin: 2rem; color: #1f2933; }}
  h1 {{ margin-bottom: 0; }} .sub {{ color: #616e7c; margin-top: .25rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
  .card {{ border: 1px solid #e4e7eb; border-radius: 8px; padding: 1rem 1.25rem; }}
  .card .n {{ font-size: 2rem; font-weight: 600; }} .card .l {{ color: #616e7c; font-size: .9rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; font-size: .9rem; }}
  th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #e4e7eb; vertical-align: top; }}
  th {{ background: #f5f7fa; }}
  td.nowrap {{ white-space: nowrap; }}
  .sev {{ padding: .1rem .5rem; border-radius: 4px; font-size: .8rem; font-weight: 600; }}
  .critical {{ background: #fde8e8; color: #9b1c1c; }} .warning {{ background: #fdf6e3; color: #8a5a00; }}
  .info {{ background: #e8f0fe; color: #1a4fa0; }}
</style></head><body>
<h1>Endpoint Audit Report</h1>
<p class="sub">Generated {today} &middot; {device_count} devices audited</p>
<div class="cards">
  <div class="card"><div class="n">{device_count}</div><div class="l">Devices</div></div>
  <div class="card"><div class="n">{clean}</div><div class="l">No critical/warning issues</div></div>
  <div class="card"><div class="n">{devices_with_critical}</div><div class="l">Devices with critical issues</div></div>
  <div class="card"><div class="n">{by_severity[CRITICAL]}</div><div class="l">Critical findings</div></div>
  <div class="card"><div class="n">{by_severity[WARNING]}</div><div class="l">Warnings</div></div>
  <div class="card"><div class="n">{by_severity[INFO]}</div><div class="l">Info</div></div>
</div>
<h2>Findings by check</h2>
<table><tr><th>Check</th><th>Severity</th><th>Count</th></tr>{check_rows}</table>
<h2>All findings</h2>
<table><tr><th>Severity</th><th>Device</th><th>User</th><th>Check</th><th>Detail</th><th>Recommended action</th></tr>
{finding_rows}</table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
