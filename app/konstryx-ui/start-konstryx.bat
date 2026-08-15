@echo off
REM ===================================================================
REM  KONSTRYX - start the UI5 app
REM  A SAPUI5 app cannot run from file:// - the XML views and manifest
REM  are fetched over XHR, which Chrome blocks on local files. This
REM  starts a small local server and opens the browser.
REM ===================================================================
setlocal
set PORT=8080
set RUNTIME=C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0

cd /d "%~dp0"

if not exist "%RUNTIME%\resources\sap-ui-core.js" (
  echo.
  echo   SAPUI5 runtime not found at:
  echo     %RUNTIME%
  echo   Edit the RUNTIME line at the top of this file and run it again.
  echo.
  pause
  exit /b 1
)

where py >/dev/null 2>/dev/null && (py -3 serve.py %PORT% "%RUNTIME%" & goto :eof)
where python >/dev/null 2>/dev/null && (python serve.py %PORT% "%RUNTIME%" & goto :eof)

echo   Python not found - falling back to PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1" -Port %PORT% -Runtime "%RUNTIME%"
