"""Lightweight web dashboard for multi-router management.

Serves a single-page HTML UI backed by a REST API that wraps the
existing RouterOsFleetClient.  No extra dependencies beyond the
Python standard library are required (the project already pulls in
PyYAML for config handling).

Start with::

    python -m mikrotik_routeros_mcp.dashboard [--port 8080] [--host 0.0.0.0]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import yaml

from .client import RouterOsFleetClient
from .config import load_config, _default_config_path
from .models import AppConfig

logger = logging.getLogger(__name__)

_HTML_PATH = Path(__file__).with_name("dashboard_ui.html")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, indent=2).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    _json_response(handler, {"error": message}, status)


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", 0))
    return handler.rfile.read(length) if length else b""


# ---------------------------------------------------------------------------
# Config management (add / remove devices in YAML)
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    return _default_config_path()


def _save_config(config: AppConfig) -> None:
    """Persist the current AppConfig back to the YAML config file."""
    path = _config_path()
    devices_list: list[dict[str, Any]] = []
    for d in config.devices:
        entry: dict[str, Any] = {
            "name": d.name,
            "host": d.host,
            "username": d.username,
        }
        if d.password:
            entry["password"] = d.password
        if d.private_key:
            entry["private_key"] = d.private_key
        if d.fallback_ip:
            entry["fallback_ip"] = d.fallback_ip
        entry["api_port"] = d.api_port
        entry["api_ssl_port"] = d.api_ssl_port
        entry["ssh_port"] = d.ssh_port
        entry["timeout_seconds"] = d.timeout_seconds
        entry["transport_order"] = list(d.transport_order)
        entry["allow_writes"] = d.allow_writes
        if d.tags:
            entry["tags"] = list(d.tags)
        devices_list.append(entry)
    raw: dict[str, Any] = {"devices": devices_list, "log_level": config.log_level}
    path.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class DashboardState:
    """Thread-safe wrapper around the fleet client and config."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self._config = load_config()
            self._client = RouterOsFleetClient(self._config)

    @property
    def client(self) -> RouterOsFleetClient:
        return self._client

    @property
    def config(self) -> AppConfig:
        return self._config

    def add_device(self, data: dict[str, Any]) -> None:
        from .models import DeviceConfig
        with self._lock:
            for d in self._config.devices:
                if d.name == data["name"]:
                    raise ValueError(f"Device '{data['name']}' already exists.")
            transport_order = data.get("transport_order", ["api", "api-ssl", "ssh"])
            device = DeviceConfig(
                name=data["name"],
                host=data["host"],
                username=data["username"],
                password=data.get("password"),
                private_key=data.get("private_key"),
                fallback_ip=data.get("fallback_ip"),
                api_port=int(data.get("api_port", 8728)),
                api_ssl_port=int(data.get("api_ssl_port", 8729)),
                ssh_port=int(data.get("ssh_port", 22)),
                timeout_seconds=float(data.get("timeout_seconds", 10.0)),
                transport_order=transport_order,
                allow_writes=bool(data.get("allow_writes", False)),
                tags=data.get("tags", []),
            )
            self._config.devices.append(device)
            _save_config(self._config)
            self._client = RouterOsFleetClient(self._config)

    def remove_device(self, name: str) -> None:
        with self._lock:
            before = len(self._config.devices)
            self._config.devices = [d for d in self._config.devices if d.name != name]
            if len(self._config.devices) == before:
                raise KeyError(f"Device '{name}' not found.")
            _save_config(self._config)
            self._client = RouterOsFleetClient(self._config)


# ---------------------------------------------------------------------------
# Route dispatching
# ---------------------------------------------------------------------------

_DEVICE_ROUTE = re.compile(r"^/api/devices/([^/]+)(?:/([a-z-]+))?$")


