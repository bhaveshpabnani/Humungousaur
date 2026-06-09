param(
  [string]$ZipPath,
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
if ([string]::IsNullOrWhiteSpace($ChecksumPath)) {
  $ChecksumPath = Join-Path $Root "artifacts/release/checksums.txt"
}

if (-not (Test-Path $ZipPath)) {
  throw "Missing Windows release zip: $ZipPath"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$ZipArchive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  foreach ($Entry in $ZipArchive.Entries) {
    $Name = $Entry.FullName
    $Normalized = $Name.Replace("\", "/")
    $Parts = $Normalized.Split("/") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
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
      throw "Windows package contains unsafe or platform metadata zip entry: $Name"
    }
  }
}
finally {
  $ZipArchive.Dispose()
}

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
  if ($VersionInfo.ProductVersion -ne $ProjectVersion) {
    throw "Humungousaur.App.exe ProductVersion mismatch. Expected $ProjectVersion, got $($VersionInfo.ProductVersion)"
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

  Write-Host "Verified $ZipPath"
}
finally {
  Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
