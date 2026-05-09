@echo off
echo Starting EducAgent...
call .\venv\Scripts\activate.bat
uvicorn main:app --reload