def _handle_get(handler: BaseHTTPRequestHandler, state: DashboardState) -> None:
    path = handler.path.split("?")[0]

    if path == "/":
        html = _HTML_PATH.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(html)))
        handler.end_headers()
        handler.wfile.write(html)
        return

    if path == "/api/devices":
        _json_response(handler, state.client.list_devices())
        return

    m = _DEVICE_ROUTE.match(path)
    if not m:
        _error(handler, 404, "Not found")
        return

    device_name = m.group(1)
    sub = m.group(2)

    try:
        if sub is None:
            _json_response(handler, state.client.describe_device(device_name))
        elif sub == "status":
            result = state.client.with_fallback(device_name, "ping", lambda t: t.ping())
            _json_response(handler, result)
        elif sub == "system":
            _json_response(handler, state.client.print_resource(device_name, "/system/resource"))
        elif sub == "interfaces":
            _json_response(handler, state.client.print_resource(device_name, "/interface"))
        elif sub == "dhcp-leases":
            _json_response(handler, state.client.print_resource(device_name, "/ip/dhcp-server/lease"))
        elif sub == "firewall":
            _json_response(handler, state.client.print_resource(device_name, "/ip/firewall/filter"))
        elif sub == "nat":
            _json_response(handler, state.client.print_resource(device_name, "/ip/firewall/nat"))
        elif sub == "routes":
            _json_response(handler, state.client.print_resource(device_name, "/ip/route"))
        elif sub == "addresses":
            _json_response(handler, state.client.print_resource(device_name, "/ip/address"))
        elif sub == "dns":
            _json_response(handler, state.client.print_resource(device_name, "/ip/dns"))
        elif sub == "neighbors":
            _json_response(handler, state.client.print_resource(device_name, "/ip/neighbor"))
        elif sub == "logs":
            result = state.client.print_resource(device_name, "/log", **{".proplist": "time,topics,message"})
            items = (result.get("result") or {}).get("items")
            if isinstance(items, list):
                result["result"]["items"] = items[:80]
            _json_response(handler, result)
        elif sub == "wireguard":
            _json_response(handler, state.client.print_resource(device_name, "/interface/wireguard"))
        else:
            _error(handler, 404, f"Unknown sub-resource: {sub}")
    except KeyError as exc:
        _error(handler, 404, str(exc))
    except Exception as exc:
        logger.exception("Error handling GET %s", path)
        _error(handler, 502, str(exc))


def _handle_post(handler: BaseHTTPRequestHandler, state: DashboardState) -> None:
    path = handler.path.split("?")[0]
    if path == "/api/devices":
        body = _read_body(handler)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            _error(handler, 400, "Invalid JSON")
            return
        for field in ("name", "host", "username"):
            if not data.get(field, "").strip():
                _error(handler, 400, f"Missing required field: {field}")
                return
        try:
            state.add_device(data)
            _json_response(handler, {"ok": True, "device": data["name"]}, 201)
        except ValueError as exc:
            _error(handler, 409, str(exc))
        except Exception as exc:
            logger.exception("Error adding device")
            _error(handler, 500, str(exc))
        return
    _error(handler, 404, "Not found")


def _handle_delete(handler: BaseHTTPRequestHandler, state: DashboardState) -> None:
    path = handler.path.split("?")[0]
    m = re.match(r"^/api/devices/([^/]+)$", path)
    if not m:
        _error(handler, 404, "Not found")
        return
    device_name = m.group(1)
    try:
        state.remove_device(device_name)
        _json_response(handler, {"ok": True, "removed": device_name})
    except KeyError as exc:
        _error(handler, 404, str(exc))
    except Exception as exc:
        logger.exception("Error removing device")
        _error(handler, 500, str(exc))


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def _make_handler(state: DashboardState):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            _handle_get(self, state)

        def do_POST(self) -> None:
            _handle_post(self, state)

        def do_DELETE(self) -> None:
            _handle_delete(self, state)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            logger.info(format, *args)

    return Handler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="MikroTik RouterOS Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    state = DashboardState()
    device_count = len(state.config.devices)
    logger.info("Loaded %d device(s) from config", device_count)

    server = HTTPServer((args.host, args.port), _make_handler(state))
    logger.info("Dashboard running at http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
