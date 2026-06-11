$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Project = Join-Path $Root "apps/windows/Humungousaur.App/Humungousaur.App.csproj"
$PublishDir = Join-Path $Root "artifacts/package/windows/publish"
$ReleaseDir = Join-Path $Root "artifacts/release"
$ZipPath = Join-Path $ReleaseDir "Humungousaur-Windows.zip"
$InstallerExePath = Join-Path $ReleaseDir "Humungousaur-Windows-Setup.exe"
$ChecksumPath = Join-Path $ReleaseDir "checksums.txt"
$InstallDoc = Join-Path $PublishDir "INSTALL.txt"
$InstallerRoot = Join-Path $Root "artifacts/package/windows/installer"
$InstallerScriptPath = Join-Path $Root "artifacts/package/windows/Humungousaur-Windows.iss"
$IsWindowsPlatform = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
if (-not $IsWindowsPlatform) {
  throw "Windows packaging must run on Windows because Humungousaur.App targets net8.0-windows and WinUI. Use the GitHub Actions windows-latest release job or a local Windows machine."
}
$Dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if ($null -eq $Dotnet) {
  throw ".NET SDK is required to package Humungousaur-Windows.zip. Install .NET 8 SDK or use the GitHub Actions windows-latest release job."
}
$ShouldSign = $env:HUMUNGOUSAUR_WINDOWS_SIGN -eq "1"
$SignCertPath = $env:HUMUNGOUSAUR_WINDOWS_CERT_PATH
$SignCertPassword = $env:HUMUNGOUSAUR_WINDOWS_CERT_PASSWORD
$TimestampUrl = if ($env:HUMUNGOUSAUR_WINDOWS_TIMESTAMP_URL) { $env:HUMUNGOUSAUR_WINDOWS_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
$PyprojectText = Get-Content -Raw -Path (Join-Path $Root "pyproject.toml")
if ($PyprojectText -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
  throw "Unable to read project.version from pyproject.toml"
}
$ProjectVersion = $Matches[1]
if ($ProjectVersion -notmatch '^(\d+)\.(\d+)\.(\d+)') {
  throw "Project version must start with major.minor.patch for Windows metadata: $ProjectVersion"
}
$WindowsFileVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"

if (Test-Path $PublishDir) {
  Remove-Item -Path $PublishDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $PublishDir, $ReleaseDir | Out-Null

function Copy-RuntimeSource {
  param([string]$Target)
  if (Test-Path $Target) {
    Remove-Item -Path $Target -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $Target "script") | Out-Null
  Copy-Item -Path (Join-Path $Root "humungousaur") -Destination $Target -Recurse -Force
  Copy-Item -Path (Join-Path $Root "skills") -Destination $Target -Recurse -Force
  Copy-Item -Path (Join-Path $Root "browser_extensions") -Destination $Target -Recurse -Force
  Copy-Item -Path (Join-Path $Root "script/bootstrap_runtime.py") -Destination (Join-Path $Target "script/bootstrap_runtime.py") -Force
  Copy-Item -Path (Join-Path $Root "pyproject.toml"), (Join-Path $Root "README.md"), (Join-Path $Root "LICENSE") -Destination $Target -Force
  Get-ChildItem -Path $Target -Recurse -Force -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
  Get-ChildItem -Path $Target -Recurse -Force -Include "*.pyc", ".DS_Store" | Remove-Item -Force
}

function Find-InnoSetupCompiler {
  $Command = Get-Command iscc.exe -ErrorAction SilentlyContinue
  if ($null -ne $Command) {
    return $Command.Source
  }
  $Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
  )
  foreach ($Candidate in $Candidates) {
    if (Test-Path $Candidate) {
      return $Candidate
    }
  }
  throw "Inno Setup 6 is required to build Humungousaur-Windows-Setup.exe. Install it with: choco install innosetup -y"
}

& $Dotnet.Source publish $Project `
  -c Release `
  -r win-x64 `
  -p:Version=$ProjectVersion `
  -p:AssemblyVersion=$WindowsFileVersion `
  -p:FileVersion=$WindowsFileVersion `
  -p:InformationalVersion=$ProjectVersion `
  -p:WindowsAppSDKSelfContained=true `
  -p:WindowsPackageType=None `
  -o $PublishDir

@"
Humungousaur Windows setup
Version: $ProjectVersion

Recommended public install:
1. Run Humungousaur-Windows-Setup.exe.
2. Keep "Bootstrap Python runtime" selected to create or repair the local venv, install dependencies, install Playwright Chromium, and write install status.
3. If Python 3.12+ is missing, select "Install Python 3.12 with winget" or install Python manually and rerun the installer.
4. The installer copies the app, installs the bundled runtime source, creates Start Menu/Desktop shortcuts, and registers a normal Windows uninstaller.
5. Developer source installs can still use:
   python -m pip install -e ".[browser,pdf,ocr,office]"
6. Start Humungousaur.App.exe, then start the runtime from the app controls, or run:
   python -m humungousaur serve --workspace <repo-root> --port 8765
7. Open Settings in the app and confirm:
   - workspace path: your project folder or home folder
   - Python path: %LOCALAPPDATA%\Humungousaur\runtime\.venv\Scripts\python.exe, python, or <repo-root>\.venv\Scripts\python.exe
   - API URL: http://127.0.0.1:8765
   - provider/model: openai, groq, ollama, grok, or local-openai
   - model keys: OPENAI_API_KEY, GROQ_API_KEY, XAI_API_KEY, OLLAMA_API_KEY, or LOCAL_LLM_API_KEY
   - voice keys: DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID
   - channel keys required by your enabled channel setup
5. Use the status controls to verify API, model, tools, runs, channels, voice, autonomy, and approvals before sending a task.

Release validation command:
python -m unittest discover -v

Package validation command:
.\script\verify_windows_package.ps1
"@ | Set-Content -Path $InstallDoc -Encoding utf8

if ($ShouldSign) {
  if ([string]::IsNullOrWhiteSpace($SignCertPath) -or -not (Test-Path $SignCertPath)) {
    throw "HUMUNGOUSAUR_WINDOWS_SIGN=1 requires HUMUNGOUSAUR_WINDOWS_CERT_PATH to point at a PFX certificate."
  }
  if ([string]::IsNullOrWhiteSpace($SignCertPassword)) {
    throw "HUMUNGOUSAUR_WINDOWS_SIGN=1 requires HUMUNGOUSAUR_WINDOWS_CERT_PASSWORD."
  }
  $Signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($null -eq $Signtool) {
    throw "signtool.exe is required for signed Windows release builds."
  }
  $SignableBinaries = Get-ChildItem -Path $PublishDir -Recurse -File |
    Where-Object { $_.Extension -eq ".exe" -or ($_.Extension -eq ".dll" -and $_.Name -like "Humungousaur*.dll") }
  if ($SignableBinaries.Count -eq 0) {
    throw "No Humungousaur Windows binaries were found to sign."
  }
  $SignableBinaries | ForEach-Object {
    & $Signtool.Source sign `
      /fd SHA256 `
      /td SHA256 `
      /tr $TimestampUrl `
      /f $SignCertPath `
      /p $SignCertPassword `
      $_.FullName
    & $Signtool.Source verify /pa $_.FullName
  }
} else {
  Write-Host "Skipping Windows Authenticode signing; set HUMUNGOUSAUR_WINDOWS_SIGN=1 for signed release builds."
}

if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}
if (Test-Path $InstallerRoot) {
  Remove-Item -Path $InstallerRoot -Recurse -Force
}
if (Test-Path $InstallerExePath) {
  Remove-Item $InstallerExePath -Force
}

Compress-Archive -Path (Join-Path $PublishDir "*") -DestinationPath $ZipPath -Force

New-Item -ItemType Directory -Force -Path (Join-Path $InstallerRoot "app"), (Join-Path $InstallerRoot "runtime-source") | Out-Null
Copy-Item -Path (Join-Path $PublishDir "*") -Destination (Join-Path $InstallerRoot "app") -Recurse -Force
Copy-RuntimeSource -Target (Join-Path $InstallerRoot "runtime-source")
@"
param(
  [switch]`$InstallPythonWithWinget,
  [switch]`$SkipPlaywright
)

`$ErrorActionPreference = "Stop"
`$DataRoot = Join-Path `$env:LOCALAPPDATA "Humungousaur"
`$RuntimeSource = Join-Path `$DataRoot "runtime-source"
`$LogPath = Join-Path `$DataRoot "install.log"
New-Item -ItemType Directory -Force -Path `$DataRoot | Out-Null

function Test-Python312([string]`$Command, [string[]]`$Arguments) {
  try {
    `$Version = & `$Command @Arguments -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>`$null
    if (`$LASTEXITCODE -eq 0) {
      return @{ Command = `$Command; Arguments = `$Arguments; Version = `$Version }
    }
  } catch {}
  return `$null
}

function Find-Python312 {
  foreach (`$Candidate in @(
    @{ Command = "py"; Arguments = @("-3.12") },
    @{ Command = "python"; Arguments = @() },
    @{ Command = "python3"; Arguments = @() }
  )) {
    `$Python = Test-Python312 `$Candidate.Command `$Candidate.Arguments
    if (`$null -ne `$Python) { return `$Python }
  }
  return `$null
}

`$Python = Find-Python312
if (`$null -eq `$Python -and `$InstallPythonWithWinget) {
  `$Winget = Get-Command winget -ErrorAction SilentlyContinue
  if (`$null -eq `$Winget) {
    throw "Python 3.12+ is missing and winget is not available. Install Python 3.12+, then rerun Humungousaur setup."
  }
  & `$Winget.Source install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
  `$Python = Find-Python312
}
if (`$null -eq `$Python) {
  throw "Python 3.12+ is required. Install Python 3.12+ or rerun setup with the winget task selected."
}

