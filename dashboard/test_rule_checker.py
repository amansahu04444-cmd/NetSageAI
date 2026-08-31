"""
Unit Tests for NetSage AI Deterministic Rule Checker

Verifies all six deterministic network rules with positive, negative, and insufficient evidence cases.
No AI APIs or external network calls are used.
"""

import unittest
from checker.rule_checker import (
    check_duplicate_ips,
    check_subnet_masks,
    check_gateway_mismatch,
    check_interface_status,
    check_missing_vlans,
    check_missing_routes,
    run_all_checks,
)


class TestRuleChecker(unittest.TestCase):

    # -------------------------------------------------------------------------
    # 1. Duplicate IP Tests
    # -------------------------------------------------------------------------
    def test_duplicate_ip_positive_structured(self):
        """Positive test: duplicate IP detected in structured host assignments."""
        evidence = {
            "ip_assignments": {
                "PC1": "192.168.1.10",
                "PC2": "192.168.1.10",
                "PC3": "192.168.1.15",
            }
        }
        res = check_duplicate_ips(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.rule, "duplicate_ip")
        self.assertIn("192.168.1.10", res.evidence)

    def test_duplicate_ip_positive_log(self):
        """Positive test: duplicate IP detected from syslog log string."""
        evidence = "Log: %IP-4-DUP_ADDR: Duplicate address 192.168.1.100 on FastEthernet0/1"
        res = check_duplicate_ips(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("192.168.1.100", res.evidence)

    def test_duplicate_ip_negative(self):
        """Negative test: all hosts have unique IP addresses."""
        evidence = {
            "ip_assignments": {
                "PC1": "192.168.1.10",
                "PC2": "192.168.1.11",
                "PC3": "192.168.1.12",
            }
        }
        res = check_duplicate_ips(evidence)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.severity, "NONE")

    # -------------------------------------------------------------------------
    # 2. Subnet Mask Tests
    # -------------------------------------------------------------------------
    def test_subnet_mask_positive_mismatch(self):
        """Positive test: configured mask does not match expected mask."""
        evidence = {
            "host_ip": "10.0.0.5",
            "subnet_mask": "255.255.255.0",
            "expected_mask": "255.255.255.240",
        }
        res = check_subnet_masks(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("255.255.255.0", res.evidence)

    def test_subnet_mask_positive_boundary_violation(self):
        """Positive test: subnet mask boundary violation in text."""
        evidence = "IP 10.1.1.50 mask 255.255.255.240; outside subnet boundary"
        res = check_subnet_masks(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.rule, "subnet_mask")

    def test_subnet_mask_negative(self):
        """Negative test: valid host IP and matching subnet mask."""
        evidence = {
            "host_ip": "192.168.1.50",
            "subnet_mask": "255.255.255.0",
            "expected_mask": "255.255.255.0",
        }
        res = check_subnet_masks(evidence)
        self.assertEqual(res.status, "PASS")

    # -------------------------------------------------------------------------
    # 3. Gateway Mismatch Tests
    # -------------------------------------------------------------------------
    def test_gateway_mismatch_positive_outside_subnet(self):
        """Positive test: gateway IP falls outside the host subnet block."""
        evidence = {
            "host_ip": "192.168.10.20",
            "subnet_mask": "255.255.255.0",  # Subnet: 192.168.10.0/24
            "gateway_ip": "192.168.20.1",     # Outside subnet
        }
        res = check_gateway_mismatch(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("outside the host subnet", res.message)

    def test_gateway_mismatch_positive_sub_28(self):
        """Positive test: gateway outside /28 subnet boundary."""
        evidence = {
            "host_ip": "10.1.1.50",
            "subnet_mask": "255.255.255.240",  # Subnet: 10.1.1.48/28
            "gateway_ip": "10.1.1.30",          # Outside subnet
        }
        res = check_gateway_mismatch(evidence)
        self.assertEqual(res.status, "ERROR")

    def test_gateway_mismatch_negative(self):
        """Negative test: gateway IP is inside host subnet."""
        evidence = {
            "host_ip": "192.168.1.50",
            "subnet_mask": "255.255.255.0",
            "gateway_ip": "192.168.1.1",
        }
        res = check_gateway_mismatch(evidence)
        self.assertEqual(res.status, "PASS")

    # -------------------------------------------------------------------------
    # 4. Interface Status Tests
    # -------------------------------------------------------------------------
    def test_interface_down_positive_admin_down(self):
        """Positive test: interface is administratively down in show output."""
        evidence = "GigabitEthernet0/0.10 is administratively down line protocol is down"
        res = check_interface_status(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.rule, "interface_status")
        self.assertIn("GigabitEthernet0/0.10", res.evidence)

    def test_interface_down_positive_shutdown(self):
        """Positive test: interface is in shutdown state."""
        evidence = "interface Vlan1; ip address 192.168.1.2 255.255.255.0; shutdown"
        res = check_interface_status(evidence)
        self.assertEqual(res.status, "ERROR")

    def test_interface_up_negative(self):
        """Negative test: interface is up in operational state."""
        evidence = {
            "interfaces": [
                {"name": "GigabitEthernet0/1", "status": "up/up"}
            ]
        }
        res = check_interface_status(evidence)
        self.assertEqual(res.status, "PASS")

    # -------------------------------------------------------------------------
    # 5. Missing VLAN Tests
    # -------------------------------------------------------------------------
    def test_missing_vlan_positive(self):
        """Positive test: required VLAN is missing from allowed list."""
        evidence = {
            "required_vlan": 20,
            "configured_vlans": [10, 30, 40],
        }
        res = check_missing_vlans(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.rule, "missing_vlan")
        self.assertIn("20", res.evidence)

    def test_vlan_present_negative(self):
        """Negative test: required VLAN is present in configured list."""
        evidence = {
            "required_vlan": 20,
            "configured_vlans": [10, 20, 30, 40],
        }
        res = check_missing_vlans(evidence)
        self.assertEqual(res.status, "PASS")

    # -------------------------------------------------------------------------
    # 6. Missing Route Tests
    # -------------------------------------------------------------------------
    def test_missing_route_positive_table(self):
        """Positive test: required destination route missing from routing table."""
        evidence = {
            "destination": "192.168.30.0/24",
            "routing_table": ["10.0.0.0/8", "172.16.0.0/16"],
        }
        res = check_missing_routes(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.rule, "missing_route")
        self.assertIn("192.168.30.0/24", res.evidence)

    def test_missing_route_positive_unreachable_nexthop(self):
        """Positive test: static route next-hop IP is unreachable."""
        evidence = "ip route 172.16.0.0 255.255.0.0 10.0.0.5 (Next-hop IP 10.0.0.5 unreachable)"
        res = check_missing_routes(evidence)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("10.0.0.5", res.evidence)

    def test_route_present_negative(self):
        """Negative test: destination route present in routing table."""
        evidence = {
            "destination": "192.168.30.0/24",
            "routing_table": ["192.168.30.0/24", "10.0.0.0/8"],
        }
        res = check_missing_routes(evidence)
        self.assertEqual(res.status, "PASS")

    # -------------------------------------------------------------------------
    # 7. Insufficient Evidence Test
    # -------------------------------------------------------------------------
    def test_insufficient_evidence(self):
        """Test returning NOT_CHECKED when required evidence is missing."""
        evidence = "DNS server unreachable on port 53"
        results = run_all_checks(evidence)
        # For unrelated evidence like DNS port timeout, IP/VLAN/Routing rules should return NOT_CHECKED
        duplicate_res = next(r for r in results if r.rule == "duplicate_ip")
        gateway_res = next(r for r in results if r.rule == "gateway_mismatch")

        self.assertEqual(duplicate_res.status, "NOT_CHECKED")
        self.assertEqual(gateway_res.status, "NOT_CHECKED")
        self.assertIn("Insufficient evidence", duplicate_res.message)


if __name__ == "__main__":
    unittest.main()
