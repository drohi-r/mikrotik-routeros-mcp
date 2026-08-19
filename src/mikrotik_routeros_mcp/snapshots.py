from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SNAPSHOT_ROOT = Path.home() / ".mikrotik-mcp" / "snapshots"


@dataclass(slots=True)
class SnapshotInfo:
    id: str
    device: str
    path: Path
    created: str
    size_bytes: int


class SnapshotStore:
    def __init__(self, root: Path = DEFAULT_SNAPSHOT_ROOT) -> None:
        self.root = root

    def _device_dir(self, device: str) -> Path:
        return self.root / device

    def _info(self, device: str, path: Path) -> SnapshotInfo:
        stat = path.stat()
        return SnapshotInfo(
            id=path.stem,
            device=device,
            path=path,
            created=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            size_bytes=stat.st_size,
        )

    def save(self, device: str, export_text: str) -> SnapshotInfo:
        device_dir = self._device_dir(device)
        device_dir.mkdir(parents=True, exist_ok=True)
        base_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_id = base_id
        suffix = 1
        while (device_dir / f"{snapshot_id}.rsc").exists():
            snapshot_id = f"{base_id}-{suffix}"
            suffix += 1
        path = device_dir / f"{snapshot_id}.rsc"
        path.write_text(export_text)
        return self._info(device, path)

    def list_snapshots(self, device: str) -> list[SnapshotInfo]:
        device_dir = self._device_dir(device)
        if not device_dir.is_dir():
            return []
        infos = [self._info(device, path) for path in device_dir.glob("*.rsc")]
        return sorted(infos, key=lambda info: info.id, reverse=True)

    def _read(self, device: str, snapshot_id: str) -> str:
        path = self._device_dir(device) / f"{snapshot_id}.rsc"
        if not path.is_file():
            raise KeyError(f"Unknown snapshot '{snapshot_id}' for device '{device}'.")
        return path.read_text()

    def diff(self, device: str, old_id: str, new_id: str) -> str:
        old_lines = self._read(device, old_id).splitlines(keepends=True)
        new_lines = self._read(device, new_id).splitlines(keepends=True)
        return "".join(difflib.unified_diff(old_lines, new_lines, fromfile=old_id, tofile=new_id))
