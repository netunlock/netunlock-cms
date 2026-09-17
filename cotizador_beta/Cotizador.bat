@echo off
title Cotizador de Aberturas de Aluminio
cd /d "%~dp0"

python main.py
if %errorlevel% equ 0 goto :fin

echo.
echo No se pudo iniciar con "python". Probando con el lanzador "py"...
echo.
py main.py
if %errorlevel% equ 0 goto :fin

echo.
echo ============================================================
echo  No se pudo iniciar la aplicacion.
echo.
echo  Revisa que Python este instalado y agregado al PATH:
echo    https://www.python.org/downloads/
echo.
echo  Y que las dependencias esten instaladas:
echo    pip install -r requirements.txt
echo ============================================================
echo.
pause

:fin
