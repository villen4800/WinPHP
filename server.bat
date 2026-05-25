@echo off
setlocal enabledelayedexpansion

title WinPHP Command Line Server Console

:: Verify PowerShell installation
where powershell >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] PowerShell was not found in your system PATH.
    pause
    exit /b 1
)

:: Execute the PowerShell CLI interface with passed arguments
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cli.ps1" %*
