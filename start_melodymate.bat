@echo off
title MelodyMate server
cd /d "%~dp0"
echo Starting MelodyMate. The page opens in your browser in a few seconds.
echo Close this window to stop MelodyMate.
start "" /b cmd /c "timeout /t 5 /nobreak >nul && start http://127.0.0.1:8000"
"C:\Users\tjohn\miniconda3-pbe\envs\melodymate\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
