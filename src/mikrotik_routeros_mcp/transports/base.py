from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import DeviceConfig


class TransportError(RuntimeError):
    pass


class UnsupportedOperationError(TransportError):
    pass


class BaseTransport(ABC):
    name: str

    def __init__(self, device: DeviceConfig) -> None:
        self.device = device

    @abstractmethod
    def ping(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def print_resource(self, path: str, **params: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def export_config(self, *, hide_sensitive: bool = True) -> Any:
        raise NotImplementedError

    @abstractmethod
    def run_script(self, script: str) -> Any:
        raise NotImplementedError
