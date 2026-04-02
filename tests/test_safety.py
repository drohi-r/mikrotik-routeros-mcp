from __future__ import annotations

import unittest

from mikrotik_routeros_mcp.models import DeviceConfig
from mikrotik_routeros_mcp.safety import classify_script_risk, plan_script_change, verify_approval_code


class SafetyTests(unittest.TestCase):
    def test_risk_classification(self) -> None:
        self.assertEqual(classify_script_risk("/ip address print"), "low")
        self.assertEqual(
            classify_script_risk("/ip address add address=192.168.1.2/24 interface=bridge"),
            "medium",
        )
        self.assertEqual(classify_script_risk("/system reboot"), "high")

    def test_plan_blocks_writes_when_device_is_read_only(self) -> None:
        device = DeviceConfig(name="office", host="router", username="admin", allow_writes=False)

        plan = plan_script_change(device, "/system reboot", "maintenance window")

        self.assertTrue(plan.blocked)
        self.assertEqual(plan.risk, "high")

    def test_approval_code_validation(self) -> None:
        device = DeviceConfig(name="home", host="router", username="admin", allow_writes=True)
        script = "/ip firewall filter add chain=input action=accept comment=mcp"
        reason = "temporary test"
        plan = plan_script_change(device, script, reason)

        verify_approval_code(device.name, script, reason, plan.approval_code)


if __name__ == "__main__":
    unittest.main()
