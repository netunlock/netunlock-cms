@echo off
REM ============================================================
REM  Convertir PDFs.bat
REM  Dos formas de usarlo:
REM   1) Doble clic  -> convierte todos los PDF de la carpeta "entrada"
REM   2) Arrastrar y soltar archivos o carpetas sobre este .bat
REM  Los .md salen en la carpeta "salida".
REM ============================================================

chcp 65001 >nul
setlocal

REM %~dp0 = carpeta donde esta este .bat (termina en \)
set "PY=%~dp0.venv\Scripts\python.exe"
set "SCRIPT=%~dp0convertir.py"

if not exist "%PY%" (
    echo No se encontro el entorno virtual en:
    echo   %PY%
    echo.
    echo Crealo con:  py -m venv .venv  ^&^&  .venv\Scripts\pip install "markitdown[pdf]"
    echo.
    pause
    exit /b 1
)

REM %* = todos los argumentos arrastrados. Si esta vacio, el script usa "entrada".
"%PY%" "%SCRIPT%" %*

echo.
pause
