param(
    [string]$ProjectName = 'modelmedic-m5-verified',
    [string]$ApiPort = '18009',
    [string]$FrontendPort = '15182'
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/m4-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'M0–M4 regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
$stack = @('compose', '-p', $ProjectName, '-f', 'compose.yaml')
$testStack = $stack + @('-f', 'scripts/compose.test.yaml')
function Invoke-CheckedDocker {
    & $docker @args
    if ($LASTEXITCODE -ne 0) { throw 'M5 Docker verification command failed.' }
}
Invoke-CheckedDocker @testStack run --rm --no-deps -T api python -m scripts.smoke_m5 prepare
try {
    Invoke-CheckedDocker @stack restart postgres api worker frontend
    Invoke-CheckedDocker @stack up -d --wait
    Invoke-CheckedDocker @testStack run --rm --no-deps -T api python -m scripts.smoke_m5 verify
    Invoke-CheckedDocker @stack ps
} finally {
    Invoke-CheckedDocker @testStack run --rm --no-deps -T api python -m scripts.smoke_m5 cleanup
}
Write-Output 'PASS: M5 executable gate and M0–M4 regressions. Browser, privacy, diff and locked-spec verification remain separate mandatory checks before commit.'
