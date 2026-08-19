from __future__ import annotations

import unittest

from mikrotik_routeros_mcp.client import RouterOsFleetClient
from mikrotik_routeros_mcp.models import AppConfig, DeviceConfig


class SafeApplyWiringTests(unittest.TestCase):
    def test_safe_apply_fails_closed_without_ssh_transport(self) -> None:
        device = DeviceConfig(
            name="api-only",
            host="router",
            username="admin",
            allow_writes=True,
            transport_order=["api"],
        )
        client = RouterOsFleetClient(AppConfig(devices=[device]))

        with self.assertRaises(RuntimeError) as ctx:
            client.safe_apply_script("api-only", "/ip dns set servers=9.9.9.9")

        self.assertIn("ssh", str(ctx.exception).lower())
        self.assertIn("safe mode", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
