# Package Manager Distribution

Humungousaur publishes package-manager metadata from this repository so users can install the native desktop apps from release assets.

## Current install commands

### Homebrew

```bash
brew tap bhaveshpabnani/humungousaur https://github.com/bhaveshpabnani/Humungousaur
brew install --cask humungousaur
```

The cask lives at `Casks/humungousaur.rb` and installs `Humungousaur-macOS.pkg` from the GitHub release.

Production macOS releases should be Developer ID signed and notarized. Until that Apple Developer certificate flow is complete, Gatekeeper can warn that Apple cannot verify the package.

### WinGet

The WinGet manifests live under `winget/manifests/b/BhaveshPabnani/Humungousaur/<version>/`.

Local manifest install:

```powershell
winget install --manifest .\winget\manifests\b\BhaveshPabnani\Humungousaur\0.1.4
```

Official WinGet availability requires submitting these manifests to `microsoft/winget-pkgs` and passing Microsoft validation/review.

### Chocolatey

The Chocolatey package source lives under `chocolatey/humungousaur/`.

Local package build and install:

```powershell
choco pack .\chocolatey\humungousaur\humungousaur.nuspec --out .
choco install humungousaur --source . -y
```

Official Chocolatey community availability requires a Chocolatey account/API key and package moderation.

### Scoop

```powershell
scoop bucket add humungousaur https://github.com/bhaveshpabnani/Humungousaur
scoop install humungousaur
```

The Scoop manifest lives at `bucket/humungousaur.json` and installs `Humungousaur-Windows.zip` from the GitHub release.

## Release asset source of truth

Package managers should reference immutable versioned GitHub release assets:

- `Humungousaur-Windows-Setup.exe`
- `Humungousaur-Windows.zip`
- `Humungousaur-macOS.pkg`
- `Humungousaur-macOS.zip`
- `checksums.txt`

When publishing a new version:

1. Run the release workflow for the tag.
2. Confirm all assets exist on the GitHub release.
3. Update package-manager versions, URLs, and SHA-256 hashes.
4. Run `python3 script/verify_package_managers.py`.
5. Submit official registry PRs or pushes where credentials/review are required.
