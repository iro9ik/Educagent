@echo off
echo Testing EducAgent...
call .\venv\Scripts\activate.bat
python test_api.py
pause
