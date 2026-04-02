from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import AppConfig, DeviceConfig

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


DEFAULT_CONFIG_CANDIDATES = (
    "devices.yaml",
    "devices.yml",
    "devices.json",
)


def _default_config_path() -> Path:
    env_path = os.getenv("MIKROTIK_ROUTEROS_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    for candidate in DEFAULT_CONFIG_CANDIDATES:
        path = Path.cwd() / candidate
        if path.exists():
            return path
    return Path.cwd() / DEFAULT_CONFIG_CANDIDATES[0]


def _load_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"MikroTik RouterOS config not found at {path}. Set MIKROTIK_ROUTEROS_CONFIG or create devices.yaml."
        )
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML config files.")
        loaded = yaml.safe_load(text)
        if loaded is None:
            return {}
        if not isinstance(loaded, dict):
            raise ValueError("Root config must be an object.")
        return loaded
    raise ValueError(f"Unsupported config format: {path.suffix}")


def _ensure_list_of_strings(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return value


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path).expanduser() if path is not None else _default_config_path()
    raw = _load_raw_config(config_path)
    raw_devices = raw.get("devices")
    if not isinstance(raw_devices, list) or not raw_devices:
        raise ValueError("Config must contain a non-empty 'devices' list.")

    devices: list[DeviceConfig] = []
    seen_names: set[str] = set()
    for item in raw_devices:
        if not isinstance(item, dict):
            raise ValueError("Each device entry must be an object.")
        name = item.get("name")
        host = item.get("host")
        username = item.get("username")
        if not all(isinstance(value, str) and value.strip() for value in (name, host, username)):
            raise ValueError("Each device must define non-empty string values for name, host, and username.")
        if name in seen_names:
            raise ValueError(f"Duplicate device name: {name}")
        seen_names.add(name)
        transport_order = _ensure_list_of_strings(item.get("transport_order"), field_name=f"{name}.transport_order")
        if not transport_order:
            transport_order = ["api", "api-ssl", "ssh"]
        invalid = [transport for transport in transport_order if transport not in {"api", "api-ssl", "ssh"}]
        if invalid:
            raise ValueError(f"Invalid transport names for {name}: {', '.join(invalid)}")
        devices.append(
            DeviceConfig(
                name=name,
                host=host,
                username=username,
                password=item.get("password"),
                private_key=item.get("private_key"),
                fallback_ip=item.get("fallback_ip"),
                api_port=int(item.get("api_port", 8728)),
                api_ssl_port=int(item.get("api_ssl_port", 8729)),
                ssh_port=int(item.get("ssh_port", 22)),
                timeout_seconds=float(item.get("timeout_seconds", 10.0)),
                transport_order=transport_order,
                allow_writes=bool(item.get("allow_writes", False)),
                tags=_ensure_list_of_strings(item.get("tags"), field_name=f"{name}.tags"),
            )
        )
    return AppConfig(devices=devices, log_level=str(raw.get("log_level", "INFO")))
