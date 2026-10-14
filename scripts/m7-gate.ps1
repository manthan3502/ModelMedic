param(
    [string]$ProjectName = 'modelmedic-m7-verified',
    [string]$ApiPort = '18011',
    [string]$FrontendPort = '15184'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
function Invoke-CheckedDocker {
    & $docker @args
    if ($LASTEXITCODE -ne 0) { throw 'M7 Docker verification command failed.' }
}
# A fresh gate must prove empty migrations and clean seed creation, not reuse prior evidence.
$existing = & $docker volume ls --filter "label=com.docker.compose.project=$ProjectName" --format '{{.Name}}'
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker volumes.' }
if ($existing) { throw 'M7 requires a fresh disposable project name with no existing volumes.' }
& "$PSScriptRoot/m6-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'M0–M6 regression gate failed.' }
$stack = @('compose', '-p', $ProjectName, '-f', 'compose.yaml')
$demo = $stack + @('-f', 'scripts/compose.demo.yaml')
$test = $demo + @('-f', 'scripts/compose.test.yaml')
Invoke-CheckedDocker @test run --rm --no-deps -T -e MM_DEPLOYMENT_MODE=full api pytest --require-postgres -m integration -q -p no:cacheprovider
Invoke-CheckedDocker @test run --rm --no-deps -T api alembic check
$production = $demo + @('-f', 'scripts/compose.production-test.yaml')
Invoke-CheckedDocker @production config --quiet
Invoke-CheckedDocker @production build api
Invoke-CheckedDocker run --rm --network none --entrypoint python modelmedic-backend:production-test -c 'import os,tempfile; from pathlib import Path; root=Path(os.environ["MM_ARTIFACT_ROOT"]); assert root==Path("/artifacts") and os.getuid()==10001; f=tempfile.NamedTemporaryFile(dir=root); f.write(b"synthetic scratch probe"); f.close(); print("PASS: production default scratch directory writable by uid 10001")'
Invoke-CheckedDocker @production up -d --wait api
Invoke-CheckedDocker @stack stop frontend
Invoke-CheckedDocker @test run --rm --no-deps -T -e MM_SMOKE_ORIGIN=http://api:8000 api python -m scripts.smoke_production
Invoke-CheckedDocker @test run --rm --no-deps -T -e MM_SMOKE_ORIGIN=http://api:8000 api python -m scripts.smoke_m6
Invoke-CheckedDocker @production restart postgres api
Invoke-CheckedDocker @production up -d --wait postgres api
Invoke-CheckedDocker @test run --rm --no-deps -T -e MM_SMOKE_ORIGIN=http://api:8000 api python -m scripts.seed_demo verify
Invoke-CheckedDocker @test run --rm --no-deps -T -e MM_SMOKE_ORIGIN=http://api:8000 api python -m scripts.smoke_production
Invoke-CheckedDocker @production ps
Write-Output 'PASS: repository M7 automated system checks and M0–M6 regressions. Benchmarks, browser, privacy, CI validation, locked specs and actual live deployment remain mandatory separate gates.'
