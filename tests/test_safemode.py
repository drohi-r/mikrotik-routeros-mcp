from __future__ import annotations

import unittest

from mikrotik_routeros_mcp.safemode import SafeModeError, SafeModeSession, safe_apply

CTRL_X = b"\x18"
PROMPT = "[admin@office] > "
SAFE_PROMPT = "[admin@office] <SAFE> "


class FakeChannel:
    """Scripted RouterOS console: maps received input to canned output."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.closed = False
        self._pending = ""
        self.responses: dict[bytes, str] = {
            CTRL_X: "\r\nTaking Safe Mode session... Success!\r\n" + SAFE_PROMPT,
        }
        self.release_response = "\r\nReleasing Safe Mode... Success!\r\n" + PROMPT + "\rSafe Mode released\r\n" + PROMPT

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def send(self, data: bytes) -> int:
        self.sent.append(data)
        if data == CTRL_X and len([item for item in self.sent if item == CTRL_X]) > 1:
            self._pending += self.release_response
        elif data in self.responses:
            self._pending += self.responses[data]
        elif data.endswith(b"\r"):
            command = data.rstrip(b"\r").decode()
            self._pending += f"{command}\r\nok-output\r\n{SAFE_PROMPT}"
        return len(data)

    def recv(self, size: int) -> bytes:
        if not self._pending:
            raise TimeoutError("no data")
        chunk, self._pending = self._pending[:size], self._pending[size:]
        return chunk.encode()

    def close(self) -> None:
        self.closed = True


class SafeModeSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.channel = FakeChannel()
        self.channel._pending = PROMPT  # login banner already consumed
        self.session = SafeModeSession(self.channel, timeout_seconds=1.0)

    def test_enter_sends_ctrl_x_and_detects_safe_mode(self) -> None:
        self.session.enter()

        self.assertIn(CTRL_X, self.channel.sent)
        self.assertTrue(self.session.in_safe_mode)

    def test_enter_raises_when_safe_mode_not_taken(self) -> None:
        self.channel.responses[CTRL_X] = "\r\nTaking Safe Mode session... Failure!\r\n" + PROMPT  # refused

        with self.assertRaises(SafeModeError):
            self.session.enter()

    def test_run_returns_command_output(self) -> None:
        self.session.enter()

        output = self.session.run("/ip dns set servers=9.9.9.9")

        self.assertIn("ok-output", output)

    def test_run_before_enter_raises(self) -> None:
        with self.assertRaises(SafeModeError):
            self.session.run("/ip dns print")

    def test_commit_releases_safe_mode_keeping_changes(self) -> None:
        self.session.enter()

        self.session.commit()

        self.assertEqual(self.channel.sent.count(CTRL_X), 2)
        self.assertFalse(self.session.in_safe_mode)
        self.assertTrue(self.channel.closed)

    def test_commit_raises_if_release_not_confirmed(self) -> None:
        self.session.enter()
        self.channel.release_response = "\r\n" + SAFE_PROMPT  # release never acknowledged

        with self.assertRaises(SafeModeError):
            self.session.commit()

    def test_commit_confirms_release_even_when_prompt_precedes_banner(self) -> None:
        # live RouterOS v7 emits: "Releasing Safe Mode... Success!" -> prompt ->
        # (pause) -> "Safe Mode released"; the pause must not fail the commit
        self.session.enter()
        self.channel.release_response = "\r\nReleasing Safe Mode... Success!\r\n" + PROMPT

        self.session.commit()

        self.assertFalse(self.session.in_safe_mode)
        self.assertTrue(self.channel.closed)

    def test_abandon_closes_channel_without_second_ctrl_x(self) -> None:
        self.session.enter()

        self.session.abandon()

        self.assertEqual(self.channel.sent.count(CTRL_X), 1)
        self.assertTrue(self.channel.closed)
        self.assertFalse(self.session.in_safe_mode)


class SafeApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.channel = FakeChannel()
        self.channel._pending = PROMPT
        self.session = SafeModeSession(self.channel, timeout_seconds=1.0)
        self.saved: list[str] = []

    def _snapshot(self) -> str:
        self.saved.append("export-taken")
        return "snap-001"

    def test_healthy_apply_snapshots_then_commits(self) -> None:
        result = safe_apply(
            session=self.session,
            script="/ip dns set servers=9.9.9.9",
            take_snapshot=self._snapshot,
            check_health=lambda: True,
        )

        self.assertTrue(result["committed"])
        self.assertEqual(result["snapshot_id"], "snap-001")
        self.assertEqual(self.saved, ["export-taken"])
        self.assertEqual(self.channel.sent.count(CTRL_X), 2)

    def test_unhealthy_apply_abandons_and_reports_reverted(self) -> None:
        result = safe_apply(
            session=self.session,
            script="/ip dns set servers=9.9.9.9",
            take_snapshot=self._snapshot,
            check_health=lambda: False,
        )

        self.assertFalse(result["committed"])
        self.assertIn("health", result["error"].lower())
        self.assertEqual(self.channel.sent.count(CTRL_X), 1)
        self.assertTrue(self.channel.closed)

    def test_exception_during_apply_abandons(self) -> None:
        def broken_health() -> bool:
            raise RuntimeError("probe exploded")

        result = safe_apply(
            session=self.session,
            script="/ip dns set servers=9.9.9.9",
            take_snapshot=self._snapshot,
            check_health=broken_health,
        )

        self.assertFalse(result["committed"])
        self.assertIn("probe exploded", result["error"])
        self.assertTrue(self.channel.closed)

    def test_snapshot_failure_stops_before_any_write(self) -> None:
        def failing_snapshot() -> str:
            raise RuntimeError("export failed")

        result = safe_apply(
            session=self.session,
            script="/ip dns set servers=9.9.9.9",
            take_snapshot=failing_snapshot,
            check_health=lambda: True,
        )

        self.assertFalse(result["committed"])
        self.assertEqual(self.channel.sent, [])  # nothing reached the router


if __name__ == "__main__":
    unittest.main()
