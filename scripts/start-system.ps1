param(
    [switch]$InstallDeps,
    [switch]$SkipCollector,
    [switch]$SkipGreenhouse,
    [switch]$SkipMysqlStart
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$CollectorDir = Join-Path $Root "JavaSDKV2.2.2\Demo"
$GreenhouseDir = Join-Path $Root "plc_web_hmi_v1_7\plc_web_hmi_v1_7"
$RuntimeDir = Join-Path $Root ".runtime"
$LogDir = Join-Path $Root "logs"

New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null

function Write-Step($Message) {
    Write-Host "[sensor-platform] $Message"
}

function Resolve-Tool($Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    throw "Required command not found: $($Names -join ', ')"
}

function Resolve-GreenhousePython {
    if ($env:CONDA_PREFIX) {
        $activePython = Join-Path $env:CONDA_PREFIX "python.exe"
        if ((Split-Path $env:CONDA_PREFIX -Leaf) -eq "sensor" -and (Test-Path $activePython)) {
            return $activePython
        }
    }

    # Conda can be exposed as a PowerShell alias/function, whose Source is not
    # an executable path. Check registered environment directories first.
    $envDirectories = @()
    if ($env:CONDA_ENVS_PATH) {
        $envDirectories += $env:CONDA_ENVS_PATH -split ';'
    }

    $environmentFile = Join-Path $env:USERPROFILE ".conda\environments.txt"
    if (Test-Path $environmentFile) {
        $envDirectories += Get-Content $environmentFile -ErrorAction SilentlyContinue
    }

    foreach ($directory in $envDirectories | Where-Object { $_ }) {
        $normalizedDirectory = $directory.Trim()
        $sensorPython = if ((Split-Path $normalizedDirectory -Leaf) -eq "sensor") {
            Join-Path $normalizedDirectory "python.exe"
        } else {
            Join-Path $normalizedDirectory "sensor\python.exe"
        }
        if (Test-Path $sensorPython) {
            return $sensorPython
        }
    }

    $base = (& conda --no-plugins info --base 2>$null | Select-Object -First 1).Trim()
    if ($base) {
        $sensorPython = Join-Path $base "envs\sensor\python.exe"
        if (Test-Path $sensorPython) {
            return $sensorPython
        }
    }

    throw "Conda environment 'sensor' was not found. Activate it first, or create it before starting the greenhouse service."
}

function Test-PortListening($Port) {
    $pattern = "[:.]$Port\s+.*LISTENING"
    return [bool](netstat -ano -p tcp | Select-String -Pattern $pattern)
}

function Wait-Port($Port, $Name, $TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening $Port) {
            Write-Step "$Name is listening on port $Port."
            return
        }
        Start-Sleep -Seconds 2
    }
    Write-Warning "$Name did not listen on port $Port within $TimeoutSeconds seconds. Check logs."
}

function Save-Pid($Name, $Process) {
    Set-Content -Path (Join-Path $RuntimeDir "$Name.pid") -Value $Process.Id -Encoding ASCII
}

function Start-ManagedProcess($Name, $FilePath, $ArgumentList, $WorkingDirectory) {
    $out = Join-Path $LogDir "$Name.out.log"
    $err = Join-Path $LogDir "$Name.err.log"
    Remove-Item -LiteralPath $out, $err -ErrorAction SilentlyContinue

    Write-Step "Starting $Name..."
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -WindowStyle Hidden `
        -PassThru
    Save-Pid $Name $process
    Write-Step "$Name started, pid=$($process.Id), log=$out"
}

Write-Step "Project root: $Root"

$java = Resolve-Tool @("java.exe", "java")
$mvn = Resolve-Tool @("mvn.cmd", "mvn")
$npm = Resolve-Tool @("npm.cmd", "npm")
if (-not $SkipGreenhouse) {
    if (-not (Test-Path $GreenhouseDir)) {
        throw "Greenhouse service directory not found: $GreenhouseDir"
    }
    $greenhouseConfig = Join-Path $GreenhouseDir "config.json"
    if (-not (Test-Path $greenhouseConfig)) {
        throw "Greenhouse local configuration is missing. Copy config.example.json to config.json and fill in the MySQL settings."
    }
    $greenhousePython = Resolve-GreenhousePython
}

if (-not $SkipMysqlStart) {
    $mysqlService = Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^MySQL" -or $_.DisplayName -match "MySQL" } |
        Select-Object -First 1
    if ($mysqlService) {
        if ($mysqlService.Status -ne "Running") {
            Write-Step "Starting MySQL service: $($mysqlService.Name)"
            try {
                Start-Service -Name $mysqlService.Name
                Start-Sleep -Seconds 3
            } catch {
                Write-Warning "Failed to start MySQL service automatically: $($_.Exception.Message)"
            }
        } else {
            Write-Step "MySQL service is already running: $($mysqlService.Name)"
        }
    } else {
        Write-Warning "No MySQL service was found. Please make sure MySQL is running."
    }
}

if ($InstallDeps) {
    Write-Step "Installing frontend dependencies..."
    Push-Location $FrontendDir
    try {
        & $npm install --registry=https://registry.npmjs.org --offline=false --prefer-offline=false
    } finally {
        Pop-Location
    }

    Write-Step "Preparing backend Maven dependencies..."
    Push-Location $BackendDir
    try {
        & $mvn -q -DskipTests package
    } finally {
        Pop-Location
    }

    Write-Step "Preparing collector Maven dependencies..."
    Push-Location $CollectorDir
    try {
        & $mvn -q compile
    } finally {
        Pop-Location
    }

    if (-not $SkipGreenhouse) {
        Write-Step "Installing greenhouse Python dependencies..."
        & $greenhousePython -m pip install -r (Join-Path $GreenhouseDir "requirements.txt")
    }
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Warning "frontend\node_modules does not exist. Run scripts\start-system.ps1 -InstallDeps first."
}

if (-not $SkipGreenhouse) {
    if (-not (Test-PortListening 8000)) {
        Start-ManagedProcess "greenhouse-hmi" $greenhousePython @("run.py") $GreenhouseDir
    } else {
        Write-Step "Greenhouse HMI port 8000 is already listening; skip starting greenhouse service."
    }
    Wait-Port 8000 "Greenhouse HMI"
}

if (-not (Test-PortListening 8080)) {
    Start-ManagedProcess "backend" $mvn @("spring-boot:run") $BackendDir
} else {
    Write-Step "Backend port 8080 is already listening; skip starting backend."
}
Wait-Port 8080 "Backend"

if (-not (Test-PortListening 5173)) {
    Start-ManagedProcess "frontend" $npm @("run", "dev") $FrontendDir
} else {
    Write-Step "Frontend port 5173 is already listening; skip starting frontend."
}
Wait-Port 5173 "Frontend"

if (-not $SkipCollector) {
    if (-not (Test-PortListening 2404)) {
        Write-Step "Preparing collector classpath..."
        Push-Location $CollectorDir
        try {
            & $mvn -q compile
            & $mvn -q dependency:build-classpath "-Dmdep.outputFile=target/classpath.txt"
        } finally {
            Pop-Location
        }

        $dependencyClasspath = (Get-Content (Join-Path $CollectorDir "target\classpath.txt") -Raw).Trim()
        $collectorClasspath = "$(Join-Path $CollectorDir "target\classes");$dependencyClasspath"
        Start-ManagedProcess "collector" $java @("-cp", $collectorClasspath, "demo.Application") $CollectorDir
    } else {
        Write-Step "Collector port 2404 is already listening; skip starting collector."
    }
    Wait-Port 2404 "Collector"
}

Write-Host ""
Write-Step "Startup finished."
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8080/api/sensor/summary"
if (-not $SkipGreenhouse) {
    Write-Host "Greenhouse: http://localhost:8000"
}
Write-Host "Logs:     $LogDir"
Write-Host "Stop:     scripts\stop-system.ps1"
