param(
  [string]$InstallRoot,
  [string]$DataRoot,
  [switch]$InstallPythonWithWinget,
  [switch]$SkipPlaywright,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadApp = Join-Path $PackageRoot "app"
$PayloadRuntime = Join-Path $PackageRoot "runtime-source"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
  $InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\Humungousaur"
}
if ([string]::IsNullOrWhiteSpace($DataRoot)) {
  $DataRoot = Join-Path $env:LOCALAPPDATA "Humungousaur"
}

function Write-Step([string]$Message) {
  if (-not $Quiet) {
    Write-Host $Message
  }
}

function Test-Python312([string]$Command, [string[]]$Arguments) {
  try {
    $Version = & $Command @Arguments -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
      return @{ Command = $Command; Arguments = $Arguments; Version = $Version }
    }
  }
  catch {
  }
  return $null
}

function Find-Python312 {
  $Candidates = @(
    @{ Command = "py"; Arguments = @("-3.12") },
    @{ Command = "python"; Arguments = @() },
    @{ Command = "python3"; Arguments = @() }
  )
  foreach ($Candidate in $Candidates) {
    $Python = Test-Python312 $Candidate.Command $Candidate.Arguments
    if ($null -ne $Python) {
      return $Python
    }
  }
  return $null
}

if (-not (Test-Path $PayloadApp)) {
  throw "Installer payload is missing app folder: $PayloadApp"
}
if (-not (Test-Path $PayloadRuntime)) {
  throw "Installer payload is missing runtime-source folder: $PayloadRuntime"
}

$Python = Find-Python312
if ($null -eq $Python -and $InstallPythonWithWinget) {
  $Winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($null -eq $Winget) {
    throw "Python 3.12+ is missing and winget is not available. Install Python 3.12+, then rerun this installer."
  }
  Write-Step "Installing Python 3.12 with winget..."
  & $Winget.Source install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
  $Python = Find-Python312
}
if ($null -eq $Python) {
  throw "Python 3.12+ is required. Install it, or rerun with -InstallPythonWithWinget."
}

$AppInstallDir = Join-Path $InstallRoot "app"
$RuntimeSourceDir = Join-Path $DataRoot "runtime-source"
New-Item -ItemType Directory -Force -Path $InstallRoot, $DataRoot | Out-Null

Write-Step "Installing app to $AppInstallDir"
if (Test-Path $AppInstallDir) {
  Remove-Item -Path $AppInstallDir -Recurse -Force
}
Copy-Item -Path $PayloadApp -Destination $AppInstallDir -Recurse -Force

Write-Step "Installing runtime source to $RuntimeSourceDir"
if (Test-Path $RuntimeSourceDir) {
  Remove-Item -Path $RuntimeSourceDir -Recurse -Force
}
Copy-Item -Path $PayloadRuntime -Destination $RuntimeSourceDir -Recurse -Force

$Bootstrap = Join-Path $RuntimeSourceDir "script\bootstrap_runtime.py"
$BootstrapArgs = @($Bootstrap, "--source", $RuntimeSourceDir, "--data-root", $DataRoot)
if ($SkipPlaywright) {
  $BootstrapArgs += "--skip-playwright"
}
if ($Quiet) {
  $BootstrapArgs += "--quiet"
}
Write-Step "Bootstrapping Python runtime..."
& $Python.Command @($Python.Arguments + $BootstrapArgs)
if ($LASTEXITCODE -ne 0) {
  throw "Runtime bootstrap failed with exit code $LASTEXITCODE"
}

$AppExe = Get-ChildItem -Path $AppInstallDir -Filter "Humungousaur.App.exe" -Recurse | Select-Object -First 1
if ($null -eq $AppExe) {
  throw "Installed app is missing Humungousaur.App.exe"
}

$ShortcutTargets = @(
  Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Humungousaur.lnk",
  Join-Path ([Environment]::GetFolderPath("Desktop")) "Humungousaur.lnk"
)
$Shell = New-Object -ComObject WScript.Shell
foreach ($ShortcutPath in $ShortcutTargets) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ShortcutPath) | Out-Null
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $AppExe.FullName
  $Shortcut.WorkingDirectory = $AppExe.DirectoryName
  $Shortcut.IconLocation = $AppExe.FullName
  $Shortcut.Save()
}

$StatusPath = Join-Path $DataRoot "install-status.json"
$Status = @{
  ok = $true
  created_at = [DateTimeOffset]::UtcNow.ToString("O")
  install_root = $InstallRoot
  data_root = $DataRoot
  app_exe = $AppExe.FullName
  python_command = $Python.Command
  python_version = $Python.Version
}
$Status | ConvertTo-Json -Depth 5 | Set-Content -Path $StatusPath -Encoding utf8
Write-Step "Humungousaur installed. Launch it from the Start Menu or Desktop shortcut."
