param(
    [string]$ProjectName = 'modelmedic-m1-verified',
    [string]$ApiPort = '18004',
    [string]$FrontendPort = '15177'
)
$ErrorActionPreference = 'Stop'
# The complete M0 gate now runs all backend/frontend tests, including M1 tests.
& "$PSScriptRoot/m0-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'Regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
& $docker compose -p $ProjectName -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.smoke_m1
if ($LASTEXITCODE -ne 0) { throw 'M1 Compose workflow smoke failed.' }
Write-Output 'PASS: M1 executable gate and complete M0 regressions. Review privacy, locked specs and Git separately.'
