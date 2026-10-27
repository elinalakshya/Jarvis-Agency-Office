@echo off
echo ========================================
echo TAWARAGA JRAVIS V9 ULTRA NO-DOCKER START
echo ========================================
cd /d C:\Users\USER\Desktop\Mark-LIV-main

echo [1/4] Activating venv...
call .\.venv\Scripts\Activate.ps1 2>nul
call .\.venv\Scripts\activate.bat

echo [2/4] Installing deps if needed...
pip install flask flask-cors -q

echo [3/4] Starting JARVIS V9 NO-DOCKER Office Server - 20129...
start "JARVIS OFFICE NO-DOCKER 20129" cmd /k python jarvis_office_server.py

timeout /t 3

echo [4/4] Starting MARK LIV Main - Holographic Face...
start "MARK LIV LIV (54) FACE" cmd /k python main.py

timeout /t 2

echo ========================================
echo JRAVIS V9 ULTRA NO-DOCKER LIVE!
echo Office: http://localhost:20129
echo Office Stats: http://localhost:20129/office
echo Brain POST: http://localhost:20129/brain
echo MARK LIV Face: Running in separate window
echo ========================================
echo Test lead: curl -X POST http://localhost:20129/brain -H "Content-Type: application/json" -d "{"name":"Veeresh","phone":"9876543210","service":"AI Automation"}"
echo ========================================
start http://localhost:20129
pause
