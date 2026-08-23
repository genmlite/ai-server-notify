import io
import json
import os
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NOTIFIER = ROOT / "bin" / "ai-notify"
NOTIFY_RUN = ROOT / "bin" / "notify-run"
MODULE = runpy.run_path(str(NOTIFIER), run_name="ai_notify_test")


class DescribeTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "server_url": "https://ntfy.invalid",
            "topic": "test-topic",
            "host_label": "test-host",
        }

    def describe_stdin(self, source, payload):
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            return MODULE["describe"](source, [], self.config)

    def assert_description(self, description):
        title, message, priority, tags = description
        self.assertTrue(title)
        self.assertIn("Host: test-host", message)
        self.assertIn(priority, range(1, 6))
        self.assertTrue(tags)
        self.assertNotIn("secret prompt", message)

    def test_codex_turn(self):
        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "cwd": "/srv/demo",
                "thread-id": "1234567890",
                "last-assistant-message": "secret prompt",
            }
        )
        description = MODULE["describe"]("codex", [payload], self.config)
        self.assert_description(description)
        self.assertIn("Session: 12345678", description[1])

    def test_codex_subagent_is_silent(self):
        payload = {
            "type": "agent-turn-complete",
            "cwd": "/srv/demo",
            "thread-id": "child1234",
            "parent-thread-id": "parent1234",
        }
        with self.assertRaises(SystemExit):
            MODULE["describe"]("codex", [json.dumps(payload)], self.config)

    def test_malformed_subagent_marker_does_not_crash(self):
        description = MODULE["describe"](
            "codex",
            [json.dumps({"type": "agent-turn-complete", "subagent": {"unknown": True}})],
            self.config,
        )
        self.assertEqual(description[0], "Codex finished a turn")

    def test_opencode_events(self):
        for event_type, expected in (
            ("session.idle", "OpenCode session paused"),
            ("session.deleted", "OpenCode session ended"),
            ("permission.asked", "OpenCode is waiting for permission"),
            ("question.asked", "OpenCode needs your input"),
        ):
            with self.subTest(event_type=event_type):
                description = MODULE["describe"](
                    "opencode",
                    [
                        json.dumps(
                            {
                                "event_type": event_type,
                                "session_id": "opencode1234",
                                "session": {
                                    "id": "opencode1234",
                                    "directory": "/srv/demo",
                                    "title": "Smoke",
                                },
                                "questions": [{"question": "Pick one"}],
                            }
                        )
                    ],
                    self.config,
                )
                self.assertEqual(description[0], expected)

    def test_opencode_subagent_is_silent(self):
        with self.assertRaises(SystemExit):
            MODULE["describe"](
                "opencode",
                [
                    json.dumps(
                        {
                            "event_type": "session.idle",
                            "session": {"id": "child", "parentID": "parent"},
                        }
                    )
                ],
                self.config,
            )

    def test_claude_stop(self):
        description = self.describe_stdin(
            "claude-stop",
            {
                "cwd": "/srv/demo",
                "session_id": "abcdefghij",
                "last_assistant_message": "secret prompt",
                "background_tasks": [],
                "session_crons": [],
            },
        )
        self.assert_description(description)
        self.assertEqual(description[0], "Claude finished a turn")

    def test_claude_subagent_stop_is_silent(self):
        with patch(
            "sys.stdin",
            io.StringIO(json.dumps({"cwd": "/srv/demo", "agent_id": "child-1"})),
        ):
            with self.assertRaises(SystemExit):
                MODULE["describe"]("claude-stop", [], self.config)

    def test_claude_background_work(self):
        description = self.describe_stdin(
            "claude-stop",
            {"cwd": "/srv/demo", "background_tasks": [{"id": "1"}]},
        )
        self.assert_description(description)
        self.assertIn("background work", description[0])

    def test_claude_failure(self):
        description = self.describe_stdin(
            "claude-failure", {"cwd": "/srv/demo", "error": "rate_limit"}
        )
        self.assert_description(description)
        self.assertEqual(description[2], 5)
        self.assertIn("rate_limit", description[1])

    def test_permission_and_input_events(self):
        for source, payload in (
            ("claude-permission", {"cwd": "/srv/demo", "tool_name": "Bash"}),
            (
                "claude-needs-input",
                {"cwd": "/srv/demo", "notification_type": "agent_needs_input"},
            ),
            (
                "claude-session-end",
                {"cwd": "/srv/demo", "reason": "prompt_input_exit"},
            ),
        ):
            with self.subTest(source=source):
                self.assert_description(self.describe_stdin(source, payload))

    def test_task_statuses(self):
        for status, exit_code in (("success", "0"), ("failure", "7"), ("interrupted", "130")):
            with self.subTest(status=status):
                description = MODULE["describe"](
                    "task", [status, "smoke", exit_code, "2"], self.config
                )
                self.assert_description(description)


class CliTests(unittest.TestCase):
    def make_config(self, directory):
        config = Path(directory) / "config.json"
        config.write_text(
            json.dumps(
                {
                    "server_url": "https://ntfy.invalid",
                    "topic": "test-topic",
                    "host_label": "test-host",
                    "token": "",
                }
            ),
            encoding="utf-8",
        )
        return config

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(
                {
                    "AI_NOTIFY_CONFIG": str(self.make_config(directory)),
                    "AI_NOTIFY_LOG": str(Path(directory) / "notify.log"),
                    "AI_NOTIFY_DRY_RUN": "1",
                }
            )
            result = subprocess.run(
                [str(NOTIFIER), "test"], env=env, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("notification sent", result.stdout)

    def test_notify_run_preserves_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(
                {
                    "AI_NOTIFY_BIN": str(NOTIFIER),
                    "AI_NOTIFY_CONFIG": str(self.make_config(directory)),
                    "AI_NOTIFY_LOG": str(Path(directory) / "notify.log"),
                    "AI_NOTIFY_DRY_RUN": "1",
                }
            )
            result = subprocess.run(
                [str(NOTIFY_RUN), "--name", "failure-smoke", "--", "bash", "-lc", "exit 7"],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 7)


if __name__ == "__main__":
    unittest.main()
