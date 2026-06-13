from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.4"
WINDOWS_EXE_SHA256 = "6232faf02acafe1fe66560e728ccb05add8956d775636397b4d0cde8500fb2a1"
WINDOWS_ZIP_SHA256 = "bf188009c4672f5e59e8fefdb88ca696e570588efa5e776d60a316909d531759"
MACOS_PKG_SHA256 = "48873267762f3b70684fc44cad4b85edb0296f4b030e55449a12a034de1d6a3d"


def main() -> int:
    checks = [
        _check_homebrew(),
        _check_scoop(),
        _check_chocolatey(),
        _check_winget(),
    ]
    failures = [item for item in checks if item]
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("Package manager metadata verified.")
    return 0


def _read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        raise AssertionError(f"Missing {path}")
    return target.read_text(encoding="utf-8")


def _check_homebrew() -> str:
    try:
        text = _read("Casks/humungousaur.rb")
        _require(text, f'version "{VERSION}"', "Homebrew version mismatch")
        _require(text, MACOS_PKG_SHA256, "Homebrew macOS pkg checksum mismatch")
        _require(text, "Humungousaur-macOS.pkg", "Homebrew pkg asset missing")
    except AssertionError as exc:
        return str(exc)
    return ""


def _check_scoop() -> str:
    try:
        payload = json.loads(_read("bucket/humungousaur.json"))
        if payload.get("version") != VERSION:
            raise AssertionError("Scoop version mismatch")
        arch = payload.get("architecture", {}).get("64bit", {})
        if arch.get("hash") != WINDOWS_ZIP_SHA256:
            raise AssertionError("Scoop zip checksum mismatch")
        _require(str(arch.get("url", "")), "Humungousaur-Windows.zip", "Scoop zip URL missing")
    except (AssertionError, json.JSONDecodeError) as exc:
        return str(exc)
    return ""


def _check_chocolatey() -> str:
    try:
        nuspec = _read("chocolatey/humungousaur/humungousaur.nuspec")
        install = _read("chocolatey/humungousaur/tools/chocolateyinstall.ps1")
        _require(nuspec, f"<version>{VERSION}</version>", "Chocolatey version mismatch")
        _require(install, WINDOWS_EXE_SHA256, "Chocolatey exe checksum mismatch")
        _require(install, "Humungousaur-Windows-Setup.exe", "Chocolatey installer URL missing")
    except AssertionError as exc:
        return str(exc)
    return ""


def _check_winget() -> str:
    try:
        base = f"winget/manifests/b/BhaveshPabnani/Humungousaur/{VERSION}"
        version_text = _read(f"{base}/BhaveshPabnani.Humungousaur.yaml")
        locale_text = _read(f"{base}/BhaveshPabnani.Humungousaur.locale.en-US.yaml")
        installer_text = _read(f"{base}/BhaveshPabnani.Humungousaur.installer.yaml")
        for text in (version_text, locale_text, installer_text):
            _require(text, f"PackageVersion: {VERSION}", "WinGet version mismatch")
            _require(text, "ManifestVersion: 1.9.0", "WinGet manifest version mismatch")
        _require(installer_text, WINDOWS_EXE_SHA256.upper(), "WinGet installer checksum mismatch")
        _require(installer_text, "InstallerType: inno", "WinGet installer type mismatch")
        if re.search(r"InstallerSha256:\s+[a-f]", installer_text):
            raise AssertionError("WinGet InstallerSha256 must be uppercase")
    except AssertionError as exc:
        return str(exc)
    return ""


def _require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
