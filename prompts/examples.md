# NetSage AI - Worked Diagnostic Examples

This document provides reference worked examples showing input case evidence and corresponding structured JSON diagnosis outputs.

---

## Example 1: Interface Down Fault (`NET-001`)

### INPUT

* **Case ID**: NET-001
* **Symptom**: PC1 cannot reach Server1 in VLAN 30
* **Topology Note**: PC1 on Fa0/1 (VLAN 10); Gateway on Router Sub-interface Gi0/0.10
* **Show Output**: GigabitEthernet0/0.10 is administratively down line protocol is down
* **Rule Checker Findings**:
  * `interface_status` -> ERROR: Interface GigabitEthernet0/0.10 is down

### OUTPUT JSON

```json
{
  "case_id": "NET-001",
  "root_cause": "Router sub-interface GigabitEthernet0/0.10 is administratively shut down.",
  "diagnosis_status": "CONFIRMED",
  "confidence": 1.0,
  "osi_layer": "Layer 3",
  "evidence": [
    "GigabitEthernet0/0.10 is administratively down line protocol is down",
    "Rule Checker: Interface GigabitEthernet0/0.10 is down"
  ],
  "rule_checker_findings": [
    {
      "rule": "interface_status",
      "status": "ERROR",
      "message": "Interface GigabitEthernet0/0.10 is down"
    }
  ],
  "next_command": null,
  "fix_steps": [
    "Enter interface configuration mode for GigabitEthernet0/0.10 on Router R1.",
    "Execute 'no shutdown' on sub-interface GigabitEthernet0/0.10.",
    "Verify interface status using 'show ip interface brief'."
  ],
  "explanation": "Show output explicitly confirms GigabitEthernet0/0.10 is administratively down, blocking Inter-VLAN routing for VLAN 10."
}
```

---

## Example 2: Missing Trunking VLAN (`NET-008`)

### INPUT

* **Case ID**: NET-008
* **Symptom**: Trunk link between SW1 and SW2 failing to carry VLAN 20 traffic
* **Topology Note**: SW1 Fa0/24 connected to SW2 Fa0/24
* **Show Output**: Switchport trunk allowed vlan 10 30 40 (VLAN 20 missing from allowed list)
* **Rule Checker Findings**:
  * `missing_vlan` -> ERROR: Required VLAN 20 is missing from trunk allowed list

### OUTPUT JSON

```json
{
  "case_id": "NET-008",
  "root_cause": "VLAN 20 is missing from the allowed VLAN list on switch trunk interface FastEthernet0/24.",
  "diagnosis_status": "CONFIRMED",
  "confidence": 0.98,
  "osi_layer": "Layer 2",
  "evidence": [
    "Switchport trunk allowed vlan 10 30 40 (VLAN 20 missing from allowed list)",
    "Rule Checker: Required VLAN 20 is missing from trunk allowed list"
  ],
  "rule_checker_findings": [
    {
      "rule": "missing_vlan",
      "status": "ERROR",
      "message": "Required VLAN 20 is missing from trunk allowed list"
    }
  ],
  "next_command": null,
  "fix_steps": [
    "Access switch interface FastEthernet0/24 configuration.",
    "Execute 'switchport trunk allowed vlan add 20'.",
    "Verify trunking status with 'show interfaces trunk'."
  ],
  "explanation": "VLAN 20 traffic is pruned on the inter-switch trunk because it was omitted from the allowed VLAN list on interface Fa0/24."
}
```

---

## Example 3: Routing / ACL Issue (`NET-005`)

### INPUT

* **Case ID**: NET-005
* **Symptom**: Web server port 80 unreachable from Sales subnet
* **Topology Note**: Sales PC on 192.168.10.0/24; Web Server on 10.0.0.10/24
* **Show Output**: access-list 101 deny tcp 192.168.10.0 0.0.0.255 host 10.0.0.10 eq 80
* **Rule Checker Findings**:
  * All deterministic checks: NOT_CHECKED (No rule checker syntax violations found)

### OUTPUT JSON

```json
{
  "case_id": "NET-005",
  "root_cause": "Extended IP Access List 101 contains an explicit rule denying HTTP traffic (TCP port 80) from Sales subnet 192.168.10.0/24 to Web Server 10.0.0.10.",
  "diagnosis_status": "CONFIRMED",
  "confidence": 0.95,
  "osi_layer": "Layer 4",
  "evidence": [
    "access-list 101 deny tcp 192.168.10.0 0.0.0.255 host 10.0.0.10 eq 80"
  ],
  "rule_checker_findings": [],
  "next_command": "show access-lists 101",
  "fix_steps": [
    "Modify Access List 101 to permit TCP port 80 traffic or remove the deny entry.",
    "Re-apply Access List 101 to the relevant interface in the correct direction.",
    "Verify web connectivity from Sales PC to Web Server 10.0.0.10:80."
  ],
  "explanation": "Show output reveals an active extended ACL entry blocking TCP port 80 traffic originating from 192.168.10.0/24 destined to 10.0.0.10."
}
```
