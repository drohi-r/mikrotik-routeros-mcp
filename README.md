# MikroTik RouterOS MCP

Public MCP server for managing multiple MikroTik RouterOS devices from one place.

This repo is designed around the two things the current public MikroTik MCP options do best:

- broad RouterOS coverage
- clean multi-device management with transport fallback

The first release keeps the tool surface read-heavy and safe by default, then adds a guarded write path for raw RouterOS scripts when you explicitly opt a device into write access.

## What makes this better

- Multi-device config with named routers like `home` and `office`
- Transport fallback in order: `api`, `api-ssl`, `ssh`
- Device-scoped tools so the model must choose a target router explicitly
- Guarded write workflow with `plan_script_change` then `apply_script_change`
- Readable JSON outputs instead of transport-specific ad hoc blobs
- Public-repo structure with tests, sample config, and clear client setup

## Current tools

- `get_server_config`
- `list_devices`
- `describe_device`
- `system_info`
- `interfaces`
- `ip_addresses`
- `routes`
- `firewall_filters`
- `nat_rules`
- `dns_settings`
- `dhcp_servers`
- `logs`
- `ping`
- `export_config`
- `run_api_print`
- `plan_script_change`
- `apply_script_change`

## Install

```bash
cd /Users/Drohi/Projects/mikrotik-routeros-mcp
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Configure devices

Copy the sample file and fill in your routers:

```bash
cp devices.yaml.example devices.yaml
```

Example:

```yaml
devices:
  - name: home
    host: 192.168.88.1
    username: admin
    password: change-me
    transport_order:
      - api
      - api-ssl
      - ssh
    allow_writes: false
    tags:
      - home
      - lab

  - name: office
    host: office-router.example.com
    username: admin
    password: change-me
    fallback_ip: 203.0.113.10
    transport_order:
      - api-ssl
      - ssh
    allow_writes: false
    tags:
      - office
      - production
```

By default the server looks for config in this order:

- `MIKROTIK_ROUTEROS_CONFIG`
- `./devices.yaml`
- `./devices.yml`
- `./devices.json`

## Run

```bash
cd /Users/Drohi/Projects/mikrotik-routeros-mcp
MIKROTIK_ROUTEROS_CONFIG=/Users/Drohi/Projects/mikrotik-routeros-mcp/devices.yaml \
.venv/bin/python -m mikrotik_routeros_mcp.server
```

## Claude Desktop

```json
{
    "mcpServers": {
    "mikrotik-routeros": {
      "command": "/Users/Drohi/Projects/mikrotik-routeros-mcp/.venv/bin/python",
      "args": [
        "-m",
        "mikrotik_routeros_mcp.server"
      ],
      "env": {
        "MIKROTIK_ROUTEROS_CONFIG": "/Users/Drohi/Projects/mikrotik-routeros-mcp/devices.yaml"
      }
    }
  }
}
```

## Cursor

```json
{
    "mcpServers": {
    "mikrotik-routeros": {
      "command": "/Users/Drohi/Projects/mikrotik-routeros-mcp/.venv/bin/python",
      "args": [
        "-m",
        "mikrotik_routeros_mcp.server"
      ],
      "env": {
        "MIKROTIK_ROUTEROS_CONFIG": "/Users/Drohi/Projects/mikrotik-routeros-mcp/devices.yaml"
      }
    }
  }
}
```

## Guarded write flow

Write access is blocked unless the target device has `allow_writes: true`.

The intended workflow is:

1. Call `plan_script_change(device, script, reason)`
2. Inspect the returned risk level and approval code
3. Call `apply_script_change(device, script, reason, approval_code)` only if the plan is acceptable

This is intentionally basic in `0.1.0`. It creates a safer MCP workflow than exposing unrestricted raw script execution immediately.

## Notes

- API transports return structured rows when possible.
- SSH fallback is especially useful for config export and environments where API access is limited.
- `run_api_print` is read-only by design. It blocks mutating RouterOS API paths.
- The guarded script tools are the escape hatch until more named write tools are added.

## Next steps

- add address lists, DHCP leases, interfaces, bridges, neighbors, and backups
- add richer per-tool schemas for write operations instead of relying on raw scripts
- add stronger change previews and rollback helpers
- add integration tests against a lab RouterOS instance
