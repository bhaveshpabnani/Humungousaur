import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.design_tools import (
    BrandGuidelinesCreateTool,
    BrandGuidelinesInspectTool,
    ThemePackCreateTool,
    ThemePackInspectTool,
)


class DesignToolTests(unittest.TestCase):
    def test_brand_guidelines_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = BrandGuidelinesCreateTool().execute(
                {
                    "filename": "brand.md",
                    "brand_name": "Humungousaur",
                    "status": "proposed",
                    "colors": [{"name": "ink", "value": "#1f2933", "usage": "primary text", "accessibility": "use on light surfaces"}],
                    "typography": [{"role": "body", "family": "Segoe UI", "size": "14px", "weight": "400"}],
                    "tone": ["calm", "direct"],
                    "accessibility_notes": ["Avoid low contrast combinations."],
                    "source_refs": ["fixture"],
                    "reason": "Verify native brand guideline artifact.",
                },
                config,
            )
            inspected = BrandGuidelinesInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["status"], "proposed")
        self.assertEqual(created.output["color_count"], 1)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["accessibility_note_count"], 1)
        self.assertIn("not official", metadata["safety_note"])

    def test_theme_pack_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = ThemePackCreateTool().execute(
                {
                    "filename": "theme.md",
                    "theme_name": "Clear Work",
                    "mode": "light",
                    "palette": [{"name": "surface", "value": "#f8fafc", "usage": "page background"}, {"name": "ink", "value": "#111827", "usage": "text"}],
                    "tokens": {"radius-card": "8px", "space-3": "12px"},
                    "typography": {"body": "Segoe UI 14px"},
                    "spacing": {"panel": "16px"},
                    "radii": {"card": "8px"},
                    "component_states": [{"component": "button", "state": "hover", "token": "color-ink", "notes": "keep contrast"}],
                    "contrast_checks": [{"foreground": "#111827", "background": "#f8fafc", "ratio": "15:1", "status": "pass"}],
                    "reason": "Verify native theme pack artifact.",
                },
                config,
            )
            inspected = ThemePackInspectTool().execute({"path": created.output["path"]}, config)
            css_exists = Path(created.output["css_path"]).exists()

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertTrue(css_exists)
        self.assertGreaterEqual(created.output["token_count"], 2)
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["contrast_check_count"], 1)

    def test_theme_pack_requires_theme_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = ThemePackCreateTool().execute({"reason": "Verify validation."}, config)

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("Theme name", result.summary)


if __name__ == "__main__":
    unittest.main()
