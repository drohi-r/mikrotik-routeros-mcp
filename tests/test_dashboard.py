"""Tests for the web dashboard REST API."""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import yaml

from mikrotik_routeros_mcp.dashboard import DashboardState, _make_handler


def _write_config(tmp: Path, devices: list[dict]) -> None:
    tmp.write_text(yaml.dump({"devices": devices}), encoding="utf-8")


def _minimal_device(name: str = "test", host: str = "192.168.1.1") -> dict:
    return {"name": name, "host": host, "username": "admin", "password": "pw"}


class DashboardAPITests(unittest.TestCase):
    """Spin up the dashboard on a random port, test the REST API."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
        _write_config(Path(cls._tmp.name), [_minimal_device()])
        cls._tmp.close()

        cls._env_patch = patch.dict(
            "os.environ", {"MIKROTIK_ROUTEROS_CONFIG": cls._tmp.name}
        )
        cls._env_patch.start()

        cls.state = DashboardState()
        cls.server = HTTPServer(("127.0.0.1", 0), _make_handler(cls.state))
        cls.port = cls.server.server_address[1]
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls._env_patch.stop()
        Path(cls._tmp.name).unlink(missing_ok=True)

    def _get(self, path: str) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            r = urllib.request.urlopen(url, timeout=5)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _post(self, path: str, data: dict) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            r = urllib.request.urlopen(req, timeout=5)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _delete(self, path: str) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, method="DELETE")
        try:
            r = urllib.request.urlopen(req, timeout=5)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # -- Tests --

    def test_list_devices(self) -> None:
        status, data = self._get("/api/devices")
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["name"], "test")

    def test_describe_device(self) -> None:
        status, data = self._get("/api/devices/test")
        self.assertEqual(status, 200)
        self.assertEqual(data["name"], "test")
        self.assertIn("ports", data)

    def test_unknown_device_returns_404(self) -> None:
        status, data = self._get("/api/devices/nonexistent")
        self.assertEqual(status, 404)

    def test_unknown_sub_resource_returns_404(self) -> None:
        status, data = self._get("/api/devices/test/foobar")
        self.assertEqual(status, 404)

    def test_index_returns_html(self) -> None:
        url = f"http://127.0.0.1:{self.port}/"
        r = urllib.request.urlopen(url, timeout=5)
        self.assertEqual(r.status, 200)
        self.assertIn("text/html", r.headers.get("Content-Type", ""))
        body = r.read().decode()
        self.assertIn("MIKROTIK DASHBOARD", body)

    def test_add_and_remove_device(self) -> None:
        # Add
        status, data = self._post("/api/devices", {
            "name": "new-router",
            "host": "10.0.0.1",
            "username": "admin",
        })
        self.assertEqual(status, 201)
        self.assertTrue(data["ok"])

        # Verify it appears
        status, devices = self._get("/api/devices")
        names = [d["name"] for d in devices]
        self.assertIn("new-router", names)

        # Remove
        status, data = self._delete("/api/devices/new-router")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

        # Verify gone
        status, devices = self._get("/api/devices")
        names = [d["name"] for d in devices]
        self.assertNotIn("new-router", names)

    def test_add_duplicate_returns_409(self) -> None:
        status, data = self._post("/api/devices", {
            "name": "test",
            "host": "1.2.3.4",
            "username": "admin",
        })
        self.assertEqual(status, 409)

    def test_add_missing_fields_returns_400(self) -> None:
        status, data = self._post("/api/devices", {"name": "x"})
        self.assertEqual(status, 400)

    def test_not_found_route(self) -> None:
        status, data = self._get("/api/nonexistent")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
