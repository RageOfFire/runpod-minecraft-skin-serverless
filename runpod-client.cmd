@echo off
setlocal

where cscript.exe >nul 2>nul
if errorlevel 1 (
    echo ERROR: cscript.exe is not available on this Windows PC.
    exit /b 1
)

cscript.exe //nologo "%~dp0runpod-client.js" %*
exit /b %errorlevel%
