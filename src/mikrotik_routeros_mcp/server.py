from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import RouterOsFleetClient
from .config import DEFAULT_CONFIG_CANDIDATES, load_config
from .safety import plan_script_change as build_script_plan
from .safety import verify_approval_code


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2)


def _parse_object(value: str | None, *, field_name: str) -> dict[str, Any]:
    if value is None or not value.strip():
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must decode to a JSON object.")
    return parsed


def _assert_read_only_path(path: str) -> None:
    lowered = path.strip().lower()
    blocked_tokens = ("add", "set", "remove", "enable", "disable")
    if any(token in lowered for token in blocked_tokens):
        raise ValueError("run_api_print is read-only and only supports print-style RouterOS API paths.")


@lru_cache(maxsize=1)
def _client() -> RouterOsFleetClient:
    return RouterOsFleetClient(load_config())


mcp = FastMCP(
    name="MikroTik RouterOS MCP",
    instructions=(
        "Use explicit device names like 'home' and 'office'. Prefer the named read tools first. "
        "Use plan_script_change before any apply_script_change call, and avoid writes unless the "
        "target device is configured to allow them."
    ),
)


@mcp.tool()
def get_server_config() -> str:
    config = load_config()
    return _json(
        {
            "device_count": len(config.devices),
            "device_names": [device.name for device in config.devices],
            "default_config_candidates": list(DEFAULT_CONFIG_CANDIDATES),
            "log_level": config.log_level,
        }
    )


@mcp.tool()
def list_devices() -> str:
    return _json(_client().list_devices())


@mcp.tool()
def describe_device(device: str) -> str:
    return _json(_client().describe_device(device))


@mcp.tool()
def system_info(device: str) -> str:
    response = _client().print_resource(device, "/system/resource")
    return _json(response)


@mcp.tool()
def interfaces(device: str, include_disabled: bool = True) -> str:
    response = _client().print_resource(device, "/interface", disabled="false" if not include_disabled else "")
    return _json(response)


@mcp.tool()
def ip_addresses(device: str) -> str:
    response = _client().print_resource(device, "/ip/address")
    return _json(response)


@mcp.tool()
def routes(device: str, active_only: bool = False) -> str:
    params: dict[str, Any] = {}
    if active_only:
        params["active"] = "true"
    response = _client().print_resource(device, "/ip/route", **params)
    return _json(response)


@mcp.tool()
def firewall_filters(device: str, chain: str = "", disabled_only: bool = False) -> str:
    params: dict[str, Any] = {}
    if chain:
        params["chain"] = chain
    if disabled_only:
        params["disabled"] = "true"
    response = _client().print_resource(device, "/ip/firewall/filter", **params)
    return _json(response)


@mcp.tool()
def nat_rules(device: str, disabled_only: bool = False) -> str:
    params: dict[str, Any] = {"disabled": "true"} if disabled_only else {}
    response = _client().print_resource(device, "/ip/firewall/nat", **params)
    return _json(response)


@mcp.tool()
def dns_settings(device: str) -> str:
    response = _client().print_resource(device, "/ip/dns")
    return _json(response)


@mcp.tool()
def dhcp_servers(device: str) -> str:
    response = _client().print_resource(device, "/ip/dhcp-server")
    return _json(response)


@mcp.tool()
def logs(device: str, topics: str = "", limit: int = 50) -> str:
    params: dict[str, Any] = {}
    if topics:
        params["topics"] = topics
    if limit > 0:
        params[".proplist"] = "time,topics,message"
    response = _client().print_resource(device, "/log", **params)
    payload = response
    result = payload.get("result", {})
    if isinstance(result, dict):
        log_result = result.get("items") or result.get("raw")
        if isinstance(log_result, list) and limit > 0:
            result["items"] = log_result[:limit]
    return _json(payload)


@mcp.tool()
def ping(device: str, address: str, count: int = 4) -> str:
    response = _client().ping(device, address=address, count=count)
    return _json(response)


@mcp.tool()
def export_config(device: str, hide_sensitive: bool = True) -> str:
    response = _client().export_config(device, hide_sensitive=hide_sensitive)
    return _json(response)


@mcp.tool()
def run_api_print(device: str, path: str, parameters_json: str = "{}") -> str:
    _assert_read_only_path(path)
    params = _parse_object(parameters_json, field_name="parameters_json")
    response = _client().print_resource(device, path, **params)
    return _json(response)


@mcp.tool()
def plan_script_change(device: str, script: str, reason: str) -> str:
    device_config = _client().get_device(device)
    plan = build_script_plan(device_config, script, reason)
    return _json(
        {
            "device": plan.device,
            "reason": plan.reason,
            "risk": plan.risk,
            "writes_allowed": plan.writes_allowed,
            "approval_code": plan.approval_code,
            "blocked": plan.blocked,
            "summary": plan.summary,
        }
    )


@mcp.tool()
def apply_script_change(device: str, script: str, reason: str, approval_code: str) -> str:
    device_config = _client().get_device(device)
    plan = build_script_plan(device_config, script, reason)
    if plan.blocked:
        raise ValueError(plan.summary)
    verify_approval_code(device, script, reason, approval_code)
    response = _client().run_script(device, script)
    return _json(
        {
            "device": device,
            "risk": plan.risk,
            "approval_code": approval_code,
            "response": response,
        }
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
