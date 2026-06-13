$ErrorActionPreference = 'Stop'

$packageName = 'humungousaur'
$url64 = 'https://github.com/bhaveshpabnani/Humungousaur/releases/download/v0.1.4/Humungousaur-Windows-Setup.exe'
$checksum64 = '6232faf02acafe1fe66560e728ccb05add8956d775636397b4d0cde8500fb2a1'

$packageArgs = @{
  packageName    = $packageName
  fileType       = 'exe'
  url64bit       = $url64
  checksum64     = $checksum64
  checksumType64 = 'sha256'
  silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
  validExitCodes = @(0, 3010, 1641)
}

Install-ChocolateyPackage @packageArgs
