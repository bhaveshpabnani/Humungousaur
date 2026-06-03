import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.env import load_dotenv, load_workspace_environment


class EnvTests(unittest.TestCase):
    def test_load_dotenv_loads_simple_values_without_overriding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        "OPENAI_API_KEY=sk-test-local",
                        "QUOTED_VALUE='hello world'",
                        "export LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1",
                        "INVALID LINE",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENAI_API_KEY": "existing"}, clear=True):
                loaded = load_dotenv(env_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "existing")
                self.assertEqual(os.environ["QUOTED_VALUE"], "hello world")
                self.assertEqual(os.environ["LOCAL_LLM_BASE_URL"], "http://127.0.0.1:11434/v1")
                self.assertNotIn("OPENAI_API_KEY", loaded)
                self.assertIn("QUOTED_VALUE", loaded)

    def test_load_workspace_environment_uses_only_workspace_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cwd = root / "cwd"
            workspace = root / "workspace"
            cwd.mkdir()
            workspace.mkdir()
            (cwd / ".env").write_text("OPENAI_API_KEY=sk-cwd-should-not-load\n", encoding="utf-8")
            (workspace / ".env").write_text("LOCAL_LLM_API_KEY=workspace-local\n", encoding="utf-8")
            original_cwd = Path.cwd()
            try:
                os.chdir(cwd)
                with patch.dict(os.environ, {}, clear=True):
                    loaded = load_workspace_environment(workspace)

                    self.assertNotIn("OPENAI_API_KEY", os.environ)
                    self.assertEqual(os.environ["LOCAL_LLM_API_KEY"], "workspace-local")
                    self.assertEqual(loaded, {"LOCAL_LLM_API_KEY": "workspace-local"})
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
