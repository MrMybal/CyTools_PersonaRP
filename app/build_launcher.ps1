$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'build_launcher.cmd')
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }
