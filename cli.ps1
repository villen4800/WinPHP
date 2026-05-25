# cli.ps1 - Standalone PowerShell Command Line Server Manager (CLI)
# No Python dependency required.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Global Directories
$Global:BaseDir = $PSScriptRoot
$Global:BinDir = Join-Path $Global:BaseDir "bin"
$Global:ToolsDir = Join-Path $Global:BaseDir "tools"
$Global:WwwDir = Join-Path $Global:BaseDir "www"
$Global:PidFile = Join-Path $Global:BinDir "services_pids.json"

# ANSI Colors for premium dashboard
$Global:C_BLUE = [char]27 + "[38;5;75m"
$Global:C_CYAN = [char]27 + "[38;5;117m"
$Global:C_GREEN = [char]27 + "[38;5;120m"
$Global:C_RED = [char]27 + "[38;5;203m"
$Global:C_ORANGE = [char]27 + "[38;5;215m"
$Global:C_PURPLE = [char]27 + "[38;5;141m"
$Global:C_SLATE = [char]27 + "[38;5;244m"
$Global:C_WHITE = [char]27 + "[38;5;255m"
$Global:C_YELLOW = [char]27 + "[38;5;220m"
$Global:C_BOLD = [char]27 + "[1m"
$Global:C_RESET = [char]27 + "[0m"

# Load Ports Configuration
function Load-Ports {
    $portsConfigPath = Join-Path $Global:BinDir "ports_config.json"
    $ports = @{
        nginx  = 80
        apache = 80
        mysql  = 3306
        php    = 9000
    }
    if (Test-Path $portsConfigPath) {
        try {
            $loaded = Get-Content $portsConfigPath -Raw | ConvertFrom-Json
            if ($loaded) {
                foreach ($key in @("nginx", "apache", "mysql", "php")) {
                    if ($loaded.PSObject.Properties[$key]) {
                        $ports[$key] = [int]$loaded.$key
                    }
                }
            }
        } catch {}
    }
    return $ports
}

$Global:Ports = Load-Ports

# Load PIDs Helper
function Load-Pids {
    if (Test-Path $Global:PidFile) {
        try {
            return Get-Content $Global:PidFile -Raw | ConvertFrom-Json
        } catch {}
    }
    # Return default empty object
    $obj = New-Object PSObject
    $obj | Add-Member -MemberType NoteProperty -Name "nginx" -Value $null
    $obj | Add-Member -MemberType NoteProperty -Name "apache" -Value $null
    $obj | Add-Member -MemberType NoteProperty -Name "mysql" -Value $null
    $obj | Add-Member -MemberType NoteProperty -Name "php" -Value $null
    $obj | Add-Member -MemberType NoteProperty -Name "php_version" -Value $null
    return $obj
}

# Save PIDs Helper
function Save-Pids($pids) {
    $parent = Split-Path $Global:PidFile -Parent
    if (-not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }
    try {
        $json = $pids | ConvertTo-Json -Depth 5
        [System.IO.File]::WriteAllText($Global:PidFile, $json, [System.Text.Encoding]::UTF8)
    } catch {
        Write-Warning "Failed to save PIDs: $_"
    }
}

# Load DB Config Helper
function Load-DbConfig {
    $dbConfigPath = Join-Path $Global:BinDir "db_config.json"
    if (Test-Path $dbConfigPath) {
        try {
            return Get-Content $dbConfigPath -Raw | ConvertFrom-Json
        } catch {}
    }
    return @{ root_password = "" }
}

# Check if Port is Open
function Test-PortOpen([int]$port) {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    try {
        $asyncResult = $tcpClient.BeginConnect("127.0.0.1", $port, $null, $null)
        $wait = $asyncResult.AsyncWaitHandle.WaitOne(200) # 200ms timeout
        if ($wait -and $tcpClient.Connected) {
            $tcpClient.EndConnect($asyncResult)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $tcpClient.Dispose()
    }
}

# Get PHP Version Folders
function Get-PhpVersions {
    $phpDir = Join-Path $Global:BinDir "php"
    if (-not (Test-Path $phpDir)) { return @() }
    
    $dirs = Get-ChildItem -Path $phpDir -Directory -ErrorAction SilentlyContinue | 
            Where-Object { $_.Name -like "php-*" } | 
            Select-Object -ExpandProperty Name
            
    return $dirs | Sort-Object -Descending
}

# Get Currently Active PHP Version
function Get-CurrentPhpVersion {
    $pids = Load-Pids
    if ($pids.PSObject.Properties['php_version'] -and $pids.php_version) {
        return $pids.php_version
    }
    $versions = Get-PhpVersions
    if ($versions.Count -gt 0) {
        return $versions[0]
    }
    return "php-8.2.31-nts"
}

# Get Service Status
function Get-ServiceStatus([string]$name) {
    $pids = Load-Pids
    $pidVal = $pids.$name
    $port = $Global:Ports.$name
    $portActive = Test-PortOpen -port $port

    $procName = switch ($name) {
        "nginx" { "nginx" }
        "apache" { "httpd" }
        "mysql" { "mysqld" }
        "php" { "php-cgi" }
    }

    $pidRunning = $false
    if ($pidVal) {
        $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($proc) { $pidRunning = $true }
    }

    $procRunning = $false
    $matchingProcs = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if ($matchingProcs) { $procRunning = $true }

    $isRunning = $pidRunning -or ($procRunning -and $portActive)

    if ($isRunning) {
        # Try to resolve PID if not already correct
        if (-not $pidRunning) {
            if ($name -eq "nginx") {
                $nginxPidPath = Join-Path $Global:BinDir "nginx\logs\nginx.pid"
                if (Test-Path $nginxPidPath) {
                    try {
                        $pidVal = [int](Get-Content $nginxPidPath -Raw).Trim()
                    } catch {}
                }
            }
            if (-not $pidVal -and $matchingProcs) {
                $pidVal = $matchingProcs[0].Id
            }
        }

        # Calculate memory
        $mem = 0
        if ($pidVal) {
            $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
            if ($proc) {
                $mem = [math]::Round($proc.WorkingSet64 / (1024 * 1024), 1)
            }
        }
        return @{ status = "running"; pid = $pidVal; memory = $mem }
    } else {
        return @{ status = "stopped"; pid = $null; memory = 0 }
    }
}

# Kill Process Tree Helper
function Stop-ProcessTree([int]$targetPid) {
    if ($targetPid) {
        Start-Process "taskkill" -ArgumentList "/F", "/T", "/PID", $targetPid -NoNewWindow -Wait -ErrorAction SilentlyContinue
    }
}

# Stop Service
function Stop-ServiceInternal([string]$name) {
    $statusInfo = Get-ServiceStatus -name $name
    if ($statusInfo.status -eq "stopped") {
        $pids = Load-Pids
        $pids.$name = $null
        Save-Pids $pids
        return
    }

    $pidVal = $statusInfo.pid

    try {
        if ($name -eq "nginx") {
            $nginxExe = Join-Path $Global:BinDir "nginx\nginx.exe"
            if (Test-Path $nginxExe) {
                Start-Process $nginxExe -ArgumentList "-s", "stop" -WorkingDirectory (Join-Path $Global:BinDir "nginx") -NoNewWindow -Wait -ErrorAction SilentlyContinue
            }
            Start-Sleep -Milliseconds 500
            if ($pidVal) {
                Stop-ProcessTree -targetPid $pidVal
            }
            Stop-Process -Name "nginx" -Force -ErrorAction SilentlyContinue
        }
        elseif ($name -eq "mysql") {
            $mysqladminExe = Join-Path $Global:BinDir "mysql\bin\mysqladmin.exe"
            $shutdownSuccess = $false
            if (Test-Path $mysqladminExe) {
                $dbConfig = Load-DbConfig
                $rootPass = $dbConfig.root_password
                $args = @("-u", "root")
                if ($rootPass) {
                    $args += "-p$rootPass"
                }
                $args += "shutdown"
                $proc = Start-Process $mysqladminExe -ArgumentList $args -NoNewWindow -PassThru -ErrorAction SilentlyContinue
                if ($proc) {
                    $proc.WaitForExit(5000)
                    if ($proc.ExitCode -eq 0) {
                        $shutdownSuccess = $true
                    }
                }
            }
            if (-not $shutdownSuccess -and $pidVal) {
                Stop-ProcessTree -targetPid $pidVal
            }
            Stop-Process -Name "mysqld" -Force -ErrorAction SilentlyContinue
        }
        elseif ($name -eq "apache") {
            if ($pidVal) {
                Stop-ProcessTree -targetPid $pidVal
            }
            Stop-Process -Name "httpd" -Force -ErrorAction SilentlyContinue
        }
        elseif ($name -eq "php") {
            if ($pidVal) {
                Stop-ProcessTree -targetPid $pidVal
            }
            Stop-Process -Name "php-cgi" -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Warning "Error stopping service $($name): $($_)"
    }

    $pids = Load-Pids
    $pids.$name = $null
    Save-Pids $pids
}

# Start Process Detached Helper
function Start-ProcessDetached([string]$exePath, [string]$arguments, [string]$workDir) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exePath
    if ($arguments) {
        $psi.Arguments = $arguments
    }
    if ($workDir) {
        $psi.WorkingDirectory = $workDir
    }
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    $proc = [System.Diagnostics.Process]::Start($psi)
    return $proc
}

# Configure Apache Config File
function Setup-ApacheInternal {
    $apacheDir = Join-Path $Global:BinDir "apache"
    $httpdConf = Join-Path $apacheDir "conf\httpd.conf"
    if (-not (Test-Path $httpdConf)) { return }

    try {
        $content = [System.IO.File]::ReadAllText($httpdConf, [System.Text.Encoding]::UTF8)

        # 1. Replace SRVROOT
        $apachePathEsc = $apacheDir.Replace('\', '/')
        $content = $content -replace 'Define SRVROOT "C:/Apache24"', "Define SRVROOT `"$apachePathEsc`""
        $content = $content -replace 'Define SRVROOT "c:/Apache24"', "Define SRVROOT `"$apachePathEsc`""

        # 2. Replace Listen Port
        $apachePort = $Global:Ports.apache
        $content = [System.Text.RegularExpressions.Regex]::Replace($content, '(?m)^\s*Listen\s+\d+', "Listen $apachePort")

        # 3. Replace DocumentRoot & DirectoryIndex
        $wwwPathEsc = $Global:WwwDir.Replace('\', '/')
        $content = $content -replace 'DocumentRoot "\$\{SRVROOT\}/htdocs"', "DocumentRoot `"$wwwPathEsc`""
        $content = $content -replace '<Directory "\$\{SRVROOT\}/htdocs">', "<Directory `"$wwwPathEsc`">"
        $content = $content -replace 'DirectoryIndex index.html', 'DirectoryIndex index.php index.html'

        # 4. Enable Proxy Modules
        $content = $content -replace '#LoadModule proxy_module modules/mod_proxy.so', 'LoadModule proxy_module modules/mod_proxy.so'
        $content = $content -replace '#LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so', 'LoadModule proxy_fcgi_module modules/mod_proxy_fcgi.so'

        # 5. PHP Proxy Setup
        $phpPort = $Global:Ports.php
        $phpProxySetup = @"
<FilesMatch \.php$>
    ProxyFCGIBackendType GENERIC
    SetHandler `"proxy:fcgi://127.0.0.1:$phpPort//./`"
</FilesMatch>
"@
        if ($content -match '<FilesMatch\s+[^>]*\.php[^>]*>') {
            $content = [System.Text.RegularExpressions.Regex]::Replace($content, '(?s)<FilesMatch\s+[^>]*\.php[^>]*>.*?</FilesMatch>', $phpProxySetup)
        } else {
            $content += "`r`n`r`n# PHP FastCGI proxy setup`r`n" + $phpProxySetup
        }

        # 6. phpMyAdmin Setup
        if (-not ($content -contains 'Alias /phpmyadmin')) {
            $phpmyadminPathEsc = (Join-Path $Global:ToolsDir "phpmyadmin").Replace('\', '/')
            $pmaSetup = @"

Alias /phpmyadmin `"$phpmyadminPathEsc`"
<Directory `"$phpmyadminPathEsc`">
    Options Indexes FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
"@
            $content += "`r`n" + $pmaSetup
        }

        [System.IO.File]::WriteAllText($httpdConf, $content, [System.Text.Encoding]::UTF8)
    } catch {
        Write-Warning "Failed to setup Apache: $_"
    }
}

# Start PHP Internal
function Start-PhpInternal([string]$version) {
    $phpStatus = Get-ServiceStatus -name "php"
    if ($phpStatus.status -eq "running") {
        return $true
    }

    $ver = if ($version) { $version } else { Get-CurrentPhpVersion }
    $phpExe = Join-Path $Global:BinDir "php\$ver\php-cgi.exe"
    if (-not (Test-Path $phpExe)) {
        return $false
    }

    $phpPort = $Global:Ports.php
    $proc = $null
    try {
        $proc = Start-ProcessDetached -exePath $phpExe -arguments "-b 127.0.0.1:$phpPort" -workDir $null
    } catch {
        return $false
    }

    if (-not $proc) {
        return $false
    }

    $pidVal = $proc.Id
    $success = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 200
        if (Test-PortOpen -port $phpPort) {
            $success = $true
            break
        }
    }

    if ($success) {
        $pids = Load-Pids
        $pids.php = $pidVal
        $pids.php_version = $ver
        Save-Pids $pids
        return $true
    } else {
        if ($pidVal) {
            Stop-ProcessTree -targetPid $pidVal
        }
        return $false
    }
}

# Start Service Internal
function Start-ServiceInternal([string]$name, [string]$phpVersion) {
    $statusInfo = Get-ServiceStatus -name $name
    if ($statusInfo.status -eq "running") {
        return @{ success = $true; pid = $statusInfo.pid }
    }

    $pids = Load-Pids

    # Enforce web server mutual exclusion
    if ($name -eq "nginx") {
        Stop-ServiceInternal -name "apache"
        $null = Start-PhpInternal -version $phpVersion
    }
    elseif ($name -eq "apache") {
        Stop-ServiceInternal -name "nginx"
        Setup-ApacheInternal
        $null = Start-PhpInternal -version $phpVersion
    }

    $exePath = ""
    $args = ""
    $workDir = ""

    if ($name -eq "php") {
        $ver = if ($phpVersion) { $phpVersion } else { Get-CurrentPhpVersion }
        $exePath = Join-Path $Global:BinDir "php\$ver\php-cgi.exe"
        if (-not (Test-Path $exePath)) {
            return @{ success = $false; error = "PHP executable not found for version $ver" }
        }
        $phpPort = $Global:Ports.php
        $args = "-b 127.0.0.1:$phpPort"
        $pids.php_version = $ver
    }
    elseif ($name -eq "nginx") {
        $exePath = Join-Path $Global:BinDir "nginx\nginx.exe"
        if (-not (Test-Path $exePath)) {
            return @{ success = $false; error = "Nginx executable not found" }
        }
        $workDir = Join-Path $Global:BinDir "nginx"
    }
    elseif ($name -eq "apache") {
        $exePath = Join-Path $Global:BinDir "apache\bin\httpd.exe"
        if (-not (Test-Path $exePath)) {
            return @{ success = $false; error = "Apache executable not found" }
        }
        $workDir = Join-Path $Global:BinDir "apache"
    }
    elseif ($name -eq "mysql") {
        $exePath = Join-Path $Global:BinDir "mysql\bin\mysqld.exe"
        if (-not (Test-Path $exePath)) {
            return @{ success = $false; error = "MySQL/MariaDB executable not found" }
        }
        $myIni = Join-Path $Global:BinDir "mysql\my.ini"
        if (Test-Path $myIni) {
            $args = "--defaults-file=`"$myIni`""
        }
        $workDir = Join-Path $Global:BinDir "mysql"
    }

    $proc = $null
    try {
        $proc = Start-ProcessDetached -exePath $exePath -arguments $args -workDir $workDir
    } catch {
        return @{ success = $false; error = $_.Exception.Message }
    }

    if (-not $proc) {
        return @{ success = $false; error = "Failed to start process" }
    }

    $pidVal = $proc.Id
    $success = $false
    $port = $Global:Ports.$name

    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 200
        if (Test-PortOpen -port $port) {
            $success = $true
            break
        }
    }

    if ($name -eq "nginx" -and $success) {
        $nginxPidPath = Join-Path $Global:BinDir "nginx\logs\nginx.pid"
        if (Test-Path $nginxPidPath) {
            try {
                $pidVal = [int](Get-Content $nginxPidPath -Raw).Trim()
            } catch {}
        }
    }

    if ($success -and $pidVal) {
        $pids.$name = $pidVal
        Save-Pids $pids
        return @{ success = $true; pid = $pidVal }
    } else {
        if ($pidVal) {
            Stop-ProcessTree -targetPid $pidVal
        }
        return @{ success = $false; error = "Service $name failed to start or port $port did not bind." }
    }
}

# Get Active Web Server Name
function Get-ActiveWebServer {
    $aStatus = (Get-ServiceStatus -name "apache").status
    $nStatus = (Get-ServiceStatus -name "nginx").status
    if ($aStatus -eq "running") { return "apache" }
    if ($nStatus -eq "running") { return "nginx" }
    return "nginx"
}

# ANSI Stripper Helper
function Strip-Ansi([string]$s) {
    return [System.Text.RegularExpressions.Regex]::Replace($s, '\e\[[0-9;]*m', '')
}

# Table Cell Text Fit Helper
function Fit-Text([string]$text, [int]$width) {
    $visible = Strip-Ansi $text
    if ($visible.Length -gt $width) {
        return $visible.Substring(0, $width)
    }
    return $text + (" " * ($width - $visible.Length))
}

# Make Border Line for Table
function Make-Border([string]$left, [string]$mid, [string]$right) {
    $widths = @(24, 12, 8, 8, 13)
    $inner = ($widths | ForEach-Object { "─" * $_ }) -join $mid
    return "  $Global:C_SLATE$left$inner$right$Global:C_RESET"
}

# Draw Interactive Dashboard Table
function Draw-StatusTable {
    $headers = @("Service Name", "Status", "Port", "PID", "Memory (MB)")
    $widths = @(24, 12, 8, 8, 13)

    Write-Host (Make-Border "┌" "┬" "┐")

    $headerRow = "  $Global:C_SLATE│$Global:C_RESET"
    for ($i = 0; $i -lt $headers.Count; $i++) {
        $cell = Fit-Text "$Global:C_WHITE$Global:C_BOLD$($headers[$i])$Global:C_RESET" ($widths[$i] - 2)
        $headerRow += " $cell $Global:C_SLATE│$Global:C_RESET"
    }
    Write-Host $headerRow

    Write-Host (Make-Border "├" "┼" "┤")

    $services = @("nginx", "apache", "mysql", "php")
    $currentPhpVer = Get-CurrentPhpVersion
    $displayNames = @{
        "nginx"  = "Nginx Web Server"
        "apache" = "Apache Web Server"
        "mysql"  = "MySQL/MariaDB Database"
        "php"    = "PHP FastCGI ($currentPhpVer)"
    }

    foreach ($svc in $services) {
        $statusInfo = Get-ServiceStatus -name $svc
        $port = $Global:Ports.$svc

        $statusText = if ($statusInfo.status -eq "running") { "Running" } else { "Stopped" }
        $statusColor = if ($statusInfo.status -eq "running") { $Global:C_GREEN } else { $Global:C_RED }
        $statusColored = "$statusColor$statusText$Global:C_RESET"

        $memStr = if ($statusInfo.status -eq "running" -and $statusInfo.memory -gt 0) { "$($statusInfo.memory) MB" } else { "--" }
        $pidStr = if ($statusInfo.pid) { "$($statusInfo.pid)" } else { "--" }
        $portStr = if ($port) { "$port" } else { "--" }

        $cells = @(
            (Fit-Text $displayNames[$svc] ($widths[0] - 2)),
            (Fit-Text $statusColored ($widths[1] - 2)),
            (Fit-Text $portStr ($widths[2] - 2)),
            (Fit-Text $pidStr ($widths[3] - 2)),
            (Fit-Text $memStr ($widths[4] - 2))
        )

        $row = "  $Global:C_SLATE│$Global:C_RESET"
        foreach ($c in $cells) {
            $row += " $c $Global:C_SLATE│$Global:C_RESET"
        }
        Write-Host $row
    }

    Write-Host (Make-Border "└" "┴" "┘")
}

# Progress Bar Generator
function Make-ProgressBar([int]$pct, [int]$length=20, [string]$color=$Global:C_BLUE) {
    $filled = [int][math]::Round($length * $pct / 100)
    if ($filled -lt 0) { $filled = 0 }
    if ($filled -gt $length) { $filled = $length }
    
    $bar = ("█" * $filled) + ("░" * ($length - $filled))
    return "$color$bar$Global:C_RESET $Global:C_WHITE$pct%$Global:C_RESET"
}

# Get Local Logs Content
function Get-LogContentLocal([string]$svc) {
    $currentPhpVer = Get-CurrentPhpVersion
    $paths = @()

    switch ($svc) {
        "nginx" {
            $paths += Join-Path $Global:BinDir "nginx\logs\error.log"
            $paths += Join-Path $Global:BinDir "nginx\logs\access.log"
        }
        "apache" {
            $paths += Join-Path $Global:BinDir "apache\logs\error.log"
        }
        "mysql" {
            $mysqlDataDir = Join-Path $Global:BinDir "mysql\data"
            if (Test-Path $mysqlDataDir) {
                $errFiles = Get-ChildItem -Path $mysqlDataDir -Filter "*.err" -File | Sort-Object LastWriteTime -Descending
                if ($errFiles) {
                    $paths += $errFiles[0].FullName
                }
            }
        }
        "php" {
            $paths += Join-Path $Global:BinDir "php\$currentPhpVer\php_errors.log"
            $paths += Join-Path $Global:BaseDir "php_errors.log"
        }
    }

    $logsContent = ""
    $foundPath = $null

    foreach ($path in $paths) {
        if ($path -and (Test-Path $path)) {
            $foundPath = $path
            try {
                $lines = Get-Content $path -Tail 30 -ErrorAction SilentlyContinue
                if ($lines) {
                    $logsContent = $lines -join "`r`n"
                } else {
                    $logsContent = "No log records found for this service."
                }
                break
            } catch {
                $logsContent = "Error reading log: $_"
            }
        }
    }

    if (-not $foundPath) {
        $logsContent = "No log records found for this service."
    }

    return @{ content = $logsContent; path = $foundPath }
}

# Interactive Logs Viewer
function View-LogsInteractive {
    while ($true) {
        Clear-Host
        Write-Host ""
        Write-Host "  $Global:C_BOLD`View Service Logs$Global:C_RESET"
        Write-Host ""
        Write-Host "  $Global:C_CYAN[1]$Global:C_RESET Nginx logs"
        Write-Host "  $Global:C_CYAN[2]$Global:C_RESET Apache logs"
        Write-Host "  $Global:C_CYAN[3]$Global:C_RESET PHP logs"
        Write-Host "  $Global:C_CYAN[4]$Global:C_RESET MySQL/MariaDB logs"
        Write-Host "  $Global:C_CYAN[5]$Global:C_RESET Back to Main Menu"
        Write-Host ""
        
        $choice = (Read-Host "  $Global:C_BOLDSelect service (1-5)$Global:C_RESET").Trim()
        
        $svc = ""
        switch ($choice) {
            "1" { $svc = "nginx" }
            "2" { $svc = "apache" }
            "3" { $svc = "php" }
            "4" { $svc = "mysql" }
            "5" { return }
            default { continue }
        }

        while ($true) {
            Clear-Host
            Write-Host ""
            Write-Host "  $Global:C_BOLD`Logs for $($svc.ToUpper())$Global:C_RESET (Press Enter to Refresh, Q to return)"
            Write-Host ""

            $logData = Get-LogContentLocal -svc $svc
            if ($logData.path) {
                Write-Host "  $Global:C_SLATESource file: $($logData.path)$Global:C_RESET"
                Write-Host ""
            } else {
                Write-Host "  $Global:C_RED`No log files found.$Global:C_RESET"
                Write-Host ""
            }

            Write-Host $logData.content
            Write-Host ""

            $action = (Read-Host "  $Global:C_BOLD[Press Enter to Refresh or 'q' to go back]$Global:C_RESET").Trim().ToLower()
            if ($action -eq "q") {
                break
            }
        }
    }
}

# Interactive Switch PHP Version
function Switch-PhpVersionInteractive {
    Clear-Host
    Write-Host ""
    Write-Host "  $Global:C_BOLD`Switch PHP Version$Global:C_RESET"
    Write-Host ""
    
    $current = Get-CurrentPhpVersion
    $versions = Get-PhpVersions
    
    if ($versions.Count -eq 0) {
        Write-Host "  $Global:C_RED`No installed PHP versions found in bin/php!$Global:C_RESET"
        $null = Read-Host "`r`n  Press Enter to return..."
        return
    }

    Write-Host "  Currently Active: $Global:C_CYAN$current$Global:C_RESET"
    Write-Host ""
    Write-Host "  Available Versions:"
    
    for ($i = 0; $i -lt $versions.Count; $i++) {
        $v = $versions[$i]
        $marker = if ($v -eq $current) { "$Global:C_GREEN* $Global:C_RESET" } else { "  " }
        $idx = $i + 1
        Write-Host "  $Global:C_CYAN[$idx]$Global:C_RESET $marker$v"
    }
    Write-Host "  $Global:C_CYAN[C]$Global:C_RESET Cancel"
    Write-Host ""

    $choice = (Read-Host "  $Global:C_BOLDSelect version number$Global:C_RESET").Trim()
    if ($choice.ToLower() -eq "c") { return }

    try {
        $selIdx = [int]$choice - 1
        if ($selIdx -ge 0 -and $selIdx -lt $versions.Count) {
            $targetVer = $versions[$selIdx]
            if ($targetVer -eq $current) {
                Write-Host "`r`n  $Global:C_SLATE`PHP version $targetVer is already active.$Global:C_RESET"
                Start-Sleep -Seconds 1.5
                return
            }

            Write-Host "`r`n  Switching PHP version to $targetVer..."
            $pids = Load-Pids
            $pids.php_version = $targetVer
            Save-Pids $pids

            $phpStatus = Get-ServiceStatus -name "php"
            if ($phpStatus.status -eq "running") {
                Stop-ServiceInternal -name "php"
                $null = Start-PhpInternal -version $targetVer
            }

            Write-Host "  $Global:C_GREEN`PHP version successfully switched to $targetVer!$Global:C_RESET"
        } else {
            Write-Host "`r`n  $Global:C_RED`Invalid selection!$Global:C_RESET"
        }
    } catch {
        Write-Host "`r`n  $Global:C_RED`Invalid input!$Global:C_RESET"
    }
    Start-Sleep -Seconds 2
}

# Interactive Switch Web Server Profile
function Switch-WebServerInteractive([string]$activeWs) {
    Clear-Host
    Write-Host ""
    Write-Host "  $Global:C_BOLD`Switch Active Web Server Profile$Global:C_RESET"
    Write-Host ""
    Write-Host "  Current active server: $Global:C_CYAN$($activeWs.ToUpper())$Global:C_RESET"
    Write-Host ""
    Write-Host "  $Global:C_CYAN[1]$Global:C_RESET Switch to NGINX (will stop Apache)"
    Write-Host "  $Global:C_CYAN[2]$Global:C_RESET Switch to APACHE (will stop Nginx)"
    Write-Host "  $Global:C_CYAN[3]$Global:C_RESET Cancel"
    Write-Host ""

    $choice = (Read-Host "  $Global:C_BOLD`Choose profile (1-3)$Global:C_RESET").Trim()
    $target = $null
    
    if ($choice -eq "1") {
        if ($activeWs -eq "nginx") {
            Write-Host "`r`n  $Global:C_SLATE`Nginx is already the active web server profile.$Global:C_RESET"
            Start-Sleep -Seconds 1.5
            return
        }
        $target = "nginx"
    }
    elseif ($choice -eq "2") {
        if ($activeWs -eq "apache") {
            Write-Host "`r`n  $Global:C_SLATE`Apache is already the active web server profile.$Global:C_RESET"
            Start-Sleep -Seconds 1.5
            return
        }
        $target = "apache"
    }

    if ($target) {
        Write-Host "`r`n  Switching active profile to $($target.ToUpper())..."
        $phpVersion = Get-CurrentPhpVersion
        if ($target -eq "nginx") {
            Stop-ServiceInternal -name "apache"
            $res = Start-ServiceInternal -name "nginx" -phpVersion $phpVersion
        } else {
            Stop-ServiceInternal -name "nginx"
            $res = Start-ServiceInternal -name "apache" -phpVersion $phpVersion
        }

        if ($res.success) {
            Write-Host "  $Global:C_GREEN`Switched to $($target.ToUpper()) successfully!$Global:C_RESET"
        } else {
            Write-Host "  $Global:C_RED`Failed to start $($target.ToUpper()): $($res.error)$Global:C_RESET"
        }
    } else {
        Write-Host "`r`n  $Global:C_SLATE`No switch performed.$Global:C_RESET"
    }
    Start-Sleep -Seconds 2
}

# Interactive Toggle Single Service
function Toggle-SingleServiceInteractive([string]$activeWs) {
    Clear-Host
    Write-Host ""
    Write-Host "  $Global:C_BOLD`Toggle Single Service$Global:C_RESET"
    Write-Host ""
    Write-Host "  $Global:C_CYAN[1]$Global:C_RESET $($activeWs.ToUpper()) Web Server"
    Write-Host "  $Global:C_CYAN[2]$Global:C_RESET PHP FastCGI"
    Write-Host "  $Global:C_CYAN[3]$Global:C_RESET MySQL/MariaDB Database"
    Write-Host "  $Global:C_CYAN[4]$Global:C_RESET Back to Main Menu"
    Write-Host ""

    $choice = (Read-Host "  $Global:C_BOLD`Select service to toggle (1-4)$Global:C_RESET").Trim()
    $svc = ""
    
    if ($choice -eq "1") { $svc = $activeWs }
    elseif ($choice -eq "2") { $svc = "php" }
    elseif ($choice -eq "3") { $svc = "mysql" }
    else { return }

    $statusInfo = Get-ServiceStatus -name $svc
    if ($statusInfo.status -eq "running") {
        Write-Host "`r`n  Stopping $($svc.ToUpper())..."
        Stop-ServiceInternal -name $svc
        Write-Host "  $Global:C_RED$($svc.ToUpper()) stopped.$Global:C_RESET"
    } else {
        Write-Host "`r`n  Starting $($svc.ToUpper())..."
        $phpVersion = Get-CurrentPhpVersion
        $res = Start-ServiceInternal -name $svc -phpVersion $phpVersion
        if ($res.success) {
            Write-Host "  $Global:C_GREEN$($svc.ToUpper()) started.$Global:C_RESET"
        } else {
            Write-Host "  $Global:C_RED`Failed to start $($svc.ToUpper()): $($res.error)$Global:C_RESET"
        }
    }
    Start-Sleep -Seconds 2
}

# Interactive Menu Dashboard
function Interactive-Main {
    $Global:SyncHash = [hashtable]::Synchronized(@{
        cpu = 0
        ram = 0
        disk = 0
        loading = $true
        active = $true
    })

    $runspace = [runspacefactory]::CreateRunspace()
    $runspace.Open()
    $runspace.SessionStateProxy.SetVariable("syncHash", $Global:SyncHash)

    $pipeline = $runspace.CreatePipeline({
        while ($syncHash.active) {
            $ramPct = 0
            try {
                $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
                if ($os) {
                    $total = $os.TotalVisibleMemorySize
                    $free = $os.FreePhysicalMemory
                    $ramPct = [math]::Round((($total - $free) / $total) * 100)
                }
            } catch {}

            $cpuPct = 0
            try {
                $cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue
                if ($cpu) {
                    $pcts = $cpu | Select-Object -ExpandProperty LoadPercentage
                    $cpuPct = ($pcts | Measure-Object -Average).Average
                    if (-not $cpuPct) { $cpuPct = 0 }
                    $cpuPct = [math]::Round($cpuPct)
                }
            } catch {}

            $diskPct = 0
            try {
                $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue
                if ($disk) {
                    $size = $disk.Size
                    $free = $disk.FreeSpace
                    $diskPct = [math]::Round((($size - $free) / $size) * 100)
                }
            } catch {}

            $syncHash.cpu = $cpuPct
            $syncHash.ram = $ramPct
            $syncHash.disk = $diskPct
            $syncHash.loading = $false

            for ($i = 0; $i -lt 50; $i++) {
                if (-not $syncHash.active) { break }
                Start-Sleep -Milliseconds 100
            }
        }
    })

    $pipeline.InvokeAsync()

    try {
        while ($true) {
            Clear-Host
            
            # Print Banner
            Write-Host "$Global:C_BLUE$Global:C_BOLD"
            Write-Host "  ██╗    ██╗██╗███╗   ██╗██████╗ ██╗  ██╗██████╗ "
            Write-Host "  ██║    ██║██║████╗  ██║██╔══██╗██║  ██║██╔══██╗"
            Write-Host "  ██║ █╗ ██║██║██╔██╗ ██║██████╔╝███████║██████╔╝"
            Write-Host "  ██║███╗██║██║██║╚██╗██║██╔═══╝ ██╔══██║██╔═══╝ "
            Write-Host "  ╚███╔███╔╝██║██║ ╚████║██║     ██║  ██║██║     "
            Write-Host "   ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝╚═╝     "
            Write-Host "            $Global:C_PURPLE⚡ CONTROL CENTER CLI v1.2 ⚡$Global:C_RESET`r`n"

            $activeWs = Get-ActiveWebServer
            $currentPhp = Get-CurrentPhpVersion
            Write-Host "  $Global:C_BOLD`Active Web Server Profile:$Global:C_RESET $Global:C_CYAN$($activeWs.ToUpper())$Global:C_RESET"
            Write-Host "  $Global:C_BOLD`Active PHP Version:$Global:C_RESET        $Global:C_CYAN$currentPhp$Global:C_RESET`r`n"

            Draw-StatusTable
            Write-Host ""

            $loading = $Global:SyncHash.loading
            $cpu = $Global:SyncHash.cpu
            $ram = $Global:SyncHash.ram
            $disk = $Global:SyncHash.disk

            Write-Host "  $Global:C_BOLD`SYSTEM PERFORMANCE$Global:C_RESET"
            if ($loading) {
                Write-Host "  $Global:C_SLATE`Fetching system metrics...$Global:C_RESET`r`n"
            } else {
                Write-Host "  CPU Usage:  $(Make-ProgressBar -pct $cpu -color $Global:C_BLUE)"
                Write-Host "  RAM Usage:  $(Make-ProgressBar -pct $ram -color $Global:C_PURPLE)"
                Write-Host "  Disk Usage: $(Make-ProgressBar -pct $disk -color $Global:C_ORANGE)`r`n"
            }

            Write-Host "  $Global:C_BOLD$Global:C_WHITE`AVAILABLE ACTIONS:$Global:C_RESET"
            Write-Host "  $Global:C_CYAN[1]$Global:C_RESET Start All Services                 $Global:C_CYAN[6]$Global:C_RESET Switch PHP Version"
            Write-Host "  $Global:C_CYAN[2]$Global:C_RESET Stop All Services                  $Global:C_CYAN[7]$Global:C_RESET View Service Logs"
            Write-Host "  $Global:C_CYAN[3]$Global:C_RESET Restart All Services               $Global:C_CYAN[8]$Global:C_RESET Refresh Menu"
            Write-Host "  $Global:C_CYAN[4]$Global:C_RESET Toggle Single Service              $Global:C_CYAN[9]$Global:C_RESET Stop Everything & Exit"
            Write-Host "  $Global:C_CYAN[5]$Global:C_RESET Switch Web Server (Nginx/Apache)   $Global:C_CYAN[10]$Global:C_RESET Exit Control Center`r`n"

            $choice = (Read-Host "  $Global:C_BOLD`Choose action (1-10)$Global:C_RESET").Trim()
            $activeWs = Get-ActiveWebServer

            if ($choice -eq "1") {
                Write-Host "`r`n  $Global:C_YELLOW`Starting all services...$Global:C_RESET"
                $phpVersion = Get-CurrentPhpVersion
                $null = Start-ServiceInternal -name "mysql" -phpVersion $phpVersion
                $null = Start-ServiceInternal -name $activeWs -phpVersion $phpVersion
                Write-Host "  $Global:C_GREEN`Services start triggered!$Global:C_RESET"
                Start-Sleep -Seconds 1.5
            }
            elseif ($choice -eq "2") {
                Write-Host "`r`n  $Global:C_YELLOW`Stopping all services...$Global:C_RESET"
                foreach ($s in @("nginx", "apache", "mysql", "php")) {
                    Stop-ServiceInternal -name $s
                }
                Write-Host "  $Global:C_RED`All services stopped!$Global:C_RESET"
                Start-Sleep -Seconds 1.5
            }
            elseif ($choice -eq "3") {
                Write-Host "`r`n  $Global:C_YELLOW`Restarting all services...$Global:C_RESET"
                foreach ($s in @("nginx", "apache", "mysql", "php")) {
                    Stop-ServiceInternal -name $s
                }
                $phpVersion = Get-CurrentPhpVersion
                $null = Start-ServiceInternal -name "mysql" -phpVersion $phpVersion
                $null = Start-ServiceInternal -name $activeWs -phpVersion $phpVersion
                Write-Host "  $Global:C_GREEN`All services restarted!$Global:C_RESET"
                Start-Sleep -Seconds 1.5
            }
            elseif ($choice -eq "4") {
                Toggle-SingleServiceInteractive -activeWs $activeWs
            }
            elseif ($choice -eq "5") {
                Switch-WebServerInteractive -activeWs $activeWs
            }
            elseif ($choice -eq "6") {
                Switch-PhpVersionInteractive
            }
            elseif ($choice -eq "7") {
                View-LogsInteractive
            }
            elseif ($choice -eq "8") {
                # loops again
            }
            elseif ($choice -eq "9") {
                Write-Host "`r`n  $Global:C_YELLOW`Stopping all services...$Global:C_RESET"
                foreach ($s in @("nginx", "apache", "mysql", "php")) {
                    Stop-ServiceInternal -name $s
                }
                Write-Host "  $Global:C_GREEN`All services stopped. Goodbye!$Global:C_RESET"
                Start-Sleep -Seconds 1
                break
            }
            elseif ($choice -eq "10") {
                Write-Host "`r`n  $Global:C_GREEN`Goodbye!$Global:C_RESET"
                break
            }
            else {
                Write-Host "`r`n  $Global:C_RED`Invalid option!$Global:C_RESET"
                Start-Sleep -Seconds 1
            }
        }
    } finally {
        $Global:SyncHash.active = $false
        Start-Sleep -Milliseconds 200
        $runspace.Close()
        $runspace.Dispose()
    }
}

# Print CLI Usage Help Screen
function Print-CliUsage {
    Write-Host "$Global:C_BOLD`WinPHP Command Line Server Manager (CLI) v1.2$Global:C_RESET"
    Write-Host ""
    Write-Host "$Global:C_BOLD`Usage:$Global:C_RESET"
    Write-Host "  server.bat             - Launch the interactive control dashboard"
    Write-Host "  server.bat status      - Show status of all services"
    Write-Host "  server.bat start       - Start Nginx/Apache (active profile) + MySQL + PHP"
    Write-Host "  server.bat stop        - Stop all running services"
    Write-Host "  server.bat restart     - Restart all services"
    Write-Host "  server.bat start <svc> - Start a specific service (nginx, apache, mysql, php)"
    Write-Host "  server.bat stop <svc>  - Stop a specific service (nginx, apache, mysql, php)"
    Write-Host "  server.bat web <type>  - Switch web server profile (nginx or apache)"
    Write-Host "  server.bat php <ver>   - Switch active PHP version (e.g. php-8.2.31-nts)"
    Write-Host "  server.bat logs <svc>  - Show last lines of logs for a service"
    Write-Host "  server.bat help        - Show this help screen"
}

# CLI Main Entrypoint
function Main($cliArgs) {
    if ($cliArgs.Count -gt 0) {
        $cmd = $cliArgs[0].ToLower()

        if ($cmd -eq "start") {
            $target = if ($cliArgs.Count -gt 1) { $cliArgs[1].ToLower() } else { "all" }
            if ($target -eq "all") {
                Write-Host "Starting all services..."
                $activeWs = Get-ActiveWebServer
                $phpVersion = Get-CurrentPhpVersion
                
                $resDb = Start-ServiceInternal -name "mysql" -phpVersion $phpVersion
                if (-not $resDb.success) {
                    Write-Host "Error starting MySQL: $($resDb.error)"
                }
                
                $resWs = Start-ServiceInternal -name $activeWs -phpVersion $phpVersion
                if (-not $resWs.success) {
                    Write-Host "Error starting Web Server ($activeWs): $($resWs.error)"
                } else {
                    Write-Host "Web Server ($activeWs) and PHP FastCGI successfully started."
                }
            }
            elseif ($target -in @("nginx", "apache", "mysql", "php")) {
                Write-Host "Starting service: $($target.ToUpper())..."
                $phpVersion = Get-CurrentPhpVersion
                $res = Start-ServiceInternal -name $target -phpVersion $phpVersion
                if ($res.success) {
                    Write-Host "Service $($target.ToUpper()) successfully started."
                } else {
                    Write-Host "Error starting $($target.ToUpper()): $($res.error)"
                }
            }
            else {
                Write-Host "Unknown start target: $target. Allowed: all, nginx, apache, mysql, php"
            }
        }
        elseif ($cmd -eq "stop") {
            $target = if ($cliArgs.Count -gt 1) { $cliArgs[1].ToLower() } else { "all" }
            if ($target -eq "all") {
                Write-Host "Stopping all services..."
                foreach ($s in @("nginx", "apache", "mysql", "php")) {
                    Stop-ServiceInternal -name $s
                }
                Write-Host "All services stopped."
            }
            elseif ($target -in @("nginx", "apache", "mysql", "php")) {
                Write-Host "Stopping service: $($target.ToUpper())..."
                Stop-ServiceInternal -name $target
                Write-Host "Service $($target.ToUpper()) stopped."
            }
            else {
                Write-Host "Unknown stop target: $target. Allowed: all, nginx, apache, mysql, php"
            }
        }
        elseif ($cmd -eq "restart") {
            $target = if ($cliArgs.Count -gt 1) { $cliArgs[1].ToLower() } else { "all" }
            if ($target -eq "all") {
                Write-Host "Restarting all services..."
                foreach ($s in @("nginx", "apache", "mysql", "php")) {
                    Stop-ServiceInternal -name $s
                }
                $activeWs = Get-ActiveWebServer
                $phpVersion = Get-CurrentPhpVersion
                $null = Start-ServiceInternal -name "mysql" -phpVersion $phpVersion
                $null = Start-ServiceInternal -name $activeWs -phpVersion $phpVersion
                Write-Host "All services restarted."
            }
            elseif ($target -in @("nginx", "apache", "mysql", "php")) {
                Write-Host "Restarting service: $($target.ToUpper())..."
                Stop-ServiceInternal -name $target
                $phpVersion = Get-CurrentPhpVersion
                $res = Start-ServiceInternal -name $target -phpVersion $phpVersion
                if ($res.success) {
                    Write-Host "Service $($target.ToUpper()) restarted successfully."
                } else {
                    Write-Host "Error restarting $($target.ToUpper()): $($res.error)"
                }
            }
            else {
                Write-Host "Unknown restart target: $target. Allowed: all, nginx, apache, mysql, php"
            }
        }
        elseif ($cmd -eq "status") {
            Write-Host ""
            Write-Host "$Global:C_BOLD`WinPHP Server Status:$Global:C_RESET"
            Write-Host ""
            $activeWs = Get-ActiveWebServer
            Write-Host "Active Web Server Profile: $($activeWs.ToUpper())`r`n"

            $displayNames = @{
                "nginx"  = "Nginx Web Server"
                "apache" = "Apache Web Server"
                "mysql"  = "MySQL/MariaDB Database"
                "php"    = "PHP FastCGI ($(Get-CurrentPhpVersion))"
            }

            foreach ($s in @("nginx", "apache", "mysql", "php")) {
                $statusInfo = Get-ServiceStatus -name $s
                $port = $Global:Ports.$s
                $statusColor = if ($statusInfo.status -eq "running") { $Global:C_GREEN } else { $Global:C_RED }
                $pidStr = if ($statusInfo.pid) { "PID: $($statusInfo.pid)" } else { "Not running" }
                $memStr = if ($statusInfo.status -eq "running" -and $statusInfo.memory -gt 0) { "Memory: $($statusInfo.memory) MB" } else { "" }
                $portStr = if ($port) { "Port: $port" } else { "" }

                $details = @()
                if ($portStr) { $details += $portStr }
                if ($pidStr) { $details += $pidStr }
                if ($memStr) { $details += $memStr }
                
                $detailsJoined = $details -join ", "
                
                $paddedName = $displayNames[$s].PadRight(30)
                $paddedStatus = ($statusInfo.status.ToUpper()).PadRight(8)
                
                Write-Host "  $paddedName : $statusColor$paddedStatus$Global:C_RESET ($detailsJoined)"
            }
            Write-Host ""
        }
        elseif ($cmd -eq "web") {
            if ($cliArgs.Count -lt 2) {
                Write-Host "Error: Please specify web server type (nginx or apache)."
                Write-Host "Usage: server.bat web <nginx|apache>"
                return
            }
            $target = $cliArgs[1].ToLower()
            if ($target -notin @("nginx", "apache")) {
                Write-Host "Error: Invalid web server type '$target'. Allowed: nginx, apache"
                return
            }
            $activeWs = Get-ActiveWebServer
            if ($target -eq $activeWs) {
                Write-Host "Web server profile is already set to $($target.ToUpper())."
                return
            }
            Write-Host "Switching active web server profile to $($target.ToUpper())..."
            $phpVersion = Get-CurrentPhpVersion
            if ($target -eq "nginx") {
                Stop-ServiceInternal -name "apache"
                $res = Start-ServiceInternal -name "nginx" -phpVersion $phpVersion
            } else {
                Stop-ServiceInternal -name "nginx"
                $res = Start-ServiceInternal -name "apache" -phpVersion $phpVersion
            }

            if ($res.success) {
                Write-Host "Successfully switched and started $($target.ToUpper())!"
            } else {
                Write-Host "Failed to start $($target.ToUpper()): $($res.error)"
            }
        }
        elseif ($cmd -eq "php") {
            if ($cliArgs.Count -lt 2) {
                Write-Host "Error: Please specify target PHP version."
                $versions = Get-PhpVersions
                Write-Host "Installed PHP versions: $($versions -join ', ')"
                return
            }
            $target = $cliArgs[1].ToLower()
            $versions = Get-PhpVersions
            $matchedVer = $null
            foreach ($v in $versions) {
                if ($v.ToLower().Contains($target)) {
                    $matchedVer = $v
                    break
                }
            }
            if (-not $matchedVer) {
                Write-Host "Error: Version '$target' not found in installed versions."
                Write-Host "Installed versions: $($versions -join ', ')"
                return
            }

            $current = Get-CurrentPhpVersion
            if ($matchedVer -eq $current) {
                Write-Host "PHP version $matchedVer is already active."
                return
            }

            Write-Host "Switching active PHP version to $matchedVer..."
            $pids = Load-Pids
            $pids.php_version = $matchedVer
            Save-Pids $pids

            $phpStatus = Get-ServiceStatus -name "php"
            if ($phpStatus.status -eq "running") {
                Stop-ServiceInternal -name "php"
                $null = Start-PhpInternal -version $matchedVer
            }
            Write-Host "Successfully switched active PHP version to $matchedVer!"
        }
        elseif ($cmd -in @("logs", "log")) {
            if ($cliArgs.Count -lt 2) {
                Write-Host "Error: Please specify service (nginx, apache, php, or mysql)."
                Write-Host "Usage: server.bat logs <service_name>"
                return
            }
            $svc = $cliArgs[1].ToLower()
            if ($svc -notin @("nginx", "apache", "php", "mysql")) {
                Write-Host "Error: Invalid service '$svc'. Allowed: nginx, apache, php, mysql"
                return
            }
            $logData = Get-LogContentLocal -svc $svc
            if ($logData.path) {
                Write-Host ""
                Write-Host "$Global:C_BOLD`Last lines from $($logData.path):$Global:C_RESET"
                Write-Host ""
                Write-Host $logData.content
            } else {
                Write-Host "No log files found for $($svc.ToUpper())."
            }
        }
        elseif ($cmd -in @("help", "--help", "-h")) {
            Print-CliUsage
        }
        else {
            Write-Host "Unknown command: '$cmd'"
            Print-CliUsage
        }
    } else {
        Interactive-Main
    }
}

Main $args
