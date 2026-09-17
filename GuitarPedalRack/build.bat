@echo off
REM ===========================================================================
REM  Compila Guitar Pedal Rack.
REM  Doble click en este archivo y espera. El .exe sale en:
REM      build\GuitarPedalRack_artefacts\Release\Guitar Pedal Rack.exe
REM ===========================================================================

setlocal

set "VSBT=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"
set "VSCMAKE=%VSBT%\Common7\IDE\CommonExtensions\Microsoft\CMake"

REM Carga las variables de entorno del compilador MSVC (cl.exe, libs, SDK).
call "%VSBT%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 (
    echo ERROR: no se pudo cargar el entorno de MSVC
    exit /b 1
)

set "PATH=%VSCMAKE%\CMake\bin;%VSCMAKE%\Ninja;%PATH%"

cd /d "%~dp0"

echo.
echo === Configurando ===
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1

echo.
echo === Compilando (tarda varios minutos la primera vez) ===
cmake --build build --config Release
if errorlevel 1 exit /b 1

echo.
echo === LISTO ===
endlocal
