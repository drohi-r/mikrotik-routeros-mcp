from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mikrotik_routeros_mcp.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_from_json(self) -> None:
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        config_path = Path(temp_dir.name) / "devices.json"
        config_path.write_text(
            """
{
  "devices": [
    {
      "name": "home",
      "host": "192.168.88.1",
      "username": "admin",
      "password": "secret",
      "transport_order": ["api", "ssh"],
      "tags": ["home"]
    },
    {
      "name": "office",
      "host": "office.example.com",
      "username": "admin",
      "password": "secret",
      "allow_writes": true
    }
  ]
}
""".strip(),
            encoding="utf-8",
        )

        config = load_config(config_path)

        self.assertEqual(len(config.devices), 2)
        self.assertEqual(config.get_device("home").transport_order, ["api", "ssh"])
        self.assertTrue(config.get_device("office").allow_writes)

    def test_duplicate_device_names_are_rejected(self) -> None:
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        config_path = Path(temp_dir.name) / "devices.json"
        config_path.write_text(
            """
{
  "devices": [
    {
      "name": "home",
      "host": "192.168.88.1",
      "username": "admin"
    },
    {
      "name": "home",
      "host": "192.168.88.2",
      "username": "admin"
    }
  ]
}
""".strip(),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "Duplicate device name"):
            load_config(config_path)


if __name__ == "__main__":
    unittest.main()
