import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = REPO_ROOT / "browser_extensions" / "humungousaur_collector"
BROWSERS = ("chrome", "edge", "brave", "firefox", "safari")


class BrowserExtensionCollectorTests(unittest.TestCase):
    def test_build_creates_loadable_extension_directories_for_all_browsers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir)
            result = subprocess.run(
                ["python3", str(EXTENSION_ROOT / "scripts" / "build.py"), "--output", str(output)],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            built = {Path(line).resolve() for line in result.stdout.splitlines()}
            for browser in BROWSERS:
                directory = output / browser
                self.assertIn(directory.resolve(), built)
                self.assertTrue((directory / "manifest.json").exists())
                self.assertTrue((directory / "src" / "background.js").exists())
                self.assertTrue((directory / "src" / "content.js").exists())
                self.assertTrue((directory / "src" / "options.html").exists())

    def test_manifests_cover_browser_activity_api_surfaces(self) -> None:
        for browser in BROWSERS:
            manifest = json.loads((EXTENSION_ROOT / f"manifest.{browser}.json").read_text(encoding="utf-8"))
            permissions = set(manifest.get("permissions", []))
            host_permissions = set(manifest.get("host_permissions", [])) | permissions

            self.assertIn("tabs", permissions)
            self.assertIn("storage", permissions)
            self.assertIn("webNavigation", permissions)
            self.assertIn("downloads", permissions)
            self.assertIn("http://127.0.0.1/*", host_permissions)
            self.assertIn("http://localhost/*", host_permissions)
            self.assertTrue(manifest.get("content_scripts"))
            self.assertIn("commands", manifest)
            if browser in {"chrome", "edge", "brave"}:
                self.assertEqual(manifest["manifest_version"], 3)
                self.assertIn("tabGroups", permissions)
                self.assertIn("service_worker", manifest["background"])
            else:
                self.assertEqual(manifest["manifest_version"], 2)
                self.assertIn("scripts", manifest["background"])

    def test_emitter_sources_cover_p0_browser_events(self) -> None:
        source = "\n".join(
            [
                (EXTENSION_ROOT / "src" / "background.js").read_text(encoding="utf-8"),
                (EXTENSION_ROOT / "src" / "content.js").read_text(encoding="utf-8"),
            ]
        )
        required_event_types = {
            "tab_opened",
            "tab_closed",
            "tab_switched",
            "url_changed",
            "web_app_opened",
            "form_submitted",
            "file_uploaded",
            "download_started",
            "download_completed",
            "page_error",
            "extension_clicked",
            "tab_group_created",
            "profile_switched",
            "reader_mode_enabled",
            "find_in_page",
            "zoom_changed",
            "page_muted",
            "picture_in_picture_started",
            "translation_accepted",
        }

        missing = sorted(event_type for event_type in required_event_types if event_type not in source)
        self.assertEqual(missing, [])

    def test_content_script_keeps_raw_content_out_of_emitted_payloads(self) -> None:
        source = (EXTENSION_ROOT / "src" / "content.js").read_text(encoding="utf-8")

        self.assertNotIn(".value", source)
        self.assertNotIn("innerText", source)
        self.assertNotIn("textContent", source)
        self.assertNotIn("document.body", source)
        self.assertIn("form_values_omitted", source)
        self.assertIn("filenames_omitted", source)
        self.assertIn("selected_text_omitted", source)


if __name__ == "__main__":
    unittest.main()
