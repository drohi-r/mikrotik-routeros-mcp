# Safe-Mode Write Engine + Snapshots (v0.2)

**Date:** 2026-08-20
**Status:** Approved

## Goal

Make every write lockout-proof: snapshot first, apply inside a RouterOS Safe Mode
session, health-check, then commit. If the session drops or the health check fails,
the router itself reverts the change. This is the differentiator no other RouterOS
MCP has, because Safe Mode is console-only (not exposed via the binary or REST API)
and requires a persistent SSH PTY.

## Scope

In: safe-mode session machinery, pre-write export snapshots, snapshot list/diff
tools, upgraded `apply_script_change` pipeline.
Out (later versions): policy tiers, custom health probes, binary backups, drift
detection, UI changes, fleet bulk writes, CHR-based CI integration tests.

## Design

### `snapshots.py` — SnapshotStore

- Root: `~/.mikrotik-mcp/snapshots/<device>/<id>.rsc` (root overridable for tests).
- `save(device, export_text) -> SnapshotInfo` — id is a UTC timestamp
  (`YYYYMMDDTHHMMSSZ`, suffixed on collision).
- `list_snapshots(device) -> list[SnapshotInfo]` — newest first.
- `diff(device, old_id, new_id) -> str` — unified diff of the two exports.
- `SnapshotInfo`: id, device, path, created (iso), size_bytes.

### `safemode.py` — SafeModeSession + pipeline

`SafeModeSession` drives a RouterOS console over a persistent channel (paramiko
`invoke_shell` in production; injected fake in tests). RouterOS semantics:

- Ctrl-X enters Safe Mode (`[Safe Mode taken]`); prompt gains `<SAFE>`.
- Changes made while in Safe Mode are reverted by the router if the session ends
  abnormally (connection loss / Ctrl-D).
- Ctrl-X again releases Safe Mode **keeping** the changes.

API: `enter()`, `run(command) -> str`, `commit()`, `abandon()`. All reads are
bounded by a deadline; a timeout never commits — it abandons. Construction takes a
channel-like object (`send`, `recv`, `close`, `settimeout`) so the state machine is
unit-testable without a router.

`safe_apply(...)` pipeline (pure orchestration, dependencies injected):

1. export config → `SnapshotStore.save`
2. `session.enter()`
3. `session.run(script)`
4. health check (callable; production = `:put "mcp-ok"` over a *separate* SSH
   exec connection)
5. healthy → `session.commit()`; unhealthy or any exception → `session.abandon()`
   and report `reverted` with the failure reason.

Result dict: `snapshot_id`, `output`, `committed` (bool), `health`, `error`.

### Server wiring

- `apply_script_change` keeps its exact signature and the existing
  plan → approval-code gate, but now runs the safe_apply pipeline instead of a
  bare `run_script`. Devices without SSH in `transport_order` fail closed with a
  clear message — no silent fallback to unprotected writes.
- New tools: `list_snapshots(device)`, `diff_snapshots(device, old_id, new_id)`.
- `allow_writes` stays a boolean; no policy changes.

### Testing

- `tests/test_snapshots.py` — save/list/diff against a temp dir.
- `tests/test_safemode.py` — FakeChannel scripted with router banners/prompts:
  enter, run, commit, abandon, timeout-never-commits, and pipeline behavior
  (healthy → commit, unhealthy → abandon, snapshot always taken first).
- No live-router tests in this version.

## Non-goals / honesty notes

The health check is minimal (management path still answers). It catches lockouts,
not subtle breakage. README must state exactly that.
