@echo off
REM ---------------------------------------------------------------------------
REM  KONSTRYX - start both tiers locally and open the app.
REM
REM    CAP Java service   http://localhost:8090   OData V4 + static UI
REM    UI dev server      http://localhost:8081   serves the app, proxies /odata
REM
REM  Set KX_USER / KX_PASS to sign in as a different persona, e.g.
REM    set KX_USER=steward_infc & set KX_PASS=steward_infc & run-local.bat
REM ---------------------------------------------------------------------------
setlocal

set "ROOT=%~dp0"
set "JAVA_HOME=C:\Program Files\SapMachine\JDK\17"
set "JAR=%ROOT%srv\target\konstryx-srv-exec.jar"
set "PY=C:\Users\Ziya\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=python"

REM Load .env if present. Lines starting with # and blank lines are skipped.
REM Anything already set in the environment wins, so you can override per run:
REM     set KX_USER=daud && run-local.bat
if exist "%ROOT%.env" (
  echo Reading .env ...
  for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%ROOT%.env") do (
    if not "%%~a"=="" if not defined %%a set "%%a=%%b"
  )
) else (
  echo No .env found - using defaults. Copy .env.example to .env to change them.
)

if not defined KX_PORT     set "KX_PORT=8090"
if not defined KX_UI_PORT  set "KX_UI_PORT=8081"
if not defined KX_USER     set "KX_USER=demo"
if not defined KX_PASS     set "KX_PASS=demo"

if not exist "%JAR%" (
  echo.
  echo   The service jar is missing. Build it first:
  echo       mvn clean install -DskipTests
  echo.
  pause
  exit /b 1
)

echo Stopping anything already running on %KX_PORT% / %KX_UI_PORT% ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%KX_PORT% .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%KX_UI_PORT% .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1

echo Starting the CAP service on %KX_PORT% ...
start "KONSTRYX service" /min "%JAVA_HOME%\bin\java.exe" -jar "%JAR%" --server.port=%KX_PORT%

echo Waiting for the service to come up ...
set /a tries=0
:wait
set /a tries+=1
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "try{ (Invoke-WebRequest -Uri 'http://localhost:%KX_PORT%/' -Headers @{Authorization=('Basic '+[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:admin')))} -UseBasicParsing -TimeoutSec 4)|Out-Null; exit 0 }catch{ exit 1 }" >nul 2>&1
if errorlevel 1 (
  if %tries% lss 25 goto wait
  echo   Service did not start in time. Check the "KONSTRYX service" window.
  pause
  exit /b 1
)

echo Starting the UI server on %KX_UI_PORT% as %KX_USER% ...
start "KONSTRYX ui" /min "%PY%" "%ROOT%app\konstryx-ui\serve.py" %KX_UI_PORT%
timeout /t 4 /nobreak >nul

echo Opening the app ...
start "" "http://localhost:%KX_UI_PORT%/index.html"

echo.
echo   App      http://localhost:%KX_UI_PORT%/index.html
echo   Service  http://localhost:%KX_PORT%/
echo.
echo   Two windows named "KONSTRYX service" and "KONSTRYX ui" are now running.
echo   Close them to stop.
echo.
endlocal


