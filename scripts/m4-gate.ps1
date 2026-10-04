param(
    [string]$ProjectName = 'modelmedic-m4-verified',
    [string]$ApiPort = '18008',
    [string]$FrontendPort = '15181'
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/m3-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'M0/M1/M2/M3 regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
& $docker compose -p $ProjectName -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.smoke_m4
if ($LASTEXITCODE -ne 0) { throw 'M4 Compose workflow smoke failed.' }
Write-Output 'PASS: M4 executable gate. Review browser flow, privacy, locked specifications and Git before committing.'
