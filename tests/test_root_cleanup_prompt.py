import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path("/Users/duanyongyao/.codex/skills/macos-uninstall-cleanup/scripts")
    / "root_cleanup_prompt.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("root_cleanup_prompt", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RootCleanupPromptTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_build_shell_script_quotes_arguments(self):
        shell_script = self.module.build_shell_script(
            [
                "--remove",
                "/Users/Shared/Battle.net",
                "--forget-pkg",
                "com.vendor.pkg with space",
                "--disable-system",
                "system/com.vendor.helper's label",
            ]
        )

        self.assertIn("python3", shell_script)
        self.assertIn("--remove", shell_script)
        self.assertIn("/Users/Shared/Battle.net", shell_script)
        self.assertIn("'com.vendor.pkg with space'", shell_script)
        self.assertIn("'system/com.vendor.helper'\"'\"'s label'", shell_script)
        self.assertIn("root_cleanup_batch.py", shell_script)

    def test_run_prompt_invokes_osascript_with_admin_privileges(self):
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
        )

        with mock.patch.object(self.module.subprocess, "run", return_value=completed) as run_mock:
            result = self.module.run_prompt(["--remove", "/Users/Shared/Battle.net"])

        self.assertEqual(result.returncode, 0)
        command = run_mock.call_args.args[0]
        self.assertEqual(command[0], "osascript")
        self.assertEqual(command[1], "-e")
        self.assertIn("with administrator privileges", command[2])
        self.assertIn("/Users/Shared/Battle.net", command[2])

    def test_build_osascript_command_escapes_double_quotes(self):
        command = self.module.build_osascript_command(
            ["--disable-system", "system/com.vendor.helper's label"]
        )

        self.assertEqual(command[0], "osascript")
        self.assertIn('\\"', command[2])

    def test_main_returns_osascript_exit_code(self):
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=2,
            stdout="",
            stderr="User canceled.",
        )

        with mock.patch.object(self.module.subprocess, "run", return_value=completed):
            with mock.patch.object(sys, "argv", [str(MODULE_PATH), "--remove", "/Users/Shared/Battle.net"]):
                with mock.patch.object(sys, "stderr") as stderr_mock:
                    code = self.module.main()

        self.assertEqual(code, 2)
        self.assertTrue(stderr_mock.write.called)


if __name__ == "__main__":
    unittest.main()
