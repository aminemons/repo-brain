param(
    [switch]$Setup,
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [switch]$Background,
    [string]$PythonExecutable,
    [ValidateRange(10, 180)][int]$HealthTimeoutSeconds = 45
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$runDirectory = Join-Path $projectDirectory '.run'
$stdoutPath = Join-Path $runDirectory "project-brain-$Port.out.log"
$stderrPath = Join-Path $runDirectory "project-brain-$Port.err.log"
$pidPath = Join-Path $runDirectory "project-brain-$Port.pid"

function Get-SafeLogTail([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    return @(
        Get-Content -LiteralPath $Path -Tail 18 -ErrorAction SilentlyContinue |
            ForEach-Object {
                $_ -replace '(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{12,}', '$1[REDACTED]' `
                   -replace '\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b', '[REDACTED]' `
                   -replace '(?i)(api[_-]?key\s*[:=]\s*)\S+', '$1[REDACTED]'
            }
    )
}

function Start-BackgroundServer {
    param([string]$Executable, [string[]]$Arguments)

    $healthy = $false
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($response.StatusCode -eq 200 -and ($response.Content | ConvertFrom-Json).status -eq 'ok') {
            $healthy = $true
        }
    }
    catch { }
    if ($healthy) {
        Write-Host "Project Brain is already healthy at http://127.0.0.1:$Port/api/health"
        return
    }

    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $workerPath = Join-Path $runDirectory "project-brain-$Port-worker.ps1"
    $workerSource = @'
param(
    [string]$PythonExecutable,
    [string[]]$Arguments,
    [string]$ProjectDirectory,
    [string]$StdoutPath,
    [string]$StderrPath,
    [string]$PidPath,
    [int]$Port
)
$ErrorActionPreference = 'Stop'
$process = Start-Process -FilePath $PythonExecutable -ArgumentList $Arguments `
    -WorkingDirectory $ProjectDirectory -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath
Set-Content -LiteralPath $PidPath -Value $process.Id -NoNewline -Encoding ascii
$process.WaitForExit()
exit $process.ExitCode
'@
    Set-Content -LiteralPath $workerPath -Value $workerSource -Encoding utf8

    $psExecutable = if ($PSHOME -and (Test-Path -LiteralPath (Join-Path $PSHOME 'pwsh.exe'))) {
        Join-Path $PSHOME 'pwsh.exe'
    }
    else {
        Join-Path $PSHOME 'powershell.exe'
    }
    if (-not (Test-Path -LiteralPath $psExecutable -PathType Leaf)) {
        throw 'Could not find PowerShell to create the detached background worker.'
    }
    $workerInvocation = @(
        '&', (ConvertTo-Json -InputObject $workerPath -Compress),
        '-PythonExecutable', (ConvertTo-Json -InputObject $Executable -Compress),
        '-Arguments', "@($((ConvertTo-Json -InputObject $Arguments -Compress).TrimStart('[').TrimEnd(']')))",
        '-ProjectDirectory', (ConvertTo-Json -InputObject $projectDirectory -Compress),
        '-StdoutPath', (ConvertTo-Json -InputObject $stdoutPath -Compress),
        '-StderrPath', (ConvertTo-Json -InputObject $stderrPath -Compress),
        '-PidPath', (ConvertTo-Json -InputObject $pidPath -Compress),
        '-Port', "$Port"
    ) -join ' '
    $encodedInvocation = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($workerInvocation))
    $commandLine = "`"$psExecutable`" -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand $encodedInvocation"
    try {
        $created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
            CommandLine = $commandLine
            CurrentDirectory = $projectDirectory
        }
        if ($created.ReturnValue -ne 0 -or -not $created.ProcessId) {
            throw "Windows process creation returned code $($created.ReturnValue)."
        }
        $workerProcessId = [int]$created.ProcessId
    }
    catch {
        throw "Could not create the detached Project Brain worker. Ensure Windows CIM process creation is available. $($_.Exception.Message)"
    }
    Write-Host "Starting Project Brain in the background (worker PID $workerProcessId)."

    $deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $worker = Get-Process -Id $workerProcessId -ErrorAction SilentlyContinue
        if (-not $worker) {
            $tail = @(Get-SafeLogTail $stderrPath) + @(Get-SafeLogTail $stdoutPath)
            $details = if ($tail.Count) { "`n$($tail -join "`n")" } else { '' }
            throw "Project Brain exited during startup. Logs: $stderrPath and $stdoutPath$details"
        }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200 -and ($response.Content | ConvertFrom-Json).status -eq 'ok') {
                $serverId = if (Test-Path -LiteralPath $pidPath) {
                    (Get-Content -LiteralPath $pidPath -Raw).Trim()
                }
                else { 'starting' }
                Write-Host "Project Brain is healthy at http://127.0.0.1:$Port"
                Write-Host "Server PID: $serverId (worker PID $workerProcessId)"
                Write-Host "PID file: $pidPath"
                Write-Host "Logs: $stdoutPath and $stderrPath"
                return
            }
        }
        catch { }
        Start-Sleep -Milliseconds 750
    }

    $tail = @(Get-SafeLogTail $stderrPath) + @(Get-SafeLogTail $stdoutPath)
    $details = if ($tail.Count) { "`n$($tail -join "`n")" } else { '' }
    throw "Project Brain did not report healthy within $HealthTimeoutSeconds seconds. It may still be starting. Worker PID $workerProcessId; logs: $stderrPath and $stdoutPath$details"
}

Push-Location -LiteralPath $projectDirectory
try {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if (($Setup -or -not $Background -or (-not $PythonExecutable -and -not (Test-Path -LiteralPath (Join-Path $projectDirectory '.venv\Scripts\python.exe')))) -and -not $uvCommand) {
        throw 'Install uv, then rerun this launcher. Manual setup is documented in README.md.'
    }
    if ($Setup) {
        $env:CODEWIKI_SKIP_FRONTEND_BUILD = '1'
        & uv sync --locked --python 3.12 --extra docs
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency setup failed.' }
        & npm.cmd --prefix frontend ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency setup failed.' }
        & npm.cmd --prefix frontend run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend compilation failed.' }
    }
    if (-not (Test-Path -LiteralPath 'backend/app/static/index.html')) {
        throw 'Compile the frontend first by running this script with -Setup.'
    }

    if ($Background) {
        if ($PythonExecutable) {
            if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
                throw "Python executable not found: $PythonExecutable"
            }
            $pythonPath = (Resolve-Path -LiteralPath $PythonExecutable).Path
        }
        else {
            $projectVenvPython = Join-Path $projectDirectory '.venv\Scripts\python.exe'
            if (Test-Path -LiteralPath $projectVenvPython -PathType Leaf) {
                $pythonPath = (Resolve-Path -LiteralPath $projectVenvPython).Path
            }
        }

        if ($pythonPath) {
            Start-BackgroundServer -Executable $pythonPath -Arguments @(
                '-u', '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', "$Port"
            )
        }
        else {
            Start-BackgroundServer -Executable $uvCommand.Source -Arguments @(
                'run', '--locked', '--extra', 'docs', 'python', '-u', '-m', 'uvicorn',
                'backend.app.main:app', '--host', '127.0.0.1', '--port', "$Port"
            )
        }
        return
    }

    Write-Host "Project Brain: http://127.0.0.1:$Port"
    & uv run --locked --extra docs python -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Project Brain exited with an error.' }
}
finally {
    Pop-Location
}
