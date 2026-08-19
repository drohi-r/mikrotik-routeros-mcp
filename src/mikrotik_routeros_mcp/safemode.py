from __future__ import annotations

import time
from typing import Any, Callable, Protocol

CTRL_X = b"\x18"
# RouterOS v7 console: prompt gains "<SAFE> " once safe mode is taken, and the
# release path prints "Safe Mode released". Login must use the "+ct" console
# options or RouterOS blocks on terminal-capability negotiation.
SAFE_PROMPT_MARKER = "<SAFE> "
# the trailing "Safe Mode released" line can arrive after a pause (and after the
# prompt), so the immediate release acknowledgement is the reliable marker
SAFE_MODE_RELEASED = "Releasing Safe Mode... Success!"
_PROMPT_ENDINGS = ("> ", "<SAFE> ")


class SafeModeError(RuntimeError):
    pass


class ConsoleChannel(Protocol):
    def send(self, data: bytes) -> int: ...

    def recv(self, size: int) -> bytes: ...

    def close(self) -> None: ...

    def settimeout(self, timeout: float) -> None: ...


class SafeModeSession:
    """Drives a RouterOS console in Safe Mode over a persistent channel.

    RouterOS reverts every change made inside Safe Mode if the session ends
    without a clean release, so abandon() (or a dropped connection) is the
    rollback mechanism.
    """

    def __init__(self, channel: ConsoleChannel, *, timeout_seconds: float = 30.0) -> None:
        self.channel = channel
        self.timeout_seconds = timeout_seconds
        self.in_safe_mode = False
        self.channel.settimeout(0.25)

    def _drain(self) -> None:
        while True:
            try:
                if not self.channel.recv(4096):
                    return
            except (TimeoutError, OSError):
                return

    def _read_until(self, marker: str, *, failure_description: str) -> str:
        buffer = ""
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                chunk = self.channel.recv(4096)
            except (TimeoutError, OSError):
                chunk = b""
            if chunk:
                buffer += chunk.decode("utf-8", errors="replace")
                if marker in buffer:
                    return buffer
            elif buffer.endswith(_PROMPT_ENDINGS):
                break
            else:
                time.sleep(0.05)
        raise SafeModeError(f"{failure_description} (marker '{marker}' not seen).")

    def enter(self) -> None:
        self._drain()
        self.channel.send(CTRL_X)
        self._read_until(SAFE_PROMPT_MARKER, failure_description="Router did not enter Safe Mode")
        self.in_safe_mode = True

    def run(self, command: str) -> str:
        if not self.in_safe_mode:
            raise SafeModeError("Session is not in Safe Mode; call enter() before run().")
        self._drain()
        self.channel.send(command.encode("utf-8") + b"\r")
        return self._read_until(SAFE_PROMPT_MARKER, failure_description=f"No prompt after command '{command}'")

    def commit(self) -> None:
        if not self.in_safe_mode:
            raise SafeModeError("Session is not in Safe Mode; nothing to commit.")
        self._drain()
        self.channel.send(CTRL_X)
        try:
            self._read_until(SAFE_MODE_RELEASED, failure_description="Router did not confirm Safe Mode release")
        except SafeModeError:
            self.abandon()
            raise
        self.in_safe_mode = False
        self.channel.close()

    def abandon(self) -> None:
        self.in_safe_mode = False
        try:
            self.channel.close()
        except OSError:
            pass


def safe_apply(
    *,
    session: SafeModeSession,
    script: str,
    take_snapshot: Callable[[], str],
    check_health: Callable[[], bool],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "snapshot_id": None,
        "output": "",
        "committed": False,
        "health": None,
        "error": None,
    }
    try:
        result["snapshot_id"] = take_snapshot()
    except Exception as exc:
        result["error"] = f"snapshot failed, no changes attempted: {exc}"
        return result
    try:
        session.enter()
        result["output"] = session.run(script)
        result["health"] = check_health()
        if not result["health"]:
            session.abandon()
            result["error"] = "health check failed; Safe Mode session abandoned, router reverted the change."
            return result
        session.commit()
        result["committed"] = True
        return result
    except Exception as exc:
        session.abandon()
        result["error"] = str(exc)
        return result
