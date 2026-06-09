$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Project = Join-Path $Root "apps/windows/Humungousaur.App/Humungousaur.App.csproj"
$PublishDir = Join-Path $Root "artifacts/package/windows/publish"
$ReleaseDir = Join-Path $Root "artifacts/release"
$ZipPath = Join-Path $ReleaseDir "Humungousaur-Windows.zip"
$ChecksumPath = Join-Path $ReleaseDir "checksums.txt"
$InstallDoc = Join-Path $PublishDir "INSTALL.txt"
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

1. Extract this zip to a local application folder.
2. From the Humungousaur repo, install the runtime into your chosen Python:
   python -m pip install -e ".[browser,pdf,ocr,office]"
3. Start Humungousaur.App.exe, then start the runtime from the app controls, or run:
   python -m humungousaur serve --workspace <repo-root> --port 8765
4. Open Settings in the app and confirm:
   - workspace path: <repo-root>
   - Python path: python or <repo-root>\.venv\Scripts\python.exe
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

Compress-Archive -Path (Join-Path $PublishDir "*") -DestinationPath $ZipPath -Force

$ChecksumLines = Get-ChildItem -Path $ReleaseDir -Filter "*.zip" |
  Sort-Object Name |
  ForEach-Object {
    $Hash = Get-FileHash -Algorithm SHA256 $_.FullName
    "$($Hash.Hash.ToLower())  $($_.Name)"
  }
$ChecksumLines | Set-Content -Path $ChecksumPath -Encoding utf8

Write-Host "Created $ZipPath"
