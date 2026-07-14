$ErrorActionPreference = "Continue"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $Root ".runtime"

function Write-Step($Message) {
    Write-Host "[sensor-platform] $Message"
}

function Stop-ProcessTree($ProcessId) {
    if (-not $ProcessId) {
        return
    }
    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $ProcessId }
    foreach ($child in $children) {
        Stop-ProcessTree $child.ProcessId
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Step "Stopping pid=$ProcessId ($($process.ProcessName))"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-PidFile($Name) {
    $path = Join-Path $RuntimeDir "$Name.pid"
    if (Test-Path $path) {
        $pidValue = Get-Content $path -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pidValue -match "^\d+$") {
            Stop-ProcessTree ([int]$pidValue)
        }
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

function Stop-PortListener($Port) {
    $pattern = "[:.]$Port\s+.*LISTENING\s+(\d+)"
    $pids = New-Object System.Collections.Generic.HashSet[int]
    foreach ($line in (netstat -ano -p tcp | Select-String -Pattern $pattern)) {
        $text = $line.ToString()
        if ($text -match $pattern) {
            [void]$pids.Add([int]$Matches[1])
        }
    }
    foreach ($pidValue in $pids) {
        Stop-ProcessTree $pidValue
    }
}

Write-Step "Stopping services from pid files..."
Stop-PidFile "greenhouse-hmi"
Stop-PidFile "collector"
Stop-PidFile "frontend"
Stop-PidFile "backend"

Write-Step "Checking known ports..."
Stop-PortListener 8000
Stop-PortListener 2404
Stop-PortListener 5173
Stop-PortListener 8080

Write-Step "Stop finished."
