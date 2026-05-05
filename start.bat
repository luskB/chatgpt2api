@echo off
setlocal
cd /d "%~dp0"
set "CHATGPT2API_AUTH_KEY=chatgpt2api"
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8866 --access-log
pause
