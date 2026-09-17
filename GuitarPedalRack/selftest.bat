@echo off
REM ===========================================================================
REM  Compila y ejecuta el test del motor de audio (sin GUI).
REM  Sirve para comprobar que los plugins cargan y el audio los atraviesa.
REM ===========================================================================

setlocal

set "VSBT=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"
set "VSCMAKE=%VSBT%\Common7\IDE\CommonExtensions\Microsoft\CMake"

call "%VSBT%\VC\Auxiliary\Build\vcvars64.bat" >nul
set "PATH=%VSCMAKE%\CMake\bin;%VSCMAKE%\Ninja;%PATH%"

cd /d "%~dp0"

cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1

cmake --build build --target RackSelfTest
if errorlevel 1 exit /b 1

echo.
"build\RackSelfTest_artefacts\Release\RackSelfTest.exe"

endlocal
