param(
    [string]$ProjectName = 'modelmedic-m3-verified',
    [string]$ApiPort = '18006',
    [string]$FrontendPort = '15179'
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/m2-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'M0/M1/M2 regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
& $docker compose -p $ProjectName -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.smoke_m3
if ($LASTEXITCODE -ne 0) { throw 'M3 Compose workflow smoke failed.' }
Write-Output 'PASS: M3 executable gate. Review browser flow, privacy, locked specifications and Git before committing.'
