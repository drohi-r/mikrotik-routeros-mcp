from __future__ import annotations

import socket
from typing import Any

from ..models import DeviceConfig
from .base import BaseTransport, TransportError

try:
    import routeros_api
except ImportError:  # pragma: no cover
    routeros_api = None


def _resolve_host(device: DeviceConfig) -> str:
    try:
        socket.getaddrinfo(device.host, None)
        return device.host
    except socket.gaierror:
        if device.fallback_ip:
            return device.fallback_ip
        raise


class ApiTransport(BaseTransport):
    name = "api"

    def __init__(self, device: DeviceConfig, *, use_ssl: bool = False) -> None:
        super().__init__(device)
        self.use_ssl = use_ssl
        self.name = "api-ssl" if use_ssl else "api"

    def _pool(self) -> Any:
        if routeros_api is None:
            raise TransportError("routeros-api dependency is not installed.")
        host = _resolve_host(self.device)
        port = self.device.api_ssl_port if self.use_ssl else self.device.api_port
        try:
            return routeros_api.RouterOsApiPool(
                host,
                username=self.device.username,
                password=self.device.password or "",
                port=port,
                use_ssl=self.use_ssl,
                plaintext_login=not self.use_ssl,
                socket_timeout=self.device.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover
            raise TransportError(f"{self.name} connection failed for {self.device.name}: {exc}") from exc

    def ping(self) -> dict[str, Any]:
        return {"reachable": True, "transport": self.name}

    def print_resource(self, path: str, **params: Any) -> Any:
        pool = self._pool()
        try:
            api = pool.get_api()
            resource = api.get_resource(path)
            rows = resource.get(**params)
            return {"path": path, "items": rows}
        except Exception as exc:
            raise TransportError(f"{self.name} print failed for {path}: {exc}") from exc
        finally:
            pool.disconnect()

    def export_config(self, *, hide_sensitive: bool = True) -> Any:
        raise TransportError("Config export is not supported over the RouterOS API transport. Try SSH fallback.")

    def run_script(self, script: str) -> Any:
        raise TransportError("Script execution is not enabled over the RouterOS API transport. Try SSH fallback.")
