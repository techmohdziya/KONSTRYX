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

if not exist "%JAR%" (
  echo.
  echo   The service jar is missing. Build it first:
  echo       mvn clean install -DskipTests
  echo.
  pause
  exit /b 1
)

echo Stopping anything already running on 8090 / 8081 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8090 .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8081 .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1

echo Starting the CAP service on 8090 ...
start "KONSTRYX service" /min "%JAVA_HOME%\bin\java.exe" -jar "%JAR%"

echo Waiting for the service to come up ...
set /a tries=0
:wait
set /a tries+=1
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "try{ (Invoke-WebRequest -Uri 'http://localhost:8090/' -Headers @{Authorization=('Basic '+[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:admin')))} -UseBasicParsing -TimeoutSec 4)|Out-Null; exit 0 }catch{ exit 1 }" >nul 2>&1
if errorlevel 1 (
  if %tries% lss 25 goto wait
  echo   Service did not start in time. Check the "KONSTRYX service" window.
  pause
  exit /b 1
)

echo Starting the UI server on 8081 ...
start "KONSTRYX ui" /min "%PY%" "%ROOT%app\konstryx-ui\serve.py" 8081
timeout /t 4 /nobreak >nul

echo Opening the app ...
start "" "http://localhost:8081/index.html"

echo.
echo   App      http://localhost:8081/index.html
echo   Service  http://localhost:8090/
echo.
echo   Two windows named "KONSTRYX service" and "KONSTRYX ui" are now running.
echo   Close them to stop.
echo.
endlocal
