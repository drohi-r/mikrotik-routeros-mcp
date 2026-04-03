# AGENTS.md

## Project

- Product: `mikrotik-routeros-mcp`
- Domain: multi-device MikroTik RouterOS management
- Protocols: RouterOS API, SSH fallback
- Main entrypoint:
- `uv run python -m mikrotik_routeros_mcp.server`

## Core Rules

- Preserve safe-by-default behavior for multi-device operations.
- Keep guarded write access explicit.
- Respect transport fallback design; do not break device-level isolation.
- Add tests for behavior changes, especially around writes, device routing, and config parsing.

## Key Commands

```bash
uv sync
uv run python -m pytest -v
uv run python -m mikrotik_routeros_mcp.server
```

## Key Paths

- `src/mikrotik_routeros_mcp/server.py`: MCP server
- `src/mikrotik_routeros_mcp/`: RouterOS logic
- `devices.yaml.example`: device config reference
- `tests/`: verification

## When Editing

- Keep multi-device assumptions explicit and testable.
- Preserve the repo's read-heavy, guarded-write posture unless a task explicitly changes it.
