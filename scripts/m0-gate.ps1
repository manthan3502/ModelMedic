param(
    [string]$ProjectName = 'modelmedic-m0-gate',
    [string]$ApiPort = '18000',
    [string]$FrontendPort = '15173'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else {
    $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    if (-not (Test-Path -LiteralPath $docker)) { throw 'Docker CLI is not available.' }
}
function Invoke-Docker {
    & $docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $($args -join ' ')" }
}
$env:MM_CODE_VERSION = (git rev-parse HEAD).Trim()
$env:MM_CODE_DIRTY = if (git status --porcelain) { 'true' } else { 'false' }
$env:API_PORT = $ApiPort
$env:FRONTEND_PORT = $FrontendPort
$composeArgs = @('compose', '-p', $ProjectName, '-f', 'compose.yaml')
$testArgs = $composeArgs + @('-f', 'scripts/compose.test.yaml')
Invoke-Docker @composeArgs config --quiet
Invoke-Docker @composeArgs build
Invoke-Docker @composeArgs up -d --wait postgres
# One explicit migration step. API/worker never migrate on startup.
Invoke-Docker @composeArgs run --rm --no-deps api alembic upgrade head
# Workers expose PostgreSQL heartbeats, not an HTTP healthcheck. Some Compose
# versions reject --wait for an explicitly disabled image healthcheck; the real
# heartbeat and executed dummy job below remain mandatory worker readiness checks.
Invoke-Docker @composeArgs up -d worker
Invoke-Docker @composeArgs up -d --wait api frontend
Invoke-Docker build --target test --build-arg "CODE_VERSION=$env:MM_CODE_VERSION" --build-arg "CODE_DIRTY=$env:MM_CODE_DIRTY" -t modelmedic-backend:test .
Invoke-Docker @testArgs run --rm --no-deps -T api ruff check --no-cache backend migrations scripts
Invoke-Docker @testArgs run --rm --no-deps -T api ruff format --check --no-cache backend migrations scripts
Invoke-Docker @testArgs run --rm --no-deps -T api mypy --cache-dir /tmp/mypy
Invoke-Docker @testArgs run --rm --no-deps -T api pytest -q -p no:cacheprovider
Invoke-Docker @composeArgs exec -T frontend npm run lint
Invoke-Docker @composeArgs exec -T frontend npm run typecheck
Invoke-Docker @composeArgs exec -T frontend npm run test
Invoke-Docker @composeArgs exec -T frontend npm run build
Invoke-Docker @testArgs run --rm --no-deps -T api python -m scripts.smoke
Invoke-Docker @composeArgs ps
Write-Output 'PASS: M0 executable gate. Review privacy, locked specs and Git separately before committing.'
