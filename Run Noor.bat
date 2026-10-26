@echo off
cd /d "%~dp0"
if exist "pi\.venv\Scripts\python.exe" (
  "pi\.venv\Scripts\python.exe" pi\app.py --windowed
) else if exist "functions\venv\Scripts\python.exe" (
  "functions\venv\Scripts\python.exe" pi\app.py --windowed
) else (
  python pi\app.py --windowed
)
if errorlevel 1 pause
