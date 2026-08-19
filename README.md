<p align="center">
  <img src="assets/banner.svg" alt="MikroTik RouterOS MCP" width="100%">
</p>

# MikroTik RouterOS MCP

<p align="center">
  <a href="https://github.com/drohi-r/mikrotik-routeros-mcp/actions/workflows/ci.yml"><img src="https://github.com/drohi-r/mikrotik-routeros-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/drohi-r/mikrotik-routeros-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-orange?style=for-the-badge" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/MCP_Tools-26-2196F3?style=for-the-badge" alt="26 MCP Tools">
</p>

An MCP server for [MikroTik RouterOS](https://mikrotik.com/software) with a lightweight web dashboard for multi-router management. Exposes 26 MCP tools covering transport fallback (API → API-SSL → SSH), read-heavy network inspection, and guarded write access, while the bundled dashboard provides a simple REST-backed UI for viewing routers and common network state.

## Quick start

```bash
git clone https://github.com/drohi-r/mikrotik-routeros-mcp && cd mikrotik-routeros-mcp
uv sync

# Configure devices
cp devices.yaml.example devices.yaml   # then edit with your router details

# Run the MCP server
uv run python -m mikrotik_routeros_mcp.server

# Or run the web dashboard
uv run python -m mikrotik_routeros_mcp.dashboard --host 0.0.0.0 --port 8080
```

The server looks for config in this order: `MIKROTIK_ROUTEROS_CONFIG` env var → `./devices.yaml` → `./devices.yml` → `./devices.json`.

## Architecture

```mermaid
graph TD
    A["MikroTik RouterOS MCP Server<br/><code>mikrotik_routeros_mcp</code><br/>26 tools · safe-mode writes"] --> B
    B["Transport Layer<br/>Fallback: API → API-SSL → SSH"] --> C
    C["RouterOS Devices<br/>Named targets from devices.yaml"]

    D["Multi-Device Config<br/>Named routers · tags · per-device write control"] -.-> A
    E["Safe-Mode Write Engine<br/>snapshot → apply → health check → commit/revert"] -.-> A
    F["SSH Fallback<br/>Config export · limited-API environments"] -.-> B

    style A fill:#1a1a2e,stroke:#2196F3,color:#fff
    style B fill:#1a1a2e,stroke:#2196F3,color:#fff
    style C fill:#1a1a2e,stroke:#0f3460,color:#fff
    style D fill:#0f3460,stroke:#0f3460,color:#fff
    style E fill:#0f3460,stroke:#0f3460,color:#fff
    style F fill:#0f3460,stroke:#0f3460,color:#fff
```

## Configuration

Device config example:

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

## Tools

### Server and discovery

| Tool | What it does |
|------|-------------|
| `get_server_config` | Return current MCP server configuration and safety settings |
| `list_devices` | List all configured RouterOS devices |
| `describe_device` | Return detailed info for a named device |

### System and network reads

| Tool | What it does |
|------|-------------|
| `system_info` | Return system identity, version, uptime, and hardware info |
| `interfaces` | List all network interfaces with status |
| `ip_addresses` | List IP addresses assigned to interfaces |
| `routes` | List the routing table |
| `firewall_filters` | List firewall filter rules |
| `nat_rules` | List NAT rules |
| `dns_settings` | Return DNS configuration |
| `dhcp_servers` | List DHCP server instances |
| `dhcp_leases` | List DHCP leases |
| `address_lists` | List firewall address list entries |
| `bridges` | List bridge interfaces |
| `bridge_ports` | List bridge port memberships |
| `neighbors` | List discovered network neighbors |
| `wireguard_interfaces` | List WireGuard interfaces |
| `wireguard_peers` | List WireGuard peers |
| `logs` | Retrieve system log entries |
| `ping` | Ping a target from a device |
| `export_config` | Export device configuration |
| `run_api_print` | Read-only API print for any RouterOS path |

### Guarded writes

| Tool | What it does |
|------|-------------|
| `plan_script_change` | Preview a RouterOS script change with risk assessment |
| `apply_script_change` | Apply a planned change inside a Safe Mode session with snapshot and auto-rollback |
| `list_snapshots` | List config snapshots taken before writes, newest first |
| `diff_snapshots` | Unified diff between two config snapshots of a device |

Write access is blocked unless the target device has `allow_writes: true`. The intended workflow is: `plan_script_change` → inspect risk level and approval code → `apply_script_change` only if the plan is acceptable.

### Safe Mode writes

Every `apply_script_change` runs a lockout-proof pipeline — there is no unprotected write path:

1. **Snapshot** — the full config is exported to `~/.mikrotik-mcp/snapshots/<device>/<timestamp>.rsc` before anything is sent.
2. **Safe Mode** — the change is applied inside a RouterOS [Safe Mode](https://help.mikrotik.com/docs/display/ROS/Console#Console-SafeMode) console session over a persistent SSH PTY. Safe Mode is console-only (neither the binary API nor REST expose it), which is why this engine drives a real terminal.
3. **Health check** — after applying, the router must still answer over a *separate* SSH connection.
4. **Commit or revert** — healthy: Safe Mode is released and the change is kept. Unhealthy, timed out, or the session drops (including because the change itself cut our connectivity): **the router reverts the change itself**. That is RouterOS's own rollback mechanism, not a best-effort undo script.

Devices without `ssh` in `transport_order` fail closed — writes are refused rather than applied unprotected. The health check is deliberately minimal (management path answers); it catches lockouts, not subtle misconfiguration — review `diff_snapshots` output after any change that matters.

## Claude Desktop

```json
{
  "mcpServers": {
    "mikrotik-routeros": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mikrotik-routeros-mcp", "python", "-m", "mikrotik_routeros_mcp.server"],
      "env": {
        "MIKROTIK_ROUTEROS_CONFIG": "/path/to/devices.yaml"
      }
    }
  }
}
```

## VS Code / Cursor

```json
{
  "servers": {
    "mikrotik-routeros": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mikrotik-routeros-mcp", "python", "-m", "mikrotik_routeros_mcp.server"],
      "env": {
        "MIKROTIK_ROUTEROS_CONFIG": "/path/to/devices.yaml"
      }
    }
  }
}
```

## Codex

Create a `codex.json` MCP config file:

```json
{
  "mcpServers": {
    "mikrotik-routeros": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mikrotik-routeros-mcp", "python", "-m", "mikrotik_routeros_mcp.server"],
      "env": {
        "MIKROTIK_ROUTEROS_CONFIG": "/path/to/devices.yaml"
      }
    }
  }
}
```

Then run Codex with:

```bash
codex --mcp-config codex.json
```

## Production safety

- **Device-scoped targeting** — the model must choose a named target router explicitly. No ambient "default device" behavior.
- **Write gating** — write access is blocked per-device unless `allow_writes: true` is set in config. Read tools are always available.
- **Guarded write flow** — `plan_script_change` returns a risk assessment and approval code. `apply_script_change` requires that approval code to proceed.
- **Transport fallback** — attempts `api`, then `api-ssl`, then `ssh` in order, so the server connects via the best available transport without manual switching.
- **Read-only API guard** — `run_api_print` blocks mutating RouterOS API paths by design.
- **Input validation** — all tools validate parameters before any API call is made. Invalid inputs return structured JSON errors, never raw exceptions.

## Development

```bash
uv sync
uv run python -m pytest -v
```

## License

[Apache 2.0](LICENSE)
