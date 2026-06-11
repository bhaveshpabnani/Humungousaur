param(
  [string]$ZipPath,
  [string]$InstallerZipPath,
  [string]$ChecksumPath,
  [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$IsWindowsPlatform = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
if (-not $IsWindowsPlatform) {
  throw "Windows package verification must run on Windows because it checks Humungousaur.App.exe version metadata and Authenticode signature state."
}
$PyprojectText = Get-Content -Raw -Path (Join-Path $Root "pyproject.toml")
if ($PyprojectText -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
  throw "Unable to read project.version from pyproject.toml"
}
$ProjectVersion = $Matches[1]
if ($ProjectVersion -notmatch '^(\d+)\.(\d+)\.(\d+)') {
  throw "Project version must start with major.minor.patch for Windows metadata: $ProjectVersion"
}
$WindowsFileVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
if ([string]::IsNullOrWhiteSpace($ZipPath)) {
  $ZipPath = Join-Path $Root "artifacts/release/Humungousaur-Windows.zip"
}
if ([string]::IsNullOrWhiteSpace($InstallerZipPath)) {
  $InstallerZipPath = Join-Path $Root "artifacts/release/Humungousaur-Windows-Setup.zip"
}
if ([string]::IsNullOrWhiteSpace($ChecksumPath)) {
  $ChecksumPath = Join-Path $Root "artifacts/release/checksums.txt"
}

if (-not (Test-Path $ZipPath)) {
  throw "Missing Windows release zip: $ZipPath"
}
if (-not (Test-Path $InstallerZipPath)) {
  throw "Missing Windows installer zip: $InstallerZipPath"
}

function Test-ZipEntriesClean {
  param([string]$Path, [string]$Label)
  $Archive = [IO.Compression.ZipFile]::OpenRead($Path)
  try {
    foreach ($Entry in $Archive.Entries) {
      $Name = [string]$Entry.FullName
      $Normalized = [string]$Name.Replace("\", "/")
      [string[]]$Parts = @($Normalized.Split("/") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
      $BaseName = if ($Parts.Count -gt 0) { $Parts[-1] } else { $Normalized }
      if (
        $Normalized.StartsWith("/") -or
        $Normalized.StartsWith("\") -or
        ($Normalized.Length -ge 2 -and $Normalized[1] -eq ":") -or
        ($Parts -contains "..") -or
        ($Parts -contains "__MACOSX") -or
        $BaseName -eq ".DS_Store" -or
        $BaseName.StartsWith("._")
      ) {
        throw "$Label contains unsafe or platform metadata zip entry: $Name"
      }
    }
  }
  finally {
    $Archive.Dispose()
  }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
Test-ZipEntriesClean -Path $ZipPath -Label "Windows package"
Test-ZipEntriesClean -Path $InstallerZipPath -Label "Windows installer package"

$TempDir = Join-Path ([IO.Path]::GetTempPath()) ("humungousaur-windows-package-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

try {
  Expand-Archive -Path $ZipPath -DestinationPath $TempDir -Force

  $InstallDoc = Get-ChildItem -Path $TempDir -Filter "INSTALL.txt" -Recurse | Select-Object -First 1
  if ($null -eq $InstallDoc) {
    throw "Windows package is missing INSTALL.txt"
  }

  $AppExe = Get-ChildItem -Path $TempDir -Filter "Humungousaur.App.exe" -Recurse | Select-Object -First 1
  if ($null -eq $AppExe) {
    throw "Windows package is missing Humungousaur.App.exe"
  }
  $PackageExecutables = Get-ChildItem -Path $TempDir -Filter "*.exe" -Recurse
  if ($PackageExecutables.Count -eq 0) {
    throw "Windows package does not contain any executable files"
  }
  $PackageSignableBinaries = Get-ChildItem -Path $TempDir -Recurse -File |
    Where-Object { $_.Extension -eq ".exe" -or ($_.Extension -eq ".dll" -and $_.Name -like "Humungousaur*.dll") }
  if ($PackageSignableBinaries.Count -eq 0) {
    throw "Windows package does not contain any Humungousaur binaries to verify"
  }

  $InstallText = Get-Content -Raw -Path $InstallDoc.FullName
  $ExpectedInstallText = @(
    "Version: $ProjectVersion",
    'python -m pip install -e ".[browser,pdf,ocr,office]"',
    "python -m humungousaur serve",
    "http://127.0.0.1:8765",
    "OPENAI_API_KEY",
    "DEEPGRAM_API_KEY",
    "channels, voice, autonomy, and approvals",
    ".\script\verify_windows_package.ps1"
  )
  foreach ($Expected in $ExpectedInstallText) {
    if (-not $InstallText.Contains($Expected)) {
      throw "Windows INSTALL.txt is missing expected setup text: $Expected"
    }
  }

  $VersionInfo = (Get-Item $AppExe.FullName).VersionInfo
  if ($VersionInfo.FileVersion -ne $WindowsFileVersion) {
    throw "Humungousaur.App.exe FileVersion mismatch. Expected $WindowsFileVersion, got $($VersionInfo.FileVersion)"
  }
  $ProductVersion = [string]$VersionInfo.ProductVersion
  if ($ProductVersion -ne $ProjectVersion -and -not $ProductVersion.StartsWith("$ProjectVersion+")) {
    throw "Humungousaur.App.exe ProductVersion mismatch. Expected $ProjectVersion or $ProjectVersion+<source-revision>, got $ProductVersion"
  }

  if (Test-Path $ChecksumPath) {
    $ExpectedLine = Get-Content $ChecksumPath | Where-Object { $_ -match "\s+Humungousaur-Windows\.zip$" } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($ExpectedLine)) {
      throw "checksums.txt is missing Humungousaur-Windows.zip"
    }
    $ExpectedHash = ($ExpectedLine -split "\s+")[0].ToLowerInvariant()
    $ActualHash = (Get-FileHash -Algorithm SHA256 $ZipPath).Hash.ToLowerInvariant()
    if ($ExpectedHash -ne $ActualHash) {
      throw "Windows checksum mismatch. Expected $ExpectedHash, got $ActualHash"
    }
    $ExpectedInstallerLine = Get-Content $ChecksumPath | Where-Object { $_ -match "\s+Humungousaur-Windows-Setup\.zip$" } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($ExpectedInstallerLine)) {
      throw "checksums.txt is missing Humungousaur-Windows-Setup.zip"
    }
    $ExpectedInstallerHash = ($ExpectedInstallerLine -split "\s+")[0].ToLowerInvariant()
    $ActualInstallerHash = (Get-FileHash -Algorithm SHA256 $InstallerZipPath).Hash.ToLowerInvariant()
    if ($ExpectedInstallerHash -ne $ActualInstallerHash) {
      throw "Windows installer checksum mismatch. Expected $ExpectedInstallerHash, got $ActualInstallerHash"
    }
  }

  if ($RequireSignature) {
    foreach ($Binary in $PackageSignableBinaries) {
      $Signature = Get-AuthenticodeSignature $Binary.FullName
      if ($Signature.Status -ne "Valid") {
        throw "$($Binary.Name) signature is $($Signature.Status): $($Signature.StatusMessage)"
      }
      if ($null -eq $Signature.TimeStamperCertificate) {
        throw "$($Binary.Name) signature is missing a timestamp certificate"
      }
    }
  }

  $InstallerTempDir = Join-Path ([IO.Path]::GetTempPath()) ("humungousaur-windows-installer-" + [Guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Force -Path $InstallerTempDir | Out-Null
  try {
    Expand-Archive -Path $InstallerZipPath -DestinationPath $InstallerTempDir -Force
    foreach ($Expected in @(
      "Install-Humungousaur.ps1",
      "README.txt",
      "runtime-source\script\bootstrap_runtime.py"
    )) {
      if (-not (Test-Path (Join-Path $InstallerTempDir $Expected))) {
        throw "Windows installer zip is missing $Expected"
      }
    }
    $InstallerScript = Get-Content -Raw -Path (Join-Path $InstallerTempDir "Install-Humungousaur.ps1")
    foreach ($ExpectedText in @("InstallPythonWithWinget", "Playwright Chromium", "Start Menu/Desktop shortcuts", "runtime-source")) {
      if (-not $InstallerScript.Contains($ExpectedText)) {
        throw "Windows installer script is missing expected setup text: $ExpectedText"
      }
    }
    if ($null -eq (Get-ChildItem -Path (Join-Path $InstallerTempDir "app") -Filter "Humungousaur.App.exe" -Recurse | Select-Object -First 1)) {
      throw "Windows installer zip is missing app\Humungousaur.App.exe"
    }
  }
  finally {
    Remove-Item -Path $InstallerTempDir -Recurse -Force -ErrorAction SilentlyContinue
  }

  Write-Host "Verified $ZipPath"
  Write-Host "Verified $InstallerZipPath"
}
finally {
  Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
