from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mikrotik_routeros_mcp.snapshots import SnapshotStore


class SnapshotStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = SnapshotStore(root=Path(self._tmp.name))

    def test_save_writes_export_and_returns_info(self) -> None:
        info = self.store.save("office", "/ip address add address=192.168.10.1/24\n")

        self.assertEqual(info.device, "office")
        self.assertTrue(info.path.exists())
        self.assertEqual(info.path.suffix, ".rsc")
        self.assertEqual(info.path.read_text(), "/ip address add address=192.168.10.1/24\n")
        self.assertEqual(info.size_bytes, len("/ip address add address=192.168.10.1/24\n"))

    def test_save_generates_unique_ids_for_same_second(self) -> None:
        first = self.store.save("office", "a\n")
        second = self.store.save("office", "b\n")

        self.assertNotEqual(first.id, second.id)
        self.assertTrue(second.path.exists())

    def test_list_snapshots_returns_newest_first(self) -> None:
        first = self.store.save("office", "a\n")
        second = self.store.save("office", "b\n")

        listed = self.store.list_snapshots("office")

        self.assertEqual([item.id for item in listed], [second.id, first.id])

    def test_list_snapshots_for_unknown_device_is_empty(self) -> None:
        self.assertEqual(self.store.list_snapshots("nowhere"), [])

    def test_diff_produces_unified_diff(self) -> None:
        old = self.store.save("office", "/ip route add dst-address=0.0.0.0/0\n/ip dns set servers=1.1.1.1\n")
        new = self.store.save("office", "/ip route add dst-address=0.0.0.0/0\n/ip dns set servers=9.9.9.9\n")

        diff = self.store.diff("office", old.id, new.id)

        self.assertIn("-/ip dns set servers=1.1.1.1", diff)
        self.assertIn("+/ip dns set servers=9.9.9.9", diff)

    def test_diff_unknown_id_raises(self) -> None:
        known = self.store.save("office", "a\n")

        with self.assertRaises(KeyError):
            self.store.diff("office", known.id, "20990101T000000Z")


if __name__ == "__main__":
    unittest.main()
