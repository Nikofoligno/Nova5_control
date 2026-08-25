"""Test del protocollo WebSocket senza richiedere MoveIt avviato."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402
from robot_config import POSES  # noqa: E402


class FakeDriver:
    """Sostituto minimo del driver ROS per validare il confine HTTP/WebSocket."""

    def __init__(self) -> None:
        self.arm_enabled: bool | None = None
        self.errors: list[str] = []

    def set_arm_enabled(self, enabled: bool) -> None:
        self.arm_enabled = enabled

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def jog_joint(self, joint: str, direction: int, step: float) -> None:
        raise AssertionError("Il comando malformato non deve raggiungere il driver.")

    def start_hold(self, command: str, target: str, direction: int, step: float) -> None:
        self.hold = (command, target, direction, step)

    def stop(self, disarm: bool = True) -> None:
        self.stop_disarm = disarm


class FakeRuntime:
    def __init__(self) -> None:
        self.node = FakeDriver()


class CommandProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_runtime = app.runtime
        self.runtime = FakeRuntime()
        app.runtime = self.runtime

    def tearDown(self) -> None:
        app.runtime = self.previous_runtime

    def command(self, payload: dict[str, object]) -> dict[str, object]:
        return asyncio.run(app.handle_command(payload))

    def test_accepts_valid_arm_command(self) -> None:
        self.assertEqual(
            self.command({"command": "arm", "enabled": True}),
            {"type": "ack", "command": "arm"},
        )
        self.assertTrue(self.runtime.node.arm_enabled)

    def test_rejects_non_boolean_safety_commands(self) -> None:
        response = self.command({"command": "arm", "enabled": "false"})
        self.assertEqual(response["type"], "error")
        self.assertEqual(
            response["message"], "Il campo 'enabled' deve essere booleano.",
        )
        self.assertEqual(self.runtime.node.errors, [response["message"]])

    def test_rejects_malformed_numeric_command_without_dropping_protocol(self) -> None:
        response = self.command(
            {"command": "joint_jog", "joint": "joint1", "direction": None, "step": 0.05},
        )
        self.assertEqual(response["type"], "error")
        self.assertTrue(self.runtime.node.errors)

    def test_releasing_hold_stops_motion_without_disarming(self) -> None:
        self.assertEqual(
            self.command({"command": "hold_stop"}),
            {"type": "ack", "command": "hold_stop"},
        )
        self.assertFalse(self.runtime.node.stop_disarm)

    def test_starts_valid_server_side_hold(self) -> None:
        self.assertEqual(
            self.command(
                {
                    "command": "hold_start",
                    "motion": {"command": "joint_jog", "joint": "joint1", "direction": 1, "step": 0.05},
                }
            ),
            {"type": "ack", "command": "hold_start"},
        )
        self.assertEqual(self.runtime.node.hold, ("joint_jog", "joint1", 1, 0.05))

    def test_rejects_malformed_server_side_hold(self) -> None:
        response = self.command(
            {"command": "hold_start", "motion": {"command": "axis_jog", "axis": "x", "direction": True, "step": 0.005}}
        )
        self.assertEqual(response["type"], "error")
        self.assertTrue(self.runtime.node.errors)

    def test_safe_pose_is_available(self) -> None:
        self.assertIn("safe", POSES)
        self.assertEqual(POSES["safe"], POSES["carry"])


if __name__ == "__main__":
    unittest.main()
