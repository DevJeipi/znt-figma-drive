@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Criando ambiente virtual Python...
    python -m venv .venv
    echo [2/2] Instalando bibliotecas necessarias...
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

start "" ".venv\Scripts\pythonw.exe" app.py
