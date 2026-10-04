param(
    [string]$ProjectName = 'modelmedic-m2-verified',
    [string]$ApiPort = '18005',
    [string]$FrontendPort = '15178'
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/m1-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'Regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
& $docker compose -p $ProjectName -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.smoke_m2
if ($LASTEXITCODE -ne 0) { throw 'M2 Compose workflow smoke failed.' }
& $docker compose -p $ProjectName exec -T frontend npm audit --audit-level=low
if ($LASTEXITCODE -ne 0) { throw 'Frontend audit failed.' }
Write-Output 'PASS: M2 executable gate. Review privacy, locked specifications, UI and Git before committing.'
