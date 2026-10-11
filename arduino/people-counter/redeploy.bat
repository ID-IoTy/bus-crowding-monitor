@echo off
setlocal
set HOST=arduino@192.168.23.166
set APPDIR=/home/arduino/ArduinoApps/people-counter

cd /d "%~dp0"

echo ========================================
echo Redeploy People Counter (struttura assets/)
echo ========================================
echo.

echo [1/3] Upload app.yaml, python/ e assets/ ...
scp -r app.yaml python assets %HOST%:%APPDIR%/
if %ERRORLEVEL% NEQ 0 (
    echo ERRORE: upload fallito
    pause
    exit /b 1
)
echo OK
echo.

echo [2/3] Restart app e test endpoint...
ssh %HOST% "cd %APPDIR% && ls -la assets assets/libs && arduino-app-cli app restart . && sleep 15 && echo --- / --- && curl -s -o /dev/null -w 'HTTP %%{http_code}\n' http://localhost:7000/ && echo --- /libs/arduino.js --- && curl -s -o /dev/null -w 'HTTP %%{http_code}\n' http://localhost:7000/libs/arduino.js && echo --- video 4912/embed --- && curl -s -o /dev/null -m 3 -w 'HTTP %%{http_code}\n' http://localhost:4912/embed; docker logs --tail 15 people-counter-main-1"
echo.

echo [3/3] Fatto.
echo Apri il browser su: http://192.168.23.166:7000/  (Ctrl+F5 per svuotare la cache)
echo ========================================
pause
