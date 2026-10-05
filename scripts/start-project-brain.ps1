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

    $taskName = "RepoBrain-Local-$Port"
    $psExecutable = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    function Quote-PSLiteral([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
    $argumentList = ($Arguments | ForEach-Object { Quote-PSLiteral $_ }) -join ','
    $workerInvocation = '& ' + (Quote-PSLiteral $workerPath) +
        ' -PythonExecutable ' + (Quote-PSLiteral $Executable) +
        ' -Arguments @(' + $argumentList + ')' +
        ' -ProjectDirectory ' + (Quote-PSLiteral $projectDirectory) +
        ' -StdoutPath ' + (Quote-PSLiteral $stdoutPath) +
        ' -StderrPath ' + (Quote-PSLiteral $stderrPath) +
        ' -PidPath ' + (Quote-PSLiteral $pidPath) + ' -Port ' + $Port
    $encodedInvocation = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($workerInvocation))
    $scheduler = New-Object -ComObject Schedule.Service
    $scheduler.Connect()
    $task = $scheduler.NewTask(0)
    $task.RegistrationInfo.Description = 'Local Repo Brain server. Started manually; no recurring schedule.'
    $task.Principal.LogonType = 3
    $task.Principal.RunLevel = 0
    $task.Settings.ExecutionTimeLimit = 'PT0S'
    $task.Settings.DisallowStartIfOnBatteries = $false
    $task.Settings.StopIfGoingOnBatteries = $false
    $task.Settings.Hidden = $true
    $action = $task.Actions.Create(0)
    $action.Path = $psExecutable
    $action.Arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand $encodedInvocation"
    $action.WorkingDirectory = $projectDirectory
    $registered = $scheduler.GetFolder('\').RegisterTaskDefinition(
        $taskName, $task, 6, [System.Security.Principal.WindowsIdentity]::GetCurrent().Name, $null, 3
    )
    $registered.Run($null) | Out-Null
    $workerProcessId = $taskName
    Write-Host "Starting Project Brain in the background (worker PID $workerProcessId)."

    $deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($registered.State -eq 3 -and (Test-Path -LiteralPath $stderrPath)) {
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
