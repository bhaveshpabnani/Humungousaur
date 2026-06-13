$ErrorActionPreference = 'Stop'

$packageName = 'humungousaur'
$uninstall = Get-UninstallRegistryKey -SoftwareName 'Humungousaur*' | Select-Object -First 1

if ($null -eq $uninstall) {
  Write-Warning 'Humungousaur uninstall entry was not found.'
  return
}

$uninstallString = $uninstall.UninstallString
if ([string]::IsNullOrWhiteSpace($uninstallString)) {
  Write-Warning 'Humungousaur uninstall command was empty.'
  return
}

$file = $uninstallString.Trim('"')
if ($file -match '^\s*"([^"]+)"') {
  $file = $Matches[1]
}

$packageArgs = @{
  packageName    = $packageName
  fileType       = 'exe'
  file           = $file
  silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
  validExitCodes = @(0, 3010, 1605, 1614, 1641)
}

Uninstall-ChocolateyPackage @packageArgs
