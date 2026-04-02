from __future__ import annotations

from typing import Any

from .models import AppConfig, DeviceConfig
from .transports.api import ApiTransport
from .transports.base import BaseTransport, TransportError
from .transports.ssh import SshTransport


class RouterOsFleetClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def get_device(self, name: str) -> DeviceConfig:
        return self.config.get_device(name)

    def list_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "name": device.name,
                "host": device.host,
                "fallback_ip": device.fallback_ip,
                "transport_order": device.transport_order,
                "allow_writes": device.allow_writes,
                "tags": device.tags,
            }
            for device in self.config.devices
        ]

    def describe_device(self, name: str) -> dict[str, Any]:
        device = self.get_device(name)
        return {
            "name": device.name,
            "host": device.host,
            "fallback_ip": device.fallback_ip,
            "ports": {
                "api": device.api_port,
                "api_ssl": device.api_ssl_port,
                "ssh": device.ssh_port,
            },
            "transport_order": device.transport_order,
            "allow_writes": device.allow_writes,
            "tags": device.tags,
        }

    def _transport_candidates(self, device: DeviceConfig) -> list[BaseTransport]:
        candidates: list[BaseTransport] = []
        for name in device.transport_order:
            if name == "api":
                candidates.append(ApiTransport(device, use_ssl=False))
            elif name == "api-ssl":
                candidates.append(ApiTransport(device, use_ssl=True))
            elif name == "ssh":
                candidates.append(SshTransport(device))
        return candidates

    def _preferred_candidates(self, device: DeviceConfig, preferred: tuple[str, ...]) -> list[BaseTransport]:
        candidates = self._transport_candidates(device)
        if not preferred:
            return candidates
        rank = {name: index for index, name in enumerate(preferred)}
        return sorted(candidates, key=lambda candidate: rank.get(candidate.name, len(rank)))

    def with_fallback(self, device_name: str, operation: str, callback) -> dict[str, Any]:
        device = self.get_device(device_name)
        errors: list[dict[str, str]] = []
        for transport in self._transport_candidates(device):
            try:
                result = callback(transport)
                return {
                    "device": device.name,
                    "transport": transport.name,
                    "operation": operation,
                    "result": result,
                    "errors": errors,
                }
            except TransportError as exc:
                errors.append({"transport": transport.name, "error": str(exc)})
        raise RuntimeError(
            f"All transports failed for device {device.name} during {operation}: "
            + "; ".join(f"{item['transport']}: {item['error']}" for item in errors)
        )

    def print_resource(self, device_name: str, path: str, **params: Any) -> dict[str, Any]:
        return self.with_fallback(device_name, f"print:{path}", lambda transport: transport.print_resource(path, **params))

    def ping(self, device_name: str, *, address: str, count: int) -> dict[str, Any]:
        def callback(transport: BaseTransport) -> Any:
            if transport.name.startswith("api"):
                return transport.print_resource("/ping", address=address, count=count)
            return transport.run_script(f"/ping address={address} count={count}")

        return self.with_fallback(device_name, "ping", callback)

    def export_config(self, device_name: str, *, hide_sensitive: bool = True) -> dict[str, Any]:
        device = self.get_device(device_name)
        errors: list[dict[str, str]] = []
        for transport in self._preferred_candidates(device, ("ssh",)):
            try:
                result = transport.export_config(hide_sensitive=hide_sensitive)
                return {
                    "device": device.name,
                    "transport": transport.name,
                    "operation": "export_config",
                    "result": result,
                    "errors": errors,
                }
            except TransportError as exc:
                errors.append({"transport": transport.name, "error": str(exc)})
        raise RuntimeError(
            f"All transports failed for device {device.name} during export_config: "
            + "; ".join(f"{item['transport']}: {item['error']}" for item in errors)
        )

    def run_script(self, device_name: str, script: str) -> dict[str, Any]:
        device = self.get_device(device_name)
        errors: list[dict[str, str]] = []
        for transport in self._preferred_candidates(device, ("ssh",)):
            try:
                result = transport.run_script(script)
                return {
                    "device": device.name,
                    "transport": transport.name,
                    "operation": "run_script",
                    "result": result,
                    "errors": errors,
                }
            except TransportError as exc:
                errors.append({"transport": transport.name, "error": str(exc)})
        raise RuntimeError(
            f"All transports failed for device {device.name} during run_script: "
            + "; ".join(f"{item['transport']}: {item['error']}" for item in errors)
        )
