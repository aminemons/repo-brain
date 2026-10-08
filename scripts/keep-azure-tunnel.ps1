param([Parameter(Mandatory = $true)][string]$ConnectionFile)

$ErrorActionPreference = 'Stop'
$connection = Get-Content -LiteralPath $ConnectionFile -Raw | ConvertFrom-Json
$port = [int]$connection.localPort
if ($port -lt 1 -or $port -gt 65535) { throw 'Invalid local port.' }

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 5
    if ($health.status -eq 'ok') { return }
} catch { }

# Do not replace a listener belonging to another application.
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
foreach ($listener in $listeners) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($process.Name -ne 'ssh.exe' -or
        -not $process.CommandLine.Contains([string]$connection.identityFile) -or
        -not $process.CommandLine.Contains([string]$connection.serverAddress)) {
        throw "Local port $port is used by another application."
    }
    Stop-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
}

# Dynamic home IPs must still use an individual /32 SSH rule.
$currentIp = ([string](Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 15)).Trim()
$parsedIp = $null
if (-not [Net.IPAddress]::TryParse($currentIp, [ref]$parsedIp) -or
    $parsedIp.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
    throw 'Could not determine the current IPv4 address.'
}
& $connection.azureCliPython -m azure.cli network nsg rule update `
    --resource-group $connection.resourceGroup --nsg-name $connection.nsgName `
    --name $connection.ruleName --source-address-prefixes "$currentIp/32" `
    --only-show-errors --output none
if ($LASTEXITCODE -ne 0) { throw 'Could not refresh the Azure SSH rule. Check Azure login.' }

foreach ($path in @($connection.identityFile, $connection.knownHostsFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or $path.Contains('"')) {
        throw 'Missing or invalid SSH key or known-hosts path.'
    }
}
if ($connection.serverAddress -notmatch '^[a-zA-Z0-9.-]+$' -or
    $connection.userName -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid SSH destination.' }
$sshArguments = @(
    '-N', '-L', "127.0.0.1:${port}:127.0.0.1:8000",
    '-i', ('"' + $connection.identityFile + '"'),
    '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15',
    '-o', 'ServerAliveCountMax=2', '-o', 'StrictHostKeyChecking=yes',
    '-o', ('"UserKnownHostsFile=' + $connection.knownHostsFile + '"'),
    "$($connection.userName)@$($connection.serverAddress)"
)
Start-Process -FilePath ssh.exe -ArgumentList $sshArguments -WindowStyle Hidden

for ($attempt = 0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        if ($health.status -eq 'ok') { Write-Output 'Azure tunnel is ready.'; return }
    } catch { }
}
throw 'SSH started but the application is unreachable. Check server health and SSH access.'
