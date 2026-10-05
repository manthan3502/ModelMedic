param(
    [string]$ProjectName = 'modelmedic-m6-verified',
    [string]$ApiPort = '18010',
    [string]$FrontendPort = '15183'
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/m5-gate.ps1" -ProjectName $ProjectName -ApiPort $ApiPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -ne 0) { throw 'M0–M5 regression gate failed.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $docker = $dockerCommand.Source }
else { $docker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
$stack = @('compose', '-p', $ProjectName, '-f', 'compose.yaml')
$testStack = $stack + @('-f', 'scripts/compose.test.yaml')
$demoStack = $stack + @('-f', 'scripts/compose.demo.yaml')
$demoTest = $demoStack + @('-f', 'scripts/compose.test.yaml')
function Invoke-CheckedDocker {
    & $docker @args
    if ($LASTEXITCODE -ne 0) { throw 'M6 Docker verification command failed.' }
}
Invoke-CheckedDocker @stack exec -T frontend npm audit --audit-level=low
Invoke-CheckedDocker @testStack run --rm --no-deps -T api python -m scripts.seed_demo ensure
Invoke-CheckedDocker @testStack run --rm --no-deps -T api python -m scripts.seed_demo verify
Invoke-CheckedDocker @stack stop worker
Invoke-CheckedDocker @demoStack config --quiet
Invoke-CheckedDocker @demoStack up -d --wait postgres api frontend
Invoke-CheckedDocker @demoTest run --rm --no-deps -T api python -m scripts.smoke_m6
Invoke-CheckedDocker @demoStack restart postgres api frontend
Invoke-CheckedDocker @demoStack up -d --wait postgres api frontend
Invoke-CheckedDocker @demoTest run --rm --no-deps -T api python -m scripts.smoke_m6
Invoke-CheckedDocker @demoStack ps
Write-Output 'PASS: M6 executable Full/Demo gates and M0–M5 regressions. Browser, accessibility, print, privacy, locked specs and diff remain mandatory before commit.'
