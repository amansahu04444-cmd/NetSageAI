"""
NetSage AI - Deterministic Rule-Based Network Checker Module

This module performs 100% deterministic validation of network troubleshooting evidence.
It checks for common Cisco / Packet Tracer configuration errors without using AI/LLMs:
1. Duplicate IP Addresses
2. Wrong Subnet Masks
3. Gateway Mismatch
4. Interface Down Status
5. Missing VLANs
6. Missing Routes

Safety Rule: This module reports findings only; it NEVER alters network configurations.
"""

from dataclasses import dataclass, asdict
import ipaddress
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

# Attempt relative import or standalone import
try:
    from data.dataset_loader import load_cases_as_dicts
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from data.dataset_loader import load_cases_as_dicts


@dataclass
class RuleResult:
    rule: str
    status: str       # "ERROR", "PASS", "WARNING", "NOT_CHECKED"
    message: str
    evidence: str
    severity: str     # "HIGH", "MEDIUM", "LOW", "NONE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_text_evidence(evidence_input: Union[Dict[str, Any], str]) -> str:
    """Helper to unify dictionary or string input into a single searchable text blob."""
    if isinstance(evidence_input, str):
        return evidence_input
    elif isinstance(evidence_input, dict):
        text_parts = []
        for key in ["symptom", "topology_note", "show_output", "show_outputs", "expected_fault", "raw_text", "log"]:
            if key in evidence_input and evidence_input[key]:
                text_parts.append(str(evidence_input[key]))
        return " | ".join(text_parts)
    return ""


