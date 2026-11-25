import json
import unittest
from datetime import date
from pathlib import Path

from endpoint_audit.checks import (CRITICAL, INFO, WARNING, audit_device, check_assignment, check_disk_space,
                                   check_last_seen, check_os_support, check_ram, check_warranty, edition_group)

CONFIG = json.loads((Path(__file__).parent.parent / "config" / "config.json").read_text())
TODAY = date(2026, 11, 25)


def device(**overrides):
    base = {
        "hostname": "TEST-01", "assigned_user": "test.user", "os_name": "Windows 11", "os_version": "25H2",
        "os_edition": "Enterprise", "ram_gb": "16", "disk_total_gb": "512", "disk_free_gb": "200",
        "last_seen": "2026-11-24", "warranty_end": "2028-01-01",
    }
    base.update(overrides)
    return base


class TestOsSupport(unittest.TestCase):
    def test_supported_version_passes(self):
        self.assertEqual(check_os_support(device(), CONFIG, TODAY), [])

    def test_windows_10_is_critical(self):
        [f] = check_os_support(device(os_name="Windows 10", os_version="22H2"), CONFIG, TODAY)
        self.assertEqual(f.severity, CRITICAL)

    def test_edition_changes_end_date(self):
        # 24H2 Pro ended 2026-10-13; 24H2 Enterprise runs to 2027-10-12
        pro = check_os_support(device(os_version="24H2", os_edition="Professional"), CONFIG, TODAY)
        ent = check_os_support(device(os_version="24H2", os_edition="Enterprise"), CONFIG, TODAY)
        self.assertEqual(pro[0].severity, CRITICAL)
        self.assertEqual(ent, [])

    def test_warning_when_end_date_is_close(self):
        [f] = check_os_support(device(os_version="24H2"), CONFIG, date(2027, 6, 1))
        self.assertEqual(f.severity, WARNING)

    def test_unknown_version_is_flagged(self):
        [f] = check_os_support(device(os_version="19H1"), CONFIG, TODAY)
        self.assertEqual(f.severity, WARNING)

    def test_old_macos_is_critical(self):
        [f] = check_os_support(device(os_name="macOS", os_version="13.7"), CONFIG, TODAY)
        self.assertEqual(f.severity, CRITICAL)
        self.assertEqual(check_os_support(device(os_name="macOS", os_version="15.7"), CONFIG, TODAY), [])

    def test_edition_group(self):
        self.assertEqual(edition_group("EnterpriseS"), "Enterprise/Education")
        self.assertEqual(edition_group("Professional"), "Home/Pro")
        self.assertEqual(edition_group(""), "Home/Pro")


class TestHardwareChecks(unittest.TestCase):
    def test_disk_thresholds(self):
        self.assertEqual(check_disk_space(device(disk_free_gb="20"), CONFIG, TODAY)[0].severity, CRITICAL)  # 4%
        self.assertEqual(check_disk_space(device(disk_free_gb="60"), CONFIG, TODAY)[0].severity, WARNING)   # 12%
        self.assertEqual(check_disk_space(device(disk_free_gb="200"), CONFIG, TODAY), [])

    def test_low_ram_is_info(self):
        self.assertEqual(check_ram(device(ram_gb="4"), CONFIG, TODAY)[0].severity, INFO)
        self.assertEqual(check_ram(device(ram_gb="8"), CONFIG, TODAY), [])


class TestLifecycleChecks(unittest.TestCase):
    def test_stale_device(self):
        self.assertEqual(check_last_seen(device(last_seen="2026-09-01"), CONFIG, TODAY)[0].severity, WARNING)
        self.assertEqual(check_last_seen(device(last_seen=""), CONFIG, TODAY)[0].severity, WARNING)

    def test_warranty(self):
        self.assertEqual(check_warranty(device(warranty_end="2026-01-01"), CONFIG, TODAY)[0].severity, WARNING)
        self.assertEqual(check_warranty(device(warranty_end="2027-01-15"), CONFIG, TODAY)[0].severity, INFO)
        self.assertEqual(check_warranty(device(warranty_end="2028-01-01"), CONFIG, TODAY), [])

    def test_unassigned(self):
        self.assertEqual(check_assignment(device(assigned_user=" "), CONFIG, TODAY)[0].severity, INFO)


class TestAuditDevice(unittest.TestCase):
    def test_healthy_device_has_no_findings(self):
        self.assertEqual(audit_device(device(), CONFIG, TODAY), [])

    def test_bad_data_becomes_a_finding_not_a_crash(self):
        findings = audit_device(device(ram_gb="sixteen"), CONFIG, TODAY)
        self.assertEqual([f.check for f in findings], ["Data quality"])


if __name__ == "__main__":
    unittest.main()
