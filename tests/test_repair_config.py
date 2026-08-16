import json
import os
import subprocess
import tempfile
import time
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR = ROOT / "bin" / "ai-notify-repair-config"


class RepairConfigTests(unittest.TestCase):
    def make_files(self, directory: str) -> tuple[Path, Path, Path, dict[str, str]]:
        root = Path(directory)
        codex = root / "config.toml"
        claude = root / "settings.json"
        log = root / "repair.log"
        codex.write_text(
            'model = "gpt-test"\n\n[features]\ngoals = true\n',
            encoding="utf-8",
        )
        claude.write_text(
            json.dumps(
                {
                    "env": {"KEEP_ME": "yes"},
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "unrelated-hook"}
                                ]
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["HOME"] = str(root)
        return codex, claude, log, env

    def run_repair(
        self,
        codex: Path,
        claude: Path,
        log: Path,
        env: dict[str, str],
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(REPAIR),
                *extra,
                "--codex-config",
                str(codex),
                "--claude-settings",
                str(claude),
                "--log-file",
                str(log),
            ],
            env=env,
            text=True,
            capture_output=True,
        )

    def test_detects_repairs_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, claude, log, env = self.make_files(directory)
            check = self.run_repair(codex, claude, log, env, "--check")
            self.assertEqual(check.returncode, 1, check.stderr)
            self.assertIn("codex, claude", check.stdout)

            repaired = self.run_repair(codex, claude, log, env)
            self.assertEqual(repaired.returncode, 0, repaired.stderr)

            codex_data = tomllib.loads(codex.read_text(encoding="utf-8"))
            expected_notify = [
                str(Path(directory) / ".local" / "bin" / "ai-notify"),
                "codex",
            ]
            self.assertEqual(codex_data["notify"], expected_notify)
            self.assertTrue(codex_data["features"]["goals"])

            claude_data = json.loads(claude.read_text(encoding="utf-8"))
            self.assertEqual(claude_data["env"]["KEEP_ME"], "yes")
            self.assertEqual(
                claude_data["hooks"]["Stop"][0]["hooks"][0]["command"],
                "unrelated-hook",
            )
            self.assertEqual(
                {entry["matcher"] for entry in claude_data["hooks"]["Notification"]},
                {"agent_needs_input", "elicitation_dialog", "elicitation_url_dialog"},
            )

    def test_second_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, claude, log, env = self.make_files(directory)
            first = self.run_repair(codex, claude, log, env)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = (codex.read_bytes(), claude.read_bytes())
            before_mtime = (codex.stat().st_mtime_ns, claude.stat().st_mtime_ns)

            time.sleep(0.01)
            second = self.run_repair(codex, claude, log, env)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already valid", second.stdout)
            self.assertEqual((codex.read_bytes(), claude.read_bytes()), before)
            self.assertEqual(
                (codex.stat().st_mtime_ns, claude.stat().st_mtime_ns), before_mtime
            )

    def test_invalid_codex_toml_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, claude, log, env = self.make_files(directory)
            codex.write_text('model = "unterminated\n', encoding="utf-8")
            before = codex.read_bytes()

            result = self.run_repair(codex, claude, log, env)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(codex.read_bytes(), before)

    def test_missing_optional_client_configs_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_repair(
                root / "missing-codex.toml",
                root / "missing-claude.json",
                root / "repair.log",
                {**os.environ, "HOME": directory},
                "--check",
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
