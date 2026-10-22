@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo   Iniciando Versão Web ZNT Agência (Streamlit)...
echo ========================================================
echo.

".venv\Scripts\streamlit.exe" run web_app.py
pause
