from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


TransportName = Literal["api", "api-ssl", "ssh"]


@dataclass(slots=True)
class DeviceConfig:
    name: str
    host: str
    username: str
    password: str | None = None
    private_key: str | None = None
    fallback_ip: str | None = None
    api_port: int = 8728
    api_ssl_port: int = 8729
    ssh_port: int = 22
    timeout_seconds: float = 10.0
    transport_order: list[TransportName] = field(default_factory=lambda: ["api", "api-ssl", "ssh"])
    allow_writes: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AppConfig:
    devices: list[DeviceConfig]
    log_level: str = "INFO"

    def get_device(self, name: str) -> DeviceConfig:
        for device in self.devices:
            if device.name == name:
                return device
        known = ", ".join(sorted(device.name for device in self.devices))
        raise KeyError(f"Unknown device '{name}'. Known devices: {known}")
