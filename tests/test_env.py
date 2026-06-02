import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humungousaur.env import load_dotenv


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


if __name__ == "__main__":
    unittest.main()
