@echo off
cd /d "%~dp0"
python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo The dashboard stopped with an error.
    pause
)