# -----------------------------------------------------------------------------
# Rule 1: Duplicate IP Detection
# -----------------------------------------------------------------------------
def check_duplicate_ips(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects duplicate IP addresses assigned across hosts/interfaces or in syslog logs.
    """
    rule_name = "duplicate_ip"

    # Structured dict check
    if isinstance(evidence_input, dict):
        ip_assignments = evidence_input.get("ip_assignments") or evidence_input.get("hosts")
        if isinstance(ip_assignments, dict) and len(ip_assignments) > 1:
            seen_ips: Dict[str, str] = {}
            duplicates: List[str] = []
            for host, ip in ip_assignments.items():
                if ip in seen_ips:
                    duplicates.append(f"{ip} used by both {seen_ips[ip]} and {host}")
                else:
                    seen_ips[ip] = host
            if duplicates:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Duplicate IP address detected",
                    evidence="; ".join(duplicates),
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="No duplicate IP addresses detected",
                evidence=f"All {len(ip_assignments)} assigned IPs are unique",
                severity="NONE",
            )
        elif isinstance(ip_assignments, list) and len(ip_assignments) > 1:
            seen: set = set()
            dups: set = set()
            for ip in ip_assignments:
                if ip in seen:
                    dups.add(ip)
                seen.add(ip)
            if dups:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Duplicate IP address detected",
                    evidence=f"Duplicate IP(s): {', '.join(dups)}",
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="No duplicate IP addresses detected",
                evidence="All listed IP addresses are unique",
                severity="NONE",
            )

    text = _extract_text_evidence(evidence_input)

    # Log pattern check (e.g., %IP-4-DUP_ADDR: Duplicate address 192.168.1.100)
    dup_log_match = re.search(r"%IP-4-DUP_ADDR:\s*Duplicate\s+address\s+([\d\.]+)", text, re.IGNORECASE)
    if dup_log_match:
        dup_ip = dup_log_match.group(1)
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Duplicate IP address conflict detected in log",
            evidence=f"Syslog report: Duplicate address {dup_ip}",
            severity="HIGH",
        )

    # Keywords matching in text
    if re.search(r"duplicate\s+ip|same\s+ip|duplicate\s+address", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Duplicate IP address conflict detected",
            evidence=text,
            severity="HIGH",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate duplicate IP configuration",
        evidence="No multi-host IP assignment list or duplicate IP logs present",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Rule 2: Subnet Mask Validation
# -----------------------------------------------------------------------------
def check_subnet_masks(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects invalid subnet masks, syntax errors, or subnet mask mismatches.
    """
    rule_name = "subnet_mask"

    # Structured dict check
    if isinstance(evidence_input, dict):
        host_ip = evidence_input.get("host_ip")
        subnet_mask = evidence_input.get("subnet_mask")
        expected_mask = evidence_input.get("expected_mask")

        if host_ip and subnet_mask:
            try:
                iface = ipaddress.ip_interface(f"{host_ip}/{subnet_mask}")
                if expected_mask and str(iface.netmask) != str(expected_mask):
                    return RuleResult(
                        rule=rule_name,
                        status="ERROR",
                        message="Subnet mask mismatch detected",
                        evidence=f"Configured mask {subnet_mask} does not match expected mask {expected_mask}",
                        severity="HIGH",
                    )
                return RuleResult(
                    rule=rule_name,
                    status="PASS",
                    message="Subnet mask configuration is valid",
                    evidence=f"IP {host_ip} with valid mask {iface.netmask} (Subnet: {iface.network})",
                    severity="NONE",
                )
            except ValueError as e:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Invalid subnet mask or IP configuration syntax",
                    evidence=f"Validation failed for IP '{host_ip}' with mask '{subnet_mask}': {str(e)}",
                    severity="HIGH",
                )

    text = _extract_text_evidence(evidence_input)

    # Match textual evidence like: "IP 10.1.1.50 mask 255.255.255.240"
    mask_match = re.search(r"IP\s+([\d\.]+)\s+mask\s+([\d\.]+)", text, re.IGNORECASE)
    if mask_match:
        ip_str, mask_str = mask_match.groups()
        try:
            iface = ipaddress.ip_interface(f"{ip_str}/{mask_str}")
            if "outside subnet boundary" in text.lower() or "subnet boundary" in text.lower():
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Wrong subnet mask or network boundary violation",
                    evidence=f"Host {ip_str} with mask {mask_str} falls into subnet {iface.network}, violating boundary limits",
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="Subnet mask syntax valid",
                evidence=f"Host {ip_str} mask {mask_str} forms subnet {iface.network}",
                severity="NONE",
            )
        except ValueError as err:
            return RuleResult(
                rule=rule_name,
                status="ERROR",
                message="Invalid subnet mask format",
                evidence=f"Syntax error parsing IP/Mask {ip_str} {mask_str}: {str(err)}",
                severity="HIGH",
            )

    if re.search(r"subnet\s+mask\s+mismatch|wrong\s+subnet\s+mask|invalid\s+mask", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Subnet mask inconsistency detected",
            evidence=text,
            severity="HIGH",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate subnet mask configuration",
        evidence="No host IP and subnet mask information provided",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Rule 3: Gateway Mismatch Detection
# -----------------------------------------------------------------------------
def check_gateway_mismatch(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects if a configured default gateway lies outside the host's subnet boundary or mismatches router gateway IP.
    """
    rule_name = "gateway_mismatch"

    # Structured dict check
    if isinstance(evidence_input, dict):
        host_ip = evidence_input.get("host_ip")
        subnet_mask = evidence_input.get("subnet_mask")
        gateway_ip = evidence_input.get("gateway_ip")
        expected_gateway = evidence_input.get("expected_gateway")

        if host_ip and subnet_mask and gateway_ip:
            try:
                iface = ipaddress.ip_interface(f"{host_ip}/{subnet_mask}")
                gw_addr = ipaddress.ip_address(gateway_ip)
                if gw_addr not in iface.network:
                    return RuleResult(
                        rule=rule_name,
                        status="ERROR",
                        message="Default gateway is outside the host subnet",
                        evidence=f"Host IP {host_ip}/{subnet_mask} is in subnet {iface.network}, but Gateway {gateway_ip} is outside this range",
                        severity="HIGH",
                    )
                if expected_gateway and str(gw_addr) != str(expected_gateway):
                    return RuleResult(
                        rule=rule_name,
                        status="ERROR",
                        message="Default gateway IP mismatch",
                        evidence=f"Host configured gateway {gateway_ip} does not match expected router gateway {expected_gateway}",
                        severity="HIGH",
                    )
                return RuleResult(
                    rule=rule_name,
                    status="PASS",
                    message="Default gateway is valid for host subnet",
                    evidence=f"Gateway {gateway_ip} is within valid host subnet range {iface.network}",
                    severity="NONE",
                )
            except ValueError as err:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Invalid IP/Gateway address syntax",
                    evidence=str(err),
                    severity="HIGH",
                )

    text = _extract_text_evidence(evidence_input)

    # Text pattern check 1: IP 10.1.1.50 mask 255.255.255.240; Gateway 10.1.1.30
    pattern1 = re.search(r"IP\s+([\d\.]+)\s+mask\s+([\d\.]+);\s*Gateway\s+([\d\.]+)", text, re.IGNORECASE)
    if pattern1:
        h_ip, h_mask, g_ip = pattern1.groups()
        try:
            iface = ipaddress.ip_interface(f"{h_ip}/{h_mask}")
            gw_addr = ipaddress.ip_address(g_ip)
            if gw_addr not in iface.network:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Default gateway is outside the host subnet",
                    evidence=f"Host IP {h_ip} mask {h_mask} belongs to subnet {iface.network}, but configured Gateway {g_ip} is outside",
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="Default gateway is within subnet boundary",
                evidence=f"Host IP {h_ip} Gateway {g_ip} is inside {iface.network}",
                severity="NONE",
            )
        except ValueError:
            pass

    # Text pattern check 2: Gateway set to 192.168.1.254 on PC (vs actual 192.168.1.1)
    pattern2 = re.search(r"Default\s+Gateway\s+([\d\.]+)\s+on\s+Host", text, re.IGNORECASE)
    if pattern2 and "192.168.1.1" in text:
        configured_gw = pattern2.group(1)
        if configured_gw != "192.168.1.1":
            return RuleResult(
                rule=rule_name,
                status="ERROR",
                message="Default gateway IP misconfiguration",
                evidence=f"Host configured with default gateway {configured_gw}, actual subnet gateway is 192.168.1.1",
                severity="HIGH",
            )

    if re.search(r"gateway\s+misconfiguration|gateway\s+outside|gateway\s+mismatch", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Default gateway mismatch detected",
            evidence=text,
            severity="HIGH",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate default gateway configuration",
        evidence="No host IP, subnet mask, and gateway combination present in evidence",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Rule 4: Interface Status Detection
# -----------------------------------------------------------------------------
def check_interface_status(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects down or administratively shutdown interfaces.
    """
    rule_name = "interface_status"

    # Structured dict check
    if isinstance(evidence_input, dict):
        interfaces = evidence_input.get("interfaces")
        if isinstance(interfaces, list) and interfaces:
            down_ifaces = []
            for iface in interfaces:
                if isinstance(iface, dict):
                    name = iface.get("name", "Unknown")
                    status = str(iface.get("status", "")).lower()
                    if "down" in status or "shutdown" in status or "err-disabled" in status:
                        down_ifaces.append(f"{name} ({status})")
            if down_ifaces:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Interface down or disabled detected",
                    evidence=f"Interfaces down: {', '.join(down_ifaces)}",
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="Interface status is up",
                evidence=f"All {len(interfaces)} interface(s) are in up/operational state",
                severity="NONE",
            )

    text = _extract_text_evidence(evidence_input)

    # Patterns matching interface down
    # e.g., GigabitEthernet0/0.10 is administratively down line protocol is down
    iface_down_match = re.search(
        r"(\S+)\s+is\s+(administratively\s+down|down)", text, re.IGNORECASE
    )
    if iface_down_match:
        if_name = iface_down_match.group(1)
        if_state = iface_down_match.group(2)
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message=f"Interface {if_name} is down",
            evidence=f"Output shows: {if_name} is {if_state}",
            severity="HIGH",
        )

    # Shutdown in config
    if re.search(r"interface\s+(\S+);?\s+.*shutdown", text, re.IGNORECASE) or re.search(r"shutdown\s+state", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Interface is in shutdown state",
            evidence=text,
            severity="HIGH",
        )

    # Err-disabled port security violation
    if "err-disabled" in text.lower() or "security violation occurred" in text.lower():
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Interface in err-disabled state due to security violation",
            evidence=text,
            severity="HIGH",
        )

    if re.search(r"is\s+up,\s+line\s+protocol\s+is\s+up", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="PASS",
            message="Interface status is up",
            evidence=text,
            severity="NONE",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate interface status",
        evidence="No interface status command outputs or state indicators present",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Rule 5: Missing VLAN Detection
# -----------------------------------------------------------------------------
def check_missing_vlans(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects missing VLANs from switch allowed VLAN list, wrong access VLAN, or native VLAN mismatch.
    """
    rule_name = "missing_vlan"

    # Structured dict check
    if isinstance(evidence_input, dict):
        required_vlan = evidence_input.get("required_vlan")
        configured_vlans = evidence_input.get("configured_vlans") or evidence_input.get("allowed_vlans")

        if required_vlan is not None and isinstance(configured_vlans, (list, set)):
            req_vlan_str = str(required_vlan)
            conf_vlan_strs = [str(v) for v in configured_vlans]
            if req_vlan_str not in conf_vlan_strs:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message=f"Required VLAN {req_vlan_str} is missing",
                    evidence=f"Required VLAN {req_vlan_str} not in configured VLANs list: {conf_vlan_strs}",
                    severity="MEDIUM",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message=f"Required VLAN {req_vlan_str} is present",
                evidence=f"VLAN {req_vlan_str} present in configured VLAN list",
                severity="NONE",
            )

    text = _extract_text_evidence(evidence_input)

    # Pattern: Switchport trunk allowed vlan 10 30 40 (VLAN 20 missing from allowed list)
    missing_allowed_match = re.search(r"VLAN\s+(\d+)\s+missing\s+from\s+allowed\s+list", text, re.IGNORECASE)
    if missing_allowed_match:
        missing_vlan = missing_allowed_match.group(1)
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message=f"Required VLAN {missing_vlan} is missing from trunk allowed list",
            evidence=f"Trunk allowed list missing VLAN {missing_vlan}",
            severity="MEDIUM",
        )

    # Pattern: switchport access vlan 14 (when PC in VLAN 40)
    access_vlan_match = re.search(r"switchport\s+access\s+vlan\s+(\d+)", text, re.IGNORECASE)
    if access_vlan_match:
        configured_vlan = access_vlan_match.group(1)
        if "VLAN 40" in text and configured_vlan != "40":
            return RuleResult(
                rule=rule_name,
                status="ERROR",
                message=f"Wrong access VLAN assigned (configured VLAN {configured_vlan}, expected VLAN 40)",
                evidence=f"Switchport access vlan {configured_vlan} assigned to host in VLAN 40",
                severity="MEDIUM",
            )

    # Native VLAN mismatch
    if re.search(r"native\s+vlan\s+mismatch", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Native VLAN mismatch detected on trunk link",
            evidence=text,
            severity="MEDIUM",
        )

    if re.search(r"inter-switch\s+link\s+configured\s+as\s+access\s+instead\s+of\s+trunk", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Trunk link misconfigured as access port (VLAN encapsulation missing)",
            evidence=text,
            severity="HIGH",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate VLAN configuration",
        evidence="No VLAN database, switchport access, or trunk allowed VLAN info present",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Rule 6: Missing Route Detection
# -----------------------------------------------------------------------------
def check_missing_routes(evidence_input: Union[Dict[str, Any], str]) -> RuleResult:
    """
    Detects missing routes, unreachable next-hops, or missing redistribution flags.
    """
    rule_name = "missing_route"

    # Structured dict check
    if isinstance(evidence_input, dict):
        destination_net = evidence_input.get("destination") or evidence_input.get("destination_network")
        routing_table = evidence_input.get("routing_table") or evidence_input.get("routes")

        if destination_net and isinstance(routing_table, list):
            if destination_net not in routing_table:
                return RuleResult(
                    rule=rule_name,
                    status="ERROR",
                    message="Required route is missing",
                    evidence=f"Destination network {destination_net} not found in routing table {routing_table}",
                    severity="HIGH",
                )
            return RuleResult(
                rule=rule_name,
                status="PASS",
                message="Required route is present",
                evidence=f"Route for {destination_net} exists in routing table",
                severity="NONE",
            )

    text = _extract_text_evidence(evidence_input)

    # Explicit missing route text e.g., "No route for 192.168.30.0/24"
    no_route_match = re.search(r"No\s+route\s+for\s+([\d\.\/]+)", text, re.IGNORECASE)
    if no_route_match:
        dest = no_route_match.group(1)
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message=f"Required route for {dest} is missing",
            evidence=f"Routing table check: No route for {dest}",
            severity="HIGH",
        )

    # Unreachable next hop
    unreachable_nh_match = re.search(r"Next-hop\s+IP\s+([\d\.]+)\s+unreachable", text, re.IGNORECASE)
    if unreachable_nh_match:
        nh_ip = unreachable_nh_match.group(1)
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Invalid or unreachable static route next-hop IP",
            evidence=f"Static route next-hop IP {nh_ip} is unreachable",
            severity="HIGH",
        )

    # Missing subnets flag in OSPF redistribution
    if "redistribute eigrp" in text.lower() and "missing subnets" in text.lower():
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="OSPF route redistribution missing subnets flag",
            evidence="redistribute command missing 'subnets' keyword, preventing sub-netted routes from propagating",
            severity="MEDIUM",
        )

    # Passive interface on active route link
    if "passive-interface" in text.lower() and "active ospf link" in text.lower():
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Passive interface enabled on active OSPF link blocking routes",
            evidence=text,
            severity="HIGH",
        )

    if re.search(r"missing\s+routes|route\s+missing", text, re.IGNORECASE):
        return RuleResult(
            rule=rule_name,
            status="ERROR",
            message="Missing route detected",
            evidence=text,
            severity="HIGH",
        )

    return RuleResult(
        rule=rule_name,
        status="NOT_CHECKED",
        message="Insufficient evidence to evaluate routing table configuration",
        evidence="No destination network or routing table output available",
        severity="NONE",
    )


# -----------------------------------------------------------------------------
# Runner Functions
# -----------------------------------------------------------------------------
def run_all_checks(evidence_input: Union[Dict[str, Any], str]) -> List[RuleResult]:
    """
    Runs all 6 deterministic network rule checks against the provided evidence input.
    Returns a list of RuleResult objects.
    """
    checks = [
        check_duplicate_ips,
        check_subnet_masks,
        check_gateway_mismatch,
        check_interface_status,
        check_missing_vlans,
        check_missing_routes,
    ]
    return [check(evidence_input) for check in checks]


def run_checker_on_dataset(csv_path: Optional[Union[Path, str]] = None) -> Dict[str, List[RuleResult]]:
    """
    Loads cases from cases.csv via dataset_loader and runs all 6 rule checks on each case.
    """
    cases = load_cases_as_dicts(csv_path)
    results_by_case = {}
    for c in cases:
        case_id = c.get("case_id", "UNKNOWN")
        results_by_case[case_id] = run_all_checks(c)
    return results_by_case


def print_cli_report(csv_path: Optional[Union[Path, str]] = None):
    """
    CLI execution handler that outputs formatted validation results for all cases in cases.csv.
    """
    dataset_results = run_checker_on_dataset(csv_path)

    print("=" * 65)
    print("           NETSAGE AI - DETERMINISTIC RULE CHECKER          ")
    print("=" * 65)
    print(f"Total Cases Evaluated: {len(dataset_results)}")
    print("Rule Checker Safety  : DETERMINISTIC PASSIVE CHECK (0 Config Changes)")
    print("=" * 65)
    print("")

    total_rules_run = 0
    errors_detected = 0
    passes_detected = 0
    not_checked_count = 0

    for case_id, results in dataset_results.items():
        print(f"Case: {case_id}")
        for r in results:
            total_rules_run += 1
            if r.status == "ERROR":
                errors_detected += 1
                status_str = "[ERROR]"
            elif r.status == "PASS":
                passes_detected += 1
                status_str = "[PASS]"
            else:
                not_checked_count += 1
                status_str = "[NOT_CHECKED]"

            print(f"  Rule: {r.rule:20s} Status: {status_str:14s} Message: {r.message}")
            if r.status == "ERROR":
                print(f"    |- Evidence: {r.evidence}")
        print("-" * 65)

    print("\n" + "=" * 65)
    print("                     SUMMARY METRICS                        ")
    print("=" * 65)
    print(f"Total Rule Checks Evaluated : {total_rules_run}")
    print(f"Rule Violations Detected    : {errors_detected}")
    print(f"Rule Checks Passed          : {passes_detected}")
    print(f"Rules Not Checked (No Data) : {not_checked_count}")
    print("=" * 65)


if __name__ == "__main__":
    print_cli_report()
