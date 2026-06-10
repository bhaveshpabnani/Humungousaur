from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "script/verify_release_readiness.py"
COLLECT_SCRIPT_PATH = ROOT / "script/collect_release_artifacts.py"
REPORT_SCRIPT_PATH = ROOT / "script/generate_release_report.py"
VERIFY_REPORT_SCRIPT_PATH = ROOT / "script/verify_release_report.py"
PUBLICATION_SCRIPT_PATH = ROOT / "script/verify_publication_state.py"
HYGIENE_SCRIPT_PATH = ROOT / "script/verify_open_source_hygiene.py"
REAL_WORLD_SMOKE_PATH = ROOT / "scripts/smoke_real_world_tasks.py"
MACOS_VERIFY_PATH = ROOT / "script/verify_macos_package.sh"
WINDOWS_VERIFY_PATH = ROOT / "script/verify_windows_package.ps1"
MACOS_PACKAGE_PATH = ROOT / "script/package_macos.sh"
WINDOWS_PACKAGE_PATH = ROOT / "script/package_windows.ps1"
CI_WORKFLOW_PATH = ROOT / ".github/workflows/ci.yml"
RELEASE_WORKFLOW_PATH = ROOT / ".github/workflows/release.yml"


def load_release_readiness_module():
    spec = importlib.util.spec_from_file_location("verify_release_readiness", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verify_release_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_collect_release_artifacts_module():
    spec = importlib.util.spec_from_file_location("collect_release_artifacts", COLLECT_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load collect_release_artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_release_report_module():
    spec = importlib.util.spec_from_file_location("generate_release_report", REPORT_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load generate_release_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_verify_release_report_module():
    spec = importlib.util.spec_from_file_location("verify_release_report", VERIFY_REPORT_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verify_release_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_publication_state_module():
    spec = importlib.util.spec_from_file_location("verify_publication_state", PUBLICATION_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verify_publication_state.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_open_source_hygiene_module():
    spec = importlib.util.spec_from_file_location("verify_open_source_hygiene", HYGIENE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verify_open_source_hygiene.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_real_world_smoke_module():
    spec = importlib.util.spec_from_file_location("smoke_real_world_tasks", REAL_WORLD_SMOKE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load smoke_real_world_tasks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_workflow_runs_backend_regression_before_packaging(self) -> None:
        workflow_text = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")

        for expected in [
            'python -m pip install -e ".[browser,pdf,ocr,office,test]"',
            "python -m py_compile",
            "verify_desktop_runtime_smoke.py",
            "collect_release_artifacts.py",
            "verify_publication_state.py",
            "Verify desktop runtime smoke",
            "publish_release",
            "release_tag",
            "Validate manual release dispatch",
            "release_tag is required when publish_release is true",
            "git fetch --tags --force",
            "git rev-parse -q --verify",
            "git checkout --detach",
            "fetch-depth: 0",
            "contents: read",
            "HUMUNGOUSAUR_RELEASE_TAG",
            "HUMUNGOUSAUR_RELEASE_BUILD",
            "python3 ./script/verify_release_readiness.py --skip-website",
            "python -m unittest discover -v",
            "needs: preflight",
            "needs: [preflight, macos, windows]",
            "Verify final release asset set",
            "Verify release readiness report",
            "verify_release_report.py --report artifacts/release/final/release-readiness.md --skip-website --require-assets --require-pass-status",
            'verify_release_readiness.py --skip-website --require-assets --release-dir artifacts/release/final --require-github-release --github-release-tag "$HUMUNGOUSAUR_RELEASE_TAG" --release-tag "$HUMUNGOUSAUR_RELEASE_TAG"',
            "Unexpected final release asset set",
        ]:
            self.assertIn(expected, workflow_text)
        publish_block = workflow_text.split("\n  publish:", 1)[1]
        for expected in [
            "actions/setup-python@v6",
            'python -m pip install -e ".[browser,pdf,ocr,office,test]"',
            "generate_release_report.py",
            "HUMUNGOUSAUR_RELEASE_TAG",
            "--fail-on-check-failure",
            "verify_release_report.py",
            "contents: write",
        ]:
            self.assertIn(expected, publish_block)

    def test_release_workflow_uses_least_privilege_permissions(self) -> None:
        ci_text = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow_text = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")
        before_jobs = workflow_text.split("\njobs:", 1)[0]
        publish_block = workflow_text.split("\n  publish:", 1)[1]

        self.assertIn("permissions:\n  contents: read", ci_text)
        self.assertIn("permissions:\n  contents: read", before_jobs)
        self.assertIn("permissions:\n      contents: write", publish_block)
        self.assertNotIn("contents: write", before_jobs)
        for deprecated_action in [
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/setup-dotnet@v4",
            "actions/upload-artifact@v4",
            "actions/download-artifact@v4",
        ]:
            self.assertNotIn(deprecated_action, ci_text)
            self.assertNotIn(deprecated_action, workflow_text)
        for node24_action in [
            "actions/checkout@v6",
            "actions/setup-python@v6",
            "actions/setup-dotnet@v5",
            "actions/upload-artifact@v7",
            "actions/download-artifact@v8",
        ]:
            self.assertIn(node24_action, ci_text + workflow_text)

    def test_real_world_smoke_runs_safe_app_browser_and_calendar_checks(self) -> None:
        module = load_real_world_smoke_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workspace = temp_path / "workspace"
            data_dir = temp_path / "real-world-smoke"
            workspace.mkdir()
            with patch.object(
                module.sys,
                "argv",
                ["smoke_real_world_tasks.py", "--workspace", str(workspace), "--data-dir", str(data_dir)],
            ):
                exit_code = module.main()

            payload = json.loads((data_dir / "real-world-smoke-results.json").read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertTrue(payload["ok"])
        names = {item["name"] for item in payload["results"]}
        self.assertIn("browser_live_open_dry_run", names)
        self.assertIn("os_launch_allowlisted_app_dry_run", names)
        self.assertIn("google_calendar_operation_prepare", names)

    def test_release_report_verifier_requires_core_sections_and_pass_status(self) -> None:
        module = load_verify_release_report_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "release-readiness.md"
            report.write_text(
                "\n".join(
                    [
                        "# Humungousaur Release Readiness",
                        "## Artifact Manifest",
                        "- `Humungousaur-Windows.zip`: 1 bytes, sha256 `abc`",
                        "- `Humungousaur-macOS.zip`: 1 bytes, sha256 `def`",
                        "- `checksums.txt`: 1 bytes",
                        "## Backend Regression",
                        "- Status: `PASS`",
                        "- Command: `python -m unittest discover -v`",
                        "```text",
                        "OK",
                        "```",
                        "## Open-Source Hygiene",
                        "- Status: `PASS`",
                        "verify_open_source_hygiene.py",
                        "## Desktop Parity",
                        "- Status: `PASS`",
                        "verify_desktop_parity.py",
                        "## Desktop Runtime Smoke",
                        "- Status: `PASS`",
                        "verify_desktop_runtime_smoke.py",
                        "## Release Preflight",
                        "- Status: `PASS`",
                        "verify_release_readiness.py --require-assets",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(
                module.sys,
                "argv",
                [
                    "verify_release_report.py",
                    "--report",
                    str(report),
                    "--skip-website",
                    "--require-assets",
                    "--require-pass-status",
                ],
            ):
                exit_code = module.main()

        self.assertEqual(0, exit_code)

    def test_release_report_verifier_fails_on_missing_evidence(self) -> None:
        module = load_verify_release_report_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "release-readiness.md"
            report.write_text("# Humungousaur Release Readiness\n- Status: `FAIL`\n", encoding="utf-8")

            with patch.object(
                module.sys,
                "argv",
                ["verify_release_report.py", "--report", str(report), "--require-pass-status"],
            ):
                exit_code = module.main()

        self.assertEqual(1, exit_code)

    def test_publication_state_parses_dirty_and_renamed_status_entries(self) -> None:
        module = load_publication_state_module()

        entries = module.parse_status(" M README.md\n?? script/new.py\nR  old.py -> new.py\n")

        self.assertEqual([(" M", "README.md"), ("??", "script/new.py"), ("R ", "new.py")], [(entry.code, entry.path) for entry in entries])

    def test_publication_state_requires_current_macos_swift_sources(self) -> None:
        module = load_publication_state_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "apps/macos/Sources"
            source_dir.mkdir(parents=True)
            (source_dir / "NewReleaseView.swift").write_text("import SwiftUI\n", encoding="utf-8")
            tracked = set(module.REQUIRED_TRACKED_PATHS)

            with patch.object(module, "tracked_files", return_value=tracked):
                errors = module.publication_errors(root, require_clean=False)

        self.assertIn(
            "apps/macos/Sources/NewReleaseView.swift: required release/publication file is not tracked by git",
            errors,
        )

    def test_publication_state_requires_current_windows_app_sources(self) -> None:
        module = load_publication_state_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "apps/windows/Humungousaur.App/Services"
            source_dir.mkdir(parents=True)
            (source_dir / "NewWindowsService.cs").write_text("namespace Humungousaur.App.Services;\n", encoding="utf-8")
            tracked = set(module.REQUIRED_TRACKED_PATHS)

            with patch.object(module, "tracked_files", return_value=tracked):
                errors = module.publication_errors(root, require_clean=False)

        self.assertIn(
            "apps/windows/Humungousaur.App/Services/NewWindowsService.cs: required release/publication file is not tracked by git",
            errors,
        )

    def test_publication_state_requires_core_agent_architecture_docs(self) -> None:
        module = load_publication_state_module()

        for path in [
            "docs/GLOBAL_AGENT_INSTRUCTIONS.md",
            "docs/COGNITIVE_AGENT_ARCHITECTURE.md",
            "docs/AGENT_SKILL_AUTHORING_STANDARD.md",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, module.REQUIRED_TRACKED_PATHS)

    def test_publication_state_can_include_website_gate(self) -> None:
        module = load_publication_state_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            website_root = Path(temp_dir)

            def fake_run(command, cwd, text, capture_output, check):
                self.assertEqual(["npm", "run", "check:publication"], command)
                self.assertEqual(website_root, cwd)
                self.assertTrue(text)
                self.assertTrue(capture_output)
                self.assertFalse(check)
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="FAIL AGENTS.md: required website publication file is not tracked by git\n\nWebsite publication state: 0 passed, 1 failures\n",
                )

            with patch.object(module.subprocess, "run", side_effect=fake_run):
                errors = module.website_publication_errors(website_root)

        self.assertEqual(["website: AGENTS.md: required website publication file is not tracked by git"], errors)

    def test_publication_state_forwards_allow_dirty_to_website_gate(self) -> None:
        module = load_publication_state_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            website_root = Path(temp_dir)
            seen_commands = []

            def fake_run(command, cwd, text, capture_output, check):
                del cwd, text, capture_output, check
                seen_commands.append(command)
                return subprocess.CompletedProcess(command, 0, stdout="Website publication state: ok\n", stderr="")

            with patch.object(module.subprocess, "run", side_effect=fake_run):
                errors = module.website_publication_errors(website_root, require_clean=False)

        self.assertEqual([], errors)
        self.assertEqual([["npm", "run", "check:publication", "--", "--allow-dirty"]], seen_commands)

    def test_publication_state_combines_runtime_and_website_errors(self) -> None:
        module = load_publication_state_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "agent"
            website_root = Path(temp_dir) / "website"
            root.mkdir()
            website_root.mkdir()
            tracked = set(module.REQUIRED_TRACKED_PATHS)
            tracked.remove("AGENTS.md")

            def fake_website_publication_errors(path, require_clean=True):
                self.assertEqual(website_root, path)
                self.assertFalse(require_clean)
                return ["website: README.md: working tree has pending status \" M\""]

            with (
                patch.object(module, "tracked_files", return_value=tracked),
                patch.object(module, "website_publication_errors", side_effect=fake_website_publication_errors),
            ):
                errors = module.publication_errors(root, require_clean=False, website_root=website_root)

        self.assertIn("AGENTS.md: required release/publication file is not tracked by git", errors)
        self.assertIn('website: README.md: working tree has pending status " M"', errors)

    def test_open_source_hygiene_scans_untracked_publish_candidates(self) -> None:
        module = load_open_source_hygiene_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tracked = root / "tracked.py"
            untracked = root / "new_release_file.py"
            tracked.write_text("print('tracked')\n", encoding="utf-8")
            untracked.write_text("print('new')\n", encoding="utf-8")

            def fake_git_paths(_root, args):
                if args == ["ls-files"]:
                    return {tracked}
                if args == ["ls-files", "--others", "--exclude-standard"]:
                    return {untracked}
                raise AssertionError(f"unexpected git args: {args}")

            with patch.object(module, "git_paths", side_effect=fake_git_paths):
                candidates = module.publish_candidates(root)

        self.assertEqual({tracked, untracked}, set(candidates))

    def test_open_source_hygiene_rejects_untracked_secret_candidates(self) -> None:
        module = load_open_source_hygiene_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            secret = root / "new_release_notes.md"
            secret.write_text("temporary key sk-proj-" + "a" * 24 + "\n", encoding="utf-8")

            def fake_git_paths(_root, args):
                if args == ["ls-files"]:
                    return set()
                if args == ["ls-files", "--others", "--exclude-standard"]:
                    return {secret}
                raise AssertionError(f"unexpected git args: {args}")

            with patch.object(module, "git_paths", side_effect=fake_git_paths):
                _count, errors = module.check_root(root, "agent")

        self.assertTrue(any("likely OpenAI project key" in error for error in errors), errors)

    def test_open_source_hygiene_rejects_oversized_publish_candidates(self) -> None:
        module = load_open_source_hygiene_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            oversized = root / "release-output.bin"
            oversized.write_bytes(b"x" * (module.MAX_PUBLISH_CANDIDATE_BYTES + 1))

            def fake_git_paths(_root, args):
                if args == ["ls-files"]:
                    return set()
                if args == ["ls-files", "--others", "--exclude-standard"]:
                    return {oversized}
                raise AssertionError(f"unexpected git args: {args}")

            with patch.object(module, "git_paths", side_effect=fake_git_paths):
                _count, errors = module.check_root(root, "agent")

        self.assertTrue(any("source-size limit" in error for error in errors), errors)

    def test_collect_release_artifacts_downloads_zips_and_writes_checksums(self) -> None:
        module = load_collect_release_artifacts_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            release_dir = temp_path / "release"
            downloaded = temp_path / "downloaded"
            source = temp_path / "source"
            (source / "Humungousaur-Windows").mkdir(parents=True)
            (source / "Humungousaur-macOS").mkdir(parents=True)
            windows_zip = source / "Humungousaur-Windows" / module.WINDOWS_ASSET
            macos_zip = source / "Humungousaur-macOS" / module.MACOS_ASSET
            windows_zip.write_bytes(b"windows release bytes")
            macos_zip.write_bytes(b"macos release bytes")
            seen_verify: list[list[str]] = []

            def fake_run(command, cwd=module.ROOT):
                if command[:3] == ["gh", "run", "download"]:
                    output_dir = Path(command[command.index("--dir") + 1])
                    shutil.copytree(source, output_dir, dirs_exist_ok=True)
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command[1].endswith("verify_release_readiness.py"):
                    seen_verify.append(command)
                    return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")
                raise AssertionError(f"unexpected command: {command}")

            with patch.object(module, "run", side_effect=fake_run), patch.object(
                module.sys,
                "argv",
                [
                    "collect_release_artifacts.py",
                    "--run-id",
                    "12345",
                    "--release-dir",
                    str(release_dir),
                    "--release-tag",
                    "v0.1.0",
                ],
            ):
                exit_code = module.main()

            self.assertEqual(0, exit_code)
            self.assertEqual(windows_zip.read_bytes(), (release_dir / module.WINDOWS_ASSET).read_bytes())
            self.assertEqual(macos_zip.read_bytes(), (release_dir / module.MACOS_ASSET).read_bytes())
            checksums = (release_dir / module.CHECKSUMS_ASSET).read_text(encoding="utf-8")
            self.assertIn(f"{sha256(windows_zip.read_bytes()).hexdigest()}  {module.WINDOWS_ASSET}", checksums)
            self.assertIn(f"{sha256(macos_zip.read_bytes()).hexdigest()}  {module.MACOS_ASSET}", checksums)
            self.assertTrue(seen_verify)
            self.assertIn("--require-assets", seen_verify[0])
            self.assertIn("--release-tag", seen_verify[0])

    def test_collect_release_artifacts_can_select_latest_successful_run(self) -> None:
        module = load_collect_release_artifacts_module()

        def fake_run(command, cwd=module.ROOT):
            if command[:3] == ["gh", "run", "list"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps([{"databaseId": 98765, "displayTitle": "release", "createdAt": "2026-06-08T00:00:00Z"}]),
                    stderr="",
                )
            raise AssertionError(f"unexpected command: {command}")

        with patch.object(module, "run", side_effect=fake_run):
            run_id = module.latest_successful_run_id("owner/repo", "Release Desktop Apps")

        self.assertEqual("98765", run_id)

    def test_release_report_records_backend_regression_section(self) -> None:
        module = load_release_report_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "release-readiness.md"
            release_dir = Path(temp_dir) / "release"
            release_dir.mkdir()

            def fake_run_command(command, cwd=None, env=None):
                if command[1:5] == ["-m", "unittest", "discover", "-v"]:
                    return 0, "Ran 412 tests in 29.167s\n\nOK (skipped=6)"
                return 0, "ok"

            with patch.object(module, "run_command", side_effect=fake_run_command), patch.object(
                module.sys,
                "argv",
                ["generate_release_report.py", "--output", str(output), "--release-dir", str(release_dir)],
            ):
                exit_code = module.main()

            report = output.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertIn("## Backend Regression", report)
        self.assertIn("- Status: `PASS`", report)
        self.assertIn("-m unittest discover -v", report)
        self.assertIn("Ran 412 tests", report)
        self.assertIn("## Desktop Runtime Smoke", report)
        self.assertIn("verify_desktop_runtime_smoke.py", report)

    def test_release_report_records_website_checks_when_required(self) -> None:
        module = load_release_report_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "release-readiness.md"
            release_dir = temp_path / "release"
            website_root = temp_path / "website"
            release_dir.mkdir()
            website_root.mkdir()
            seen_commands: list[tuple[tuple[str, ...], Path | None]] = []

            def fake_run_command(command, cwd=None, env=None):
                seen_commands.append((tuple(command), cwd, env))
                return 0, "ok"

            with patch.object(module, "run_command", side_effect=fake_run_command), patch.object(
                module.sys,
                "argv",
                [
                    "generate_release_report.py",
                    "--output",
                    str(output),
                    "--release-dir",
                    str(release_dir),
                    "--website-root",
                    str(website_root),
                    "--require-website",
                ],
            ):
                exit_code = module.main()

            report = output.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        for title in [
            "## Website Lint",
            "## Website Download Source Check",
            "## Website Release Asset Self-Test",
            "## Website Build",
            "## Website Audit",
        ]:
            self.assertIn(title, report)
        self.assertIn("npm run check:downloads", report)
        self.assertIn("npm run check:release-assets:selftest", report)
        self.assertIn("npm audit --audit-level=moderate", report)
        self.assertIn(
            (("npm", "run", "build"), website_root.resolve()),
            [(command, cwd.resolve() if cwd is not None else None) for command, cwd, _env in seen_commands],
        )

    def test_release_report_records_exact_tag_website_live_release_check(self) -> None:
        module = load_release_report_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "release-readiness.md"
            release_dir = temp_path / "release"
            website_root = temp_path / "website"
            release_dir.mkdir()
            website_root.mkdir()
            seen_commands: list[tuple[tuple[str, ...], Path | None, dict[str, str] | None]] = []

            def fake_run_command(command, cwd=None, env=None):
                seen_commands.append((tuple(command), cwd, env))
                return 0, "ok"

            with patch.object(module, "run_command", side_effect=fake_run_command), patch.object(
                module.sys,
                "argv",
                [
                    "generate_release_report.py",
                    "--output",
                    str(output),
                    "--release-dir",
                    str(release_dir),
                    "--website-root",
                    str(website_root),
                    "--require-website",
                    "--check-github-release",
                    "--release-tag",
                    "v0.1.0",
                ],
            ):
                exit_code = module.main()

            report = output.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertIn("## Website Live Release Asset Check", report)
        self.assertIn("HUMUNGOUSAUR_RELEASE_TAG=v0.1.0 npm run check:release-assets", report)
        self.assertIn(
            (("npm", "run", "check:release-assets"), website_root.resolve(), {"HUMUNGOUSAUR_RELEASE_TAG": "v0.1.0"}),
            [
                (command, cwd.resolve() if cwd is not None else None, env)
                for command, cwd, env in seen_commands
            ],
        )

    def test_local_artifact_check_honors_custom_release_directory(self) -> None:
        module = load_release_readiness_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            macos_zip = release_dir / module.MACOS_ASSET
            windows_zip = release_dir / module.WINDOWS_ASSET
            checksums = release_dir / module.CHECKSUMS_ASSET
            version = module.project_version()

            with zipfile.ZipFile(macos_zip, "w") as archive:
                archive.writestr("INSTALL.txt", "\n".join([
                    f"Version: {version}",
                    'python3 -m pip install -e ".[browser,pdf,ocr,office]"',
                    "http://127.0.0.1:8765",
                    "OPENAI_API_KEY",
                    "DEEPGRAM_API_KEY",
                    "channels, voice, autonomy, and approvals",
                    "./script/verify_macos_package.sh",
                ]))
                archive.writestr("Humungousaur.app/Contents/MacOS/HumungousaurMac", "")
                archive.writestr(
                    "Humungousaur.app/Contents/Info.plist",
                    f"""
<plist>
<dict>
  <key>CFBundleShortVersionString</key>
  <string>{version}</string>
  <key>CFBundleVersion</key>
  <string>{version}</string>
</dict>
</plist>
""",
                )

            with zipfile.ZipFile(windows_zip, "w") as archive:
                archive.writestr("INSTALL.txt", "\n".join([
                    f"Version: {version}",
                    'python -m pip install -e ".[browser,pdf,ocr,office]"',
                    "http://127.0.0.1:8765",
                    "OPENAI_API_KEY",
                    "DEEPGRAM_API_KEY",
                    "channels, voice, autonomy, and approvals",
                    ".\\script\\verify_windows_package.ps1",
                ]))
                archive.writestr("publish/Humungousaur.App.exe", "")

            checksums.write_text(
                f"{sha256(windows_zip.read_bytes()).hexdigest()}  {module.WINDOWS_ASSET}\n"
                f"{sha256(macos_zip.read_bytes()).hexdigest()}  {module.MACOS_ASSET}\n",
                encoding="utf-8",
            )

            preflight = module.Preflight()
            module.check_artifacts(preflight, release_dir=release_dir, require_assets=True)

        self.assertEqual([], preflight.errors)
        self.assertIn(f"required local release artifact {module.WINDOWS_ASSET}", preflight.passed)
        self.assertIn(f"{module.CHECKSUMS_ASSET} hash matches {module.MACOS_ASSET}", preflight.passed)
        self.assertIn(f"{module.CHECKSUMS_ASSET} hash matches {module.WINDOWS_ASSET}", preflight.passed)

    def test_local_artifact_check_rejects_unsafe_zip_entries(self) -> None:
        module = load_release_readiness_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            macos_zip = release_dir / module.MACOS_ASSET
            checksums = release_dir / module.CHECKSUMS_ASSET

            with zipfile.ZipFile(macos_zip, "w") as archive:
                archive.writestr("__MACOSX/._Humungousaur", "")
                archive.writestr("INSTALL.txt", "")
                archive.writestr("Humungousaur.app/Contents/MacOS/HumungousaurMac", "")
                archive.writestr("Humungousaur.app/Contents/Info.plist", "")

            checksums.write_text(
                f"{sha256(macos_zip.read_bytes()).hexdigest()}  {module.MACOS_ASSET}\n",
                encoding="utf-8",
            )

            preflight = module.Preflight()
            module.check_artifacts(preflight, release_dir=release_dir, require_assets=False)

        self.assertTrue(
            any("unsafe or platform metadata zip entries" in error for error in preflight.errors),
            preflight.errors,
        )

    def test_platform_package_verifiers_check_version_and_setup_contracts(self) -> None:
        macos_text = MACOS_VERIFY_PATH.read_text(encoding="utf-8")
        windows_text = WINDOWS_VERIFY_PATH.read_text(encoding="utf-8")

        self.assertTrue(windows_text.lstrip().startswith("param("))

        for expected in [
            "CFBundleShortVersionString",
            "CFBundleVersion",
            "Version: $PROJECT_VERSION",
            "python3 -m humungousaur serve",
            "OPENAI_API_KEY",
            "DEEPGRAM_API_KEY",
            "./script/verify_macos_package.sh",
            "__MACOSX",
            ".DS_Store",
            "._",
            "--require-notarization",
            "xcrun stapler validate",
        ]:
            self.assertIn(expected, macos_text)

        for expected in [
            "RuntimeInformation",
            "Windows package verification must run on Windows",
            "FileVersion",
            "ProductVersion",
            'StartsWith("$ProjectVersion+")',
            "Version: $ProjectVersion",
            "python -m humungousaur serve",
            "OPENAI_API_KEY",
            "DEEPGRAM_API_KEY",
            ".\\script\\verify_windows_package.ps1",
            "__MACOSX",
            ".DS_Store",
            "._",
            "$Name = [string]$Entry.FullName",
            "$Normalized = [string]$Name.Replace",
            "[string[]]$Parts",
            'Get-ChildItem -Path $TempDir -Filter "*.exe" -Recurse',
            "$PackageSignableBinaries = Get-ChildItem -Path $TempDir -Recurse -File",
            '($_.Extension -eq ".dll" -and $_.Name -like "Humungousaur*.dll")',
            "TimeStamperCertificate",
        ]:
            self.assertIn(expected, windows_text)

    def test_windows_signature_verifier_covers_app_owned_binaries(self) -> None:
        windows_text = WINDOWS_VERIFY_PATH.read_text(encoding="utf-8")
        package_text = WINDOWS_PACKAGE_PATH.read_text(encoding="utf-8")

        self.assertIn('$SignableBinaries = Get-ChildItem -Path $PublishDir -Recurse -File', package_text)
        self.assertIn('($_.Extension -eq ".dll" -and $_.Name -like "Humungousaur*.dll")', package_text)
        self.assertIn('$PackageSignableBinaries = Get-ChildItem -Path $TempDir -Recurse -File', windows_text)
        self.assertIn('($_.Extension -eq ".dll" -and $_.Name -like "Humungousaur*.dll")', windows_text)
        self.assertIn("foreach ($Binary in $PackageSignableBinaries)", windows_text)
        self.assertIn("Get-AuthenticodeSignature $Binary.FullName", windows_text)
        self.assertIn("TimeStamperCertificate", windows_text)

    def test_macos_notarization_verifier_checks_stapled_ticket(self) -> None:
        macos_text = MACOS_VERIFY_PATH.read_text(encoding="utf-8")
        workflow_text = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("--require-notarization", macos_text)
        self.assertIn("REQUIRE_NOTARIZATION=1", macos_text)
        self.assertIn('xcrun stapler validate "$APP_BUNDLE"', macos_text)
        self.assertIn("verify_macos_package.sh --require-signature --require-notarization", workflow_text)

    def test_package_scripts_clean_staging_before_public_zip(self) -> None:
        macos_package_text = MACOS_PACKAGE_PATH.read_text(encoding="utf-8")
        windows_package_text = WINDOWS_PACKAGE_PATH.read_text(encoding="utf-8")

        self.assertIn('rm -rf "$STAGE_DIR"', macos_package_text)
        self.assertIn("Remove-Item -Path $PublishDir -Recurse -Force", windows_package_text)

    def test_macos_package_declares_voice_wakeup_permissions(self) -> None:
        package_text = MACOS_PACKAGE_PATH.read_text(encoding="utf-8")
        run_text = (ROOT / "script" / "build_and_run.sh").read_text(encoding="utf-8")

        for text in [package_text, run_text]:
            self.assertIn("NSMicrophoneUsageDescription", text)
            self.assertIn("NSSpeechRecognitionUsageDescription", text)
            self.assertIn("voice wake-up", text)
        self.assertIn("approve microphone and speech-recognition permissions", package_text)

    def test_portability_check_rejects_developer_home_paths(self) -> None:
        module = load_release_readiness_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            developer_path = "/" + "Users/example/Documents/" + "bhaveshpabnani/Umang"
            (root / "app.py").write_text(f'WORKSPACE = "{developer_path}"\n', encoding="utf-8")

            preflight = module.Preflight()
            module.check_portability(preflight, root)

        self.assertTrue(any("developer-specific checkout path" in error for error in preflight.errors), preflight.errors)

    def test_github_release_check_downloads_checksums_and_validates_rows(self) -> None:
        module = load_release_readiness_module()
        windows_bytes = b"windows zip"
        macos_bytes = b"macos zip"
        assets = [
            {"name": module.WINDOWS_ASSET, "size": 123},
            {"name": module.MACOS_ASSET, "size": 456},
            {"name": module.CHECKSUMS_ASSET, "size": 789},
        ]

        def fake_run(command, **_kwargs):
            if command[:3] == ["gh", "release", "view"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps({"url": "https://github.com/example/release", "assets": assets}),
                    stderr="",
                )
            if command[:3] == ["gh", "release", "download"]:
                output_dir = Path(command[command.index("--dir") + 1])
                pattern = command[command.index("--pattern") + 1]
                output_dir.mkdir(parents=True, exist_ok=True)
                if pattern == module.CHECKSUMS_ASSET:
                    (output_dir / module.CHECKSUMS_ASSET).write_text(
                        f"{sha256(windows_bytes).hexdigest()}  {module.WINDOWS_ASSET}\n"
                        f"{sha256(macos_bytes).hexdigest()}  {module.MACOS_ASSET}\n",
                        encoding="utf-8",
                    )
                elif pattern == module.WINDOWS_ASSET:
                    (output_dir / module.WINDOWS_ASSET).write_bytes(windows_bytes)
                elif pattern == module.MACOS_ASSET:
                    (output_dir / module.MACOS_ASSET).write_bytes(macos_bytes)
                else:
                    raise AssertionError(f"unexpected release asset pattern: {pattern}")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        preflight = module.Preflight()
        with patch.object(module.subprocess, "run", side_effect=fake_run):
            module.check_github_release(preflight, require_release=True, release_tag="v0.1.0")

        self.assertEqual([], preflight.errors)
        self.assertIn("GitHub v0.1.0 checksums.txt includes both desktop zip rows", preflight.passed)
        self.assertIn("GitHub v0.1.0 Humungousaur-Windows.zip hash matches checksums.txt", preflight.passed)
        self.assertIn("GitHub v0.1.0 Humungousaur-macOS.zip hash matches checksums.txt", preflight.passed)

    def test_github_release_check_uses_configurable_repo_slug(self) -> None:
        module = load_release_readiness_module()
        repos: list[str] = []

        def fake_run(command, **_kwargs):
            if command[:3] == ["gh", "release", "view"]:
                repos.append(command[command.index("--repo") + 1])
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="not found")
            raise AssertionError(f"unexpected command: {command}")

        preflight = module.Preflight()
        with patch.object(module.subprocess, "run", side_effect=fake_run):
            module.check_github_release(preflight, require_release=False, release_tag=None, repo="example/Humungousaur")

        self.assertEqual(["example/Humungousaur"], repos)
        self.assertEqual([], preflight.errors)

    def test_github_release_check_fails_when_checksums_miss_desktop_zip(self) -> None:
        module = load_release_readiness_module()
        macos_bytes = b"macos zip"
        assets = [
            {"name": module.WINDOWS_ASSET, "size": 123},
            {"name": module.MACOS_ASSET, "size": 456},
            {"name": module.CHECKSUMS_ASSET, "size": 789},
        ]

        def fake_run(command, **_kwargs):
            if command[:3] == ["gh", "release", "view"]:
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"assets": assets}), stderr="")
            if command[:3] == ["gh", "release", "download"]:
                output_dir = Path(command[command.index("--dir") + 1])
                pattern = command[command.index("--pattern") + 1]
                output_dir.mkdir(parents=True, exist_ok=True)
                if pattern == module.CHECKSUMS_ASSET:
                    (output_dir / module.CHECKSUMS_ASSET).write_text(
                        f"{sha256(macos_bytes).hexdigest()}  {module.MACOS_ASSET}\n",
                        encoding="utf-8",
                    )
                elif pattern == module.WINDOWS_ASSET:
                    (output_dir / module.WINDOWS_ASSET).write_bytes(b"windows zip")
                elif pattern == module.MACOS_ASSET:
                    (output_dir / module.MACOS_ASSET).write_bytes(macos_bytes)
                else:
                    raise AssertionError(f"unexpected release asset pattern: {pattern}")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        preflight = module.Preflight()
        with patch.object(module.subprocess, "run", side_effect=fake_run):
            module.check_github_release(preflight, require_release=True, release_tag="v0.1.0")

        self.assertTrue(any(module.WINDOWS_ASSET in error for error in preflight.errors), preflight.errors)

    def test_github_release_check_fails_when_download_hash_differs_from_checksum(self) -> None:
        module = load_release_readiness_module()
        windows_bytes = b"windows zip"
        macos_bytes = b"macos zip"
        assets = [
            {"name": module.WINDOWS_ASSET, "size": 123},
            {"name": module.MACOS_ASSET, "size": 456},
            {"name": module.CHECKSUMS_ASSET, "size": 789},
        ]

        def fake_run(command, **_kwargs):
            if command[:3] == ["gh", "release", "view"]:
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"assets": assets}), stderr="")
            if command[:3] == ["gh", "release", "download"]:
                output_dir = Path(command[command.index("--dir") + 1])
                pattern = command[command.index("--pattern") + 1]
                output_dir.mkdir(parents=True, exist_ok=True)
                if pattern == module.CHECKSUMS_ASSET:
                    (output_dir / module.CHECKSUMS_ASSET).write_text(
                        f"{'0' * 64}  {module.WINDOWS_ASSET}\n"
                        f"{sha256(macos_bytes).hexdigest()}  {module.MACOS_ASSET}\n",
                        encoding="utf-8",
                    )
                elif pattern == module.WINDOWS_ASSET:
                    (output_dir / module.WINDOWS_ASSET).write_bytes(windows_bytes)
                elif pattern == module.MACOS_ASSET:
                    (output_dir / module.MACOS_ASSET).write_bytes(macos_bytes)
                else:
                    raise AssertionError(f"unexpected release asset pattern: {pattern}")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        preflight = module.Preflight()
        with patch.object(module.subprocess, "run", side_effect=fake_run):
            module.check_github_release(preflight, require_release=True, release_tag="v0.1.0")

        self.assertTrue(any("hash mismatch" in error and module.WINDOWS_ASSET in error for error in preflight.errors), preflight.errors)


if __name__ == "__main__":
    unittest.main()