`$Bootstrap = Join-Path `$RuntimeSource "script\bootstrap_runtime.py"
`$Args = @(`$Bootstrap, "--source", `$RuntimeSource, "--data-root", `$DataRoot, "--quiet")
if (`$SkipPlaywright) { `$Args += "--skip-playwright" }
& `$Python.Command @(`$Python.Arguments + `$Args) *>> `$LogPath
if (`$LASTEXITCODE -ne 0) {
  throw "Humungousaur runtime bootstrap failed with exit code `$LASTEXITCODE. See `$LogPath."
}
"@ | Set-Content -Path (Join-Path $InstallerRoot "Bootstrap-Humungousaur.ps1") -Encoding utf8
@"
Humungousaur Windows installer executable
Version: $ProjectVersion

Run:
  Humungousaur-Windows-Setup.exe

This installer copies the WinUI app, installs the bundled runtime source, creates Start Menu/Desktop shortcuts, registers an uninstaller, and runs Bootstrap-Humungousaur.ps1 to create or repair the local Python runtime.
"@ | Set-Content -Path (Join-Path $InstallerRoot "README.txt") -Encoding utf8

$EscapedInstallerRoot = $InstallerRoot.Replace("\", "\\")
$EscapedReleaseDir = $ReleaseDir.Replace("\", "\\")
$InstallerIcon = Join-Path $Root "apps/windows/Humungousaur.App/Assets/Humungousaur.ico"
$EscapedInstallerIcon = $InstallerIcon.Replace("\", "\\")
@"
#define AppName "Humungousaur"
#define AppVersion "$ProjectVersion"
#define PayloadRoot "$EscapedInstallerRoot"

[Setup]
AppId={{9A137BA2-1D8B-4CF6-BA7B-9C5E1D2B52F1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Humungousaur
DefaultDirName={localappdata}\Programs\Humungousaur
DefaultGroupName=Humungousaur
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=$EscapedReleaseDir
OutputBaseFilename=Humungousaur-Windows-Setup
SetupIconFile=$EscapedInstallerIcon
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\app\Humungousaur.App.exe
VersionInfoVersion=$WindowsFileVersion
VersionInfoProductVersion=$ProjectVersion
VersionInfoCompany=Humungousaur
VersionInfoDescription=Humungousaur Windows Installer

[Tasks]
Name: "bootstrap"; Description: "Bootstrap Python runtime"; GroupDescription: "Runtime setup:"; Flags: checkedonce
Name: "installpython"; Description: "Install Python 3.12 with winget if missing"; GroupDescription: "Runtime setup:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadRoot}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\runtime-source\*"; DestDir: "{localappdata}\Humungousaur\runtime-source"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\Bootstrap-Humungousaur.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#PayloadRoot}\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Humungousaur"; Filename: "{app}\app\Humungousaur.App.exe"; WorkingDir: "{app}\app"
Name: "{autodesktop}\Humungousaur"; Filename: "{app}\app\Humungousaur.App.exe"; WorkingDir: "{app}\app"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\Bootstrap-Humungousaur.ps1"""; WorkingDir: "{app}"; StatusMsg: "Bootstrapping Humungousaur runtime..."; Flags: runhidden waituntilterminated; Tasks: bootstrap and not installpython
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\Bootstrap-Humungousaur.ps1"" -InstallPythonWithWinget"; WorkingDir: "{app}"; StatusMsg: "Installing Python if needed and bootstrapping Humungousaur runtime..."; Flags: runhidden waituntilterminated; Tasks: bootstrap and installpython
"@ | Set-Content -Path $InstallerScriptPath -Encoding utf8

$Iscc = Find-InnoSetupCompiler
& $Iscc $InstallerScriptPath
if (-not (Test-Path $InstallerExePath)) {
  throw "Inno Setup did not create $InstallerExePath"
}

if ($ShouldSign) {
  & $Signtool.Source sign `
    /fd SHA256 `
    /td SHA256 `
    /tr $TimestampUrl `
    /f $SignCertPath `
    /p $SignCertPassword `
    $InstallerExePath
  & $Signtool.Source verify /pa $InstallerExePath
}

$ChecksumLines = Get-ChildItem -Path $ReleaseDir -File |
  Where-Object { $_.Name -in @("Humungousaur-Windows-Setup.exe", "Humungousaur-Windows.zip") } |
  Sort-Object Name |
  ForEach-Object {
    $Hash = Get-FileHash -Algorithm SHA256 $_.FullName
    "$($Hash.Hash.ToLower())  $($_.Name)"
  }
$ChecksumLines | Set-Content -Path $ChecksumPath -Encoding utf8

Write-Host "Created $ZipPath"
Write-Host "Created $InstallerExePath"
