@echo off
setlocal

if "%~1"=="" (
    where mshta.exe >nul 2>nul
    if errorlevel 1 (
        echo ERROR: mshta.exe is not available on this Windows PC.
        echo You can still use command-line mode by passing arguments.
        pause
        exit /b 1
    )

    start "" mshta.exe "%~dp0runpod-client.hta"
    exit /b 0
)

where cscript.exe >nul 2>nul
if errorlevel 1 (
    echo ERROR: cscript.exe is not available on this Windows PC.
    exit /b 1
)

cscript.exe //nologo "%~dp0runpod-client.js" %*
exit /b %errorlevel%
