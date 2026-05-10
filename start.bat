@echo off
echo Starting EducAgent...

:: Start Backend in current window
call .\venv\Scripts\activate.bat
start "EducAgent Frontend" cmd /c "cd frontend && npm run dev"
uvicorn main:app --reload --port 8000
